# backend/core/delivery/tasks.py
from sqlmodel import Session
from db import engine
from celery_app import celery_app
from core.delivery.repository import DeliveryRepository
from core.delivery.service import DeliveryService
from core.event_bus import subscribe_to_background
from core.celery_queues import CeleryQueue
from core.enums import ContentSourceType
from logging_client import logger
from typing import List, Optional
from core.generation_ai.enums import GenerationAIStatus

@subscribe_to_background('word.unboosted')
@celery_app.task(name="delivery.on_word_unboosted", queue=CeleryQueue.BACKGROUND)
def discard_boost_word_task(user_id: int, word_id: int):
    """
    Suscriptor al evento global 'event.word.unboosted'.
    Descarta los ítems de contenido cuando una palabra es desboosteada.
    """
    logger.info(f"[Celery] Procesando unboost para user_id={user_id}, word_id={word_id}")

    with Session(engine) as session:
        repository = DeliveryRepository(session)
        repository.discard_boost_word_items(user_id, word_id)
        logger.info(f"[Delivery] Ítems descartados exitosamente para word_id={word_id}.")


@subscribe_to_background('content.generated')
@celery_app.task(name="delivery.on_content_generated", queue=CeleryQueue.BACKGROUND)
def register_generated_content_task(
    user_id: int,
    word_id: Optional[int],
    content_id: int,
    queue_item_id: Optional[int],
    content_type: str,
    content_source_type: str,
    status: str,
    **kwargs
) -> None:
    """
    Suscriptor al evento 'event.content.generated'.
    Registra un contenido generado en el buffer de delivery usando DeliveryService.
    Se recibe un evento por cada contenido generado (LIFO).
    """
    if status != GenerationAIStatus.COMPLETED.value:
        logger.info(f"[Delivery] Skipping registration: generation status is '{status}'")
        return

    logger.info(f"[Delivery] Registering content_id={content_id} to delivery buffer for user {user_id}")

    with Session(engine) as session:
        service = DeliveryService(session)

        try:
            from core.enums import ContentType as ContentTypeEnum
            content_type_enum = ContentTypeEnum(content_type)

            service.register_generated_content(
                user_id=user_id,
                content_id=content_id,
                source_type=ContentSourceType(content_source_type),
                content_type=content_type_enum,
                word_id=word_id,
                learning_path_queue_id=queue_item_id,
            )

            logger.info(f"[Delivery] Successfully registered content_id={content_id} for user {user_id}")

        except Exception as e:
            logger.error(f"[Delivery] Error registering content: {e}", exc_info=True)