
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from db import get_db
from logging_client import logger
from auth.repository import get_current_user
from models import User, ContentType, ContentQueue, Example
from decorators import log_endpoint
from examples.example_schemas import ExploreResponse, ExploreExample
from learning_path.content_queue import ContentQueue as ContentQueueManager
from learning_path.learning_tracker import LearningTracker
from examples.example_repository import ExampleRepository
from best_options.best_options_repository import BestOptionRepository


router = APIRouter()


@router.get("/explore", response_model=ExploreResponse)
@log_endpoint
def get_explore_feed(
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene los siguientes examples de la ContentQueue.

    Flujo:
    1. Obtener items PENDING de ContentQueue
    2. Para cada item, obtener el Example correspondiente
    3. Segmentar el texto en chunks con target words resaltados
    4. Retornar con estructura de texto segmentado
    """
    logger.info(f"[get_explore_feed] User {current_user.id}: Fetching examples (limit={limit})")

    queue_mgr = ContentQueueManager(db)

    # Obtener items pendientes
    queue_items = queue_mgr.next_many(
        user_id=current_user.id,
        content_type=ContentType.EXAMPLE,
        amount=limit,
    )

    if not queue_items:
        logger.debug(f"[get_explore_feed] No pending examples for user {current_user.id}")
        return {
            "examples": [],
            "status": "ok",
        }

    # Obtener los examples asociados
    example_ids = [item.content_id for item in queue_items]
    examples = db.exec(
        select(Example).where(Example.id.in_(example_ids))
    ).all()

    logger.debug(f"[get_explore_feed] Retrieved {len(examples)} examples")

    # Segmentar el texto de cada ejemplo
    example_repo = ExampleRepository(db)
    examples_response = []

    for ex in examples:
        text_segments = example_repo.segment_example_text(ex)
        examples_response.append(
            {
                "id": ex.id,
                "text": text_segments,
            }
        )

    return {
        "examples": examples_response,
        "status": "ok",
    }



@router.patch("/{queue_item_id}/resolve")
@log_endpoint
def resolve_queue_item(
    queue_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Marca un example como consumido y registra la exposición.

    Flujo:
    1. Obtener item de ContentQueue
    2. Llamar a LearningTracker.record_exposure()
    3. Marcar item como CONSUMED
    """

    logger.info(f"[resolve_queue_item] User {current_user.id}: Resolving queue item {queue_item_id}")

    # Obtener item
    queue_item = db.get(ContentQueue, queue_item_id)

    if not queue_item or queue_item.user_id != current_user.id:
        logger.warning(f"[resolve_queue_item] Queue item {queue_item_id} not found")
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

    logger.debug(f"[resolve_queue_item] Queue item {queue_item_id} resolved")

    return {"status": "ok"}

