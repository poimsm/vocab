from typing import List, Optional
from sqlmodel import Session, select
from logging_client import logger

from models import (
    GenerationQueue,
    QueueStatus,
    QueueRefillStatus,
    ContentType,
)


def pending(db: Session, content_type: ContentType, user_id: int) -> List:
    statement = (
        select(GenerationQueue)
        .where(
            GenerationQueue.user_id == user_id,
            GenerationQueue.type == content_type,
            GenerationQueue.status == QueueStatus.PENDING,
            GenerationQueue.is_active == True,
        )
        .order_by(GenerationQueue.created_at)
    )

    return db.exec(statement).all()


def enqueue(db: Session, content_type: ContentType, user_id: int, items: List) -> None:
    for item in items:
        queue_item = GenerationQueue(
            content_id=item.id,
            type=content_type,
            user_id=user_id,
            status=QueueStatus.PENDING,
            is_active=True,
        )
        db.add(queue_item)

    db.commit()
    logger.info(f"[Queue Repository] Enqueued {len(items)} {content_type.value} items for user {user_id}")


def mark_resolved(db: Session, queue_item_id: int) -> None:
    queue_item = db.exec(
        select(GenerationQueue).where(GenerationQueue.id == queue_item_id)
    ).first()

    if queue_item:
        queue_item.status = QueueStatus.RESOLVED
        db.add(queue_item)
        db.commit()
        logger.info(f"[Queue Repository] Marked queue item {queue_item_id} as RESOLVED")


def resolve_completed(db: Session, content_type: ContentType, user_id: int) -> None:
    statement = (
        select(GenerationQueue)
        .where(
            GenerationQueue.user_id == user_id,
            GenerationQueue.type == content_type,
            GenerationQueue.status == QueueStatus.SENT,
            GenerationQueue.is_active == True,
        )
    )

    items = db.exec(statement).all()

    for item in items:
        item.status = QueueStatus.RESOLVED
        db.add(item)

    if items:
        db.commit()
        logger.info(f"[Queue Repository] Resolved {len(items)} {content_type.value} items for user {user_id}")


def is_generating(db: Session, content_type: ContentType, user_id: int) -> bool:
    status = db.exec(
        select(QueueRefillStatus).where(
            QueueRefillStatus.user_id == user_id,
            QueueRefillStatus.queue_type == content_type,
            QueueRefillStatus.is_refilling == True,
        )
    ).first()

    return status is not None

def get_by_id(db: Session, queue_item_id: int) -> Optional[GenerationQueue]:
    return db.exec(
        select(GenerationQueue).where(GenerationQueue.id == queue_item_id)
    ).first()

