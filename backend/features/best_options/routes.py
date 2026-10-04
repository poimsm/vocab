from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import Optional, List
from pydantic import BaseModel

from db import get_db
from logging_client import logger
from auth.repository import get_current_user
from auth.models import User
from decorators import log_endpoint
from core.enums import ContentType
from features.best_options.schemas import BestOptionResponse
from core.explore.explore_actions import ExploreActions
from features.best_options.response_builder import BestOptionsResponseBuilder
from activity.user_activity_service import UserActivityService
from features.examples.repository import ExampleRepository


class BestOptionExploreRequest(BaseModel):
    """Request para el endpoint de explore con acciones encadenables."""
    actions: List[str] = ["next"]  # Acciones a ejecutar: ["resolve", "next"], ["next"], etc.
    resolve_queue_item_id: Optional[int] = None  # Requerido si actions incluye "resolve"
    limit: int = 6  # Para la acción "next"
    buffer_delivery_ids: List[int] = []  # IDs actuales del buffer
    buffer_position: int = 0  # Posición actual en el buffer


router = APIRouter()


@router.post("/explore", response_model=BestOptionResponse)
@log_endpoint
def explore_best_options(
    request: BestOptionExploreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint unificado con acciones encadenables para best options.

    Body:
    {
      "actions": ["resolve", "next"],  // Acciones a ejecutar en orden
      "resolve_queue_item_id": 47,      // Requerido si actions contiene "resolve"
      "limit": 6                        // Para acción "next"
    }

    Ejemplos:
    - {"actions": ["next"], "limit": 6}
      → Solo obtener 6 best options

    - {"actions": ["resolve", "next"], "resolve_queue_item_id": 47, "limit": 5}
      → Resolver item 47, luego obtener 5 best options

    - {"actions": ["resolve"], "resolve_queue_item_id": 47}
      → Solo resolver item 47, no obtener nuevos
    """
    logger.info(
        f"[explore_best_options] User {current_user.id}: actions={request.actions}, "
        f"resolve_id={request.resolve_queue_item_id}, limit={request.limit}"
    )

    # Log de actividad
    UserActivityService.log_feature_interaction(
        db=db,
        user_id=current_user.id,
        feature_name="best_options_explore",
        interaction_type="_".join(request.actions),
        details={
            "actions": request.actions,
            "limit": request.limit
        }
    )

    try:
        from features.content_repository import UnifiedContentRepository
        content_repo = UnifiedContentRepository(db)

        # Crear validador agnóstico usando ExampleRepository
        class ExampleContentValidator:
            def __init__(self, example_repo):
                self.example_repo = example_repo

            def is_content_learned(self, content_id: int, user_id: int) -> bool:
                return self.example_repo.is_example_learned(content_id, user_id)

        content_validator = ExampleContentValidator(ExampleRepository(db))

        explore_actions = ExploreActions(
            db,
            content_repo=content_repo,
            content_validator=content_validator
        )
        status, buffer_ids, buffer_position = explore_actions.execute_actions(
            user_id=current_user.id,
            actions=request.actions,
            content_type=ContentType.BEST_OPTIONS,
            resolve_queue_item_id=request.resolve_queue_item_id,
            limit=request.limit,
            buffer_delivery_ids=request.buffer_delivery_ids,
            buffer_position=request.buffer_position,
        )
    except ValueError as e:
        logger.error(f"[explore_best_options] Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    # Build best options response using BestOptionsResponseBuilder
    items = []
    if buffer_ids:
        # Obtener objetos DeliveryBuffer usando los IDs
        from core.delivery.repository import DeliveryRepository
        from core.delivery.service import DeliveryService
        delivery_service = DeliveryService(db)
        delivery_items = delivery_service.get_delivery_items_by_ids(buffer_ids, current_user.id)

        # Construir respuesta con los objetos
        response_builder = BestOptionsResponseBuilder(db)
        items = response_builder.build_best_options_response(delivery_items, current_user.id)

        # Marcar delivery items como DISPATCHED
        delivery_repo = DeliveryRepository(db)
        dispatched_count = delivery_repo.mark_multiple_as_dispatched(buffer_ids)
        logger.debug(
            f"[explore_best_options] Marked {dispatched_count} delivery items as DISPATCHED"
        )

        # Actualizar sesión de exploración con los IDs y posición actual
        from core.explore.explore_repository import ExploreRepository
        explore_repo = ExploreRepository(db)
        explore_repo.update_session(current_user.id, buffer_ids, buffer_position, ContentType.BEST_OPTIONS.value)
        logger.debug(
            f"[explore_best_options] Updated explore session: {len(buffer_ids)} items at position {buffer_position}"
        )

    logger.info(f"[explore_best_options] Completed with status={status}, returned {len(items)} items")

    return {
        "items": items,
        "total": len(items),
        "buffer_delivery_ids": buffer_ids,
        "buffer_position": buffer_position,
        "status": status,
    }

