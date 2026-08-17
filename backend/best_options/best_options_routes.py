from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload

from db import get_db
from logging_client import logger
from auth.repository import get_current_user
from models import User, ContentType, ContentQueue, BestOption, Word
from decorators import log_endpoint
from best_options.best_options_schemas import BestOptionResponse
from best_options.best_options_repository import BestOptionRepository
from examples.example_repository import ExampleRepository


router = APIRouter()


@router.get("/explore", response_model=BestOptionResponse)
@log_endpoint
def get_best_options(
    limit: int = 6,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene los siguientes best options de la ContentQueue.

    Flujo:
    1. Obtener items PENDING de ContentQueue
    2. Para cada item, obtener el BestOption correspondiente
    3. Retornar con detalles del contenido
    """
    from models import ContentType, ContentQueue, BestOption
    from learning_path.content_queue import ContentQueue as ContentQueueManager
    from learning_path.content_planner import ContentPlanner
    from learning_path.priority_engine import PriorityEngine

    logger.info(f"[get_best_options] User {current_user.id}: Fetching best options (limit={limit})")

    queue_mgr = ContentQueueManager(db)

    # Obtener items pendientes
    queue_items = queue_mgr.next_many(
        user_id=current_user.id,
        content_type=ContentType.BEST_OPTIONS,
        amount=limit,
    )

    if not queue_items:
        logger.debug(f"[get_best_options] No pending best options for user {current_user.id}")
        # Si no hay contenido, asegurar que hay suficiente
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
        content_planner.ensure_ready(current_user.id, ContentType.BEST_OPTIONS)

        return {
            "items": [],
            "total": 0,
            "status": "generating",
        }

    # Obtener los best options asociados con sus palabras
    best_option_ids = [item.content_id for item in queue_items]

    best_options = db.exec(
        select(BestOption)
        .where(BestOption.id.in_(best_option_ids))
        .options(joinedload(BestOption.word))
    ).all()

    logger.debug(f"[get_best_options] Retrieved {len(best_options)} best options")

    # Construir respuesta con información completa de palabras
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
            "examples": [],  # TODO: cargar ejemplos si es necesario
        }

        items_response.append({
            "queue_item_id": queue_item.id,
            "best_option_id": best_option.id,
            "word": word_data,
            "question": best_option.question,
            "options": best_option.options.split(";"),
            "correct_option": best_option.correct_option,
        })

    return {
        "items": items_response,
        "total": len(best_options),
        "status": "ok",
    }



@router.patch("/{queue_item_id}/resolve")
@log_endpoint
def resolve_best_option(
    queue_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Marca un best option como consumido y registra la exposición.

    Flujo:
    1. Obtener item de ContentQueue
    2. Llamar a LearningTracker.record_exposure()
    3. Marcar item como CONSUMED
    """
    from models import ContentQueue
    from learning_path.content_queue import ContentQueue as ContentQueueManager
    from learning_path.learning_tracker import LearningTracker
    from examples.example_repository import ExampleRepository
    from best_options.best_options_repository import BestOptionRepository

    logger.info(f"[resolve_best_option] User {current_user.id}: Resolving queue item {queue_item_id}")

    # Obtener item
    queue_item = db.get(ContentQueue, queue_item_id)

    if not queue_item or queue_item.user_id != current_user.id:
        logger.warning(f"[resolve_best_option] Queue item {queue_item_id} not found")
        raise HTTPException(status_code=404, detail="Item no encontrado")

    # Registrar exposición
    example_repo = ExampleRepository(db)
    best_option_repo = BestOptionRepository(db)
    tracker = LearningTracker(db, example_repo, best_option_repo)

    tracker.record_exposure(
        user_id=current_user.id,
        content_type=queue_item.type,
        content_id=queue_item.content_id,
    )

    # Marcar como consumido
    queue_mgr = ContentQueueManager(db)
    queue_mgr.consume(queue_item_id)

    logger.debug(f"[resolve_best_option] Queue item {queue_item_id} resolved")

    return {"status": "ok"}

