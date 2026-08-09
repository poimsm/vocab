from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select, func

from db import get_db
from logging_client import logger
from auth.repository import get_current_user
from models import User
from decorators import log_endpoint
from best_options import repository as BestOptionRepository
from generation.queue.processor import GenerationProcessor
from generation.queue.best_option_generation_strategy import BestOptionGenerationStrategy
from generation.queue import repository as QueueRepository
from schemas.best_options import BestOptionResponse


router = APIRouter()


@router.get("/explore", response_model=BestOptionResponse)
@log_endpoint
def get_best_options(
    limit: int = 6,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from sqlmodel import select
    from models import BestOption

    processor = GenerationProcessor(
        db,
        current_user.id,
        BestOptionGenerationStrategy
    )
    result = processor.process(limit)

    # Transformar items si hay
    if result.get("items"):
        transformed_items = []
        for item in result["items"]:
            best_option = db.exec(
                select(BestOption).where(BestOption.id == item.content_id)
            ).first()

            transformed_items.append({
                "id": best_option.id if best_option else 0,
                "queue_item_id": item.id,
                "content_id": item.content_id,
                "question": best_option.question if best_option else "",
                "options": best_option.options.split(";") if best_option and best_option.options else [],
                "correct_option": best_option.correct_option if best_option else 0,
                "word": {
                    "id": best_option.word.id if best_option and best_option.word else 0,
                    "main": best_option.word.main if best_option and best_option.word else "",
                    "type": best_option.word.type if best_option and best_option.word else "",
                    "meaning": best_option.word.meaning if best_option and best_option.word else "",
                    "level": best_option.word.level if best_option and best_option.word else 0,
                    "is_boosted": best_option.word.is_boosted if best_option and best_option.word else False,
                    "batch_id": best_option.word.batch_id if best_option and best_option.word else None
                }
            })
        result["items"] = transformed_items

    return result
    

@router.patch("/{queue_item_id}/resolve")
@log_endpoint
def resolve_best_option(
    queue_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.debug(f"[resolve_best_option] User {current_user.id}: Resolving best option queue item {queue_item_id}")

    queue_item = QueueRepository.get_by_id(db, queue_item_id)
    if not queue_item:
        logger.warning(f"[resolve_best_option] Queue item {queue_item_id} not found")
        raise HTTPException(status_code=404, detail="Queue item not found")

    QueueRepository.mark_resolved(db, queue_item_id)

    best_option = BestOptionRepository.increment_statistics(db, content_id=queue_item.content_id, user_id=current_user.id)

    if not best_option:
        logger.warning(f"[resolve_best_option] Best option {queue_item.content_id} not found or not pending")
        raise HTTPException(
            status_code=404,
            detail="Best option not found or no longer pending"
        )

    logger.info(f"[resolve_best_option] Best option {queue_item.content_id} resolved successfully. Times seen: {best_option.times_seen}")

    return {
        "id": best_option.id,
        "status": "resolved",
        "message": "Best option exercise resolved successfully. Views incremented.",
    }

