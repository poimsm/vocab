from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from typing import Optional, List
from pydantic import BaseModel

from db import get_db
from logging_client import logger
from auth.repository import get_current_user
from models import User, ContentType, ContentQueue, BestOption, Word
from decorators import log_endpoint
from best_options.best_options_schemas import BestOptionResponse
from best_options.best_options_repository import BestOptionRepository
from examples.example_repository import ExampleRepository


class BestOptionExploreRequest(BaseModel):
    """Request para el endpoint de explore con acciones encadenables."""
    actions: List[str] = ["next"]  # Acciones a ejecutar: ["resolve", "next"], ["next"], etc.
    resolve_queue_item_id: Optional[int] = None  # Requerido si actions incluye "resolve"
    limit: int = 6  # Para la acción "next"


router = APIRouter()


# ==================== Acciones Auxiliares ====================

def _action_resolve(
    db: Session,
    queue_item_id: int,
    current_user: User,
) -> bool:
    """
    Acción: Resolver un item (registrar exposición + marcar CONSUMED).

    Retorna True si fue exitoso, False si el item no existe.
    """
    logger.debug(f"[_action_resolve] Resolving queue_item_id={queue_item_id}")

    # Obtener con FOR UPDATE para bloquear la fila
    queue_item = db.exec(
        select(ContentQueue)
        .where(ContentQueue.id == queue_item_id)
        .with_for_update()
    ).first()

    if not queue_item or queue_item.user_id != current_user.id:
        logger.warning(f"[_action_resolve] Queue item {queue_item_id} not found or unauthorized")
        return False

    # Registrar exposición
    from learning_path.learning_tracker import LearningTracker
    example_repo = ExampleRepository(db)
    best_option_repo = BestOptionRepository(db)
    tracker = LearningTracker(db, example_repo, best_option_repo)

    tracker.record_exposure(
        user_id=current_user.id,
        content_type=queue_item.type,
        content_id=queue_item.content_id,
    )

    # Marcar como consumido
    from learning_path.content_queue import ContentQueue as ContentQueueManager
    queue_mgr = ContentQueueManager(db)
    queue_mgr.consume(queue_item_id)

    logger.debug(f"[_action_resolve] Successfully resolved queue_item_id={queue_item_id}")
    return True


def _action_next(
    db: Session,
    current_user: User,
    limit: int,
) -> tuple[list, str]:
    """
    Acción: Obtener los siguientes items de la cola.

    Retorna (best_options, status).
    Status puede ser: "ok", "generating", "no_words"
    """
    from learning_path.content_queue import ContentQueue as ContentQueueManager

    logger.debug(f"[_action_next] Fetching next {limit} best options")

    queue_mgr = ContentQueueManager(db)

    # Obtener items pendientes
    queue_items = queue_mgr.next_many(
        user_id=current_user.id,
        content_type=ContentType.BEST_OPTIONS,
        amount=limit,
    )

    logger.debug(f"[_action_next] Got {len(queue_items)} items from queue")

    if not queue_items:
        logger.debug(f"[_action_next] No pending items, checking if content generation is needed")

        # Inicializar componentes para planificación
        from learning_path.content_planner import ContentPlanner
        from learning_path.priority_engine import PriorityEngine
        from words.word_repository import WordRepository

        priority_engine = PriorityEngine()
        word_repo = WordRepository(db)
        best_option_repo = BestOptionRepository(db)
        example_repo = ExampleRepository(db)

        content_planner = ContentPlanner(
            session=db,
            priority_engine=priority_engine,
            content_queue=queue_mgr,
            word_repository=word_repo,
            example_repository=example_repo,
            best_option_repository=best_option_repo,
        )

        # Chequear si hay palabras NO LEARNED
        has_words = content_planner.has_non_learned_words(current_user.id, ContentType.BEST_OPTIONS)

        if not has_words:
            logger.info(f"[_action_next] User {current_user.id} has no non-LEARNED words")
            return [], "no_words"

        # Trigger generation
        content_planner.ensure_ready(current_user.id, ContentType.BEST_OPTIONS)
        logger.debug(f"[_action_next] Content generation triggered")

        return [], "generating"

    # Obtener best options con detalles
    best_option_ids = [item.content_id for item in queue_items]

    best_options = db.exec(
        select(BestOption)
        .where(BestOption.id.in_(best_option_ids))
        .options(joinedload(BestOption.word))
    ).all()

    logger.debug(f"[_action_next] Retrieved {len(best_options)} best option records")

    # Construir respuesta
    items_response = []
    for queue_item, best_option in zip(queue_items, best_options):
        word_data = {
            "id": best_option.word.id,
            "main": best_option.word.main,
            "meaning": best_option.word.meaning,
            "type": best_option.word.type,
            "level": best_option.word.level,
            "synonyms": best_option.word.synonyms or [],
            "frequency": best_option.word.frequency,
            "examples": [],
        }

        items_response.append({
            "queue_item_id": queue_item.id,
            "best_option_id": best_option.id,
            "word": word_data,
            "question": best_option.question,
            "options": best_option.options.split(";"),
            "correct_option": best_option.correct_option,
        })

    return items_response, "ok"


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

    TODO ATÓMICO - una sola transacción.
    """
    logger.info(
        f"[explore_best_options] User {current_user.id}: actions={request.actions}, "
        f"resolve_id={request.resolve_queue_item_id}, limit={request.limit}"
    )

    items = []
    status = "ok"

    # Ejecutar acciones en orden
    for action in request.actions:
        if action == "resolve":
            if request.resolve_queue_item_id is None:
                logger.warning(f"[explore_best_options] Action 'resolve' requires resolve_queue_item_id")
                raise HTTPException(
                    status_code=400,
                    detail="Action 'resolve' requires resolve_queue_item_id parameter"
                )

            success = _action_resolve(db, request.resolve_queue_item_id, current_user)
            if not success:
                logger.warning(f"[explore_best_options] Action 'resolve' failed for item {request.resolve_queue_item_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Item to resolve not found"
                )

        elif action == "next":
            items, status = _action_next(db, current_user, request.limit)

        else:
            logger.warning(f"[explore_best_options] Unknown action: {action}")
            raise HTTPException(
                status_code=400,
                detail=f"Unknown action: {action}. Valid actions: 'resolve', 'next'"
            )

    logger.info(f"[explore_best_options] Completed with status={status}, returned {len(items)} items")

    return {
        "items": items,
        "total": len(items),
        "status": status,
    }

