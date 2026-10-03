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
        status, queue_items = explore_actions.execute_actions(
            user_id=current_user.id,
            actions=request.actions,
            content_type=ContentType.BEST_OPTIONS,
            resolve_queue_item_id=request.resolve_queue_item_id,
            limit=request.limit,
        )
    except ValueError as e:
        logger.error(f"[explore_best_options] Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    # Build best options response using BestOptionsResponseBuilder
    items = []
    if queue_items:
        response_builder = BestOptionsResponseBuilder(db)
        items = response_builder.build_best_options_response(queue_items, current_user.id)

    logger.info(f"[explore_best_options] Completed with status={status}, returned {len(items)} items")

    return {
        "items": items,
        "total": len(items),
        "status": status,
    }

