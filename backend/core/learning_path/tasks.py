from typing import Optional, List
from sqlmodel import Session, select
from db import engine
from celery_app import celery_app
from core.learning_path.repository import LearningPathRepository
from core.enums import ContentType
from core.generation_ai.enums import GenerationAIStatus
from core.event_bus import subscribe_to, publish_event
from logging_client import logger


@subscribe_to('event.learning_path.content_exhausted')
@celery_app.task(name="learning_path.on_content_exhausted")
def on_content_exhausted(
    user_id: int,
    content_type: str,
    **kwargs
) -> None:
    """
    Suscriptor al evento 'event.learning_path.content_exhausted'.
    Se dispara cuando no hay contenido en el buffer del learning path pero hay palabras disponibles.
    Encola la generación de contenido y actualiza el monitor de generación.
    """
    logger.info(
        f"[LearningPath] Content exhausted for learning path: {content_type}. Enqueueing generation..."
    )

    with Session(engine) as session:
        try:
            content_type_enum = ContentType(content_type)

            # Actualizar monitor de generación: marcar como "generando"
            repository = LearningPathRepository(session)
            repository.start_generation_monitor(
                user_id=user_id,
                content_type=content_type_enum
            )
            logger.info(
                f"[LearningPath] Generation monitor started for user {user_id}, content_type={content_type}"
            )

            # Obtener palabras disponibles para generar
            from features.words.models import Word, WordStatistics
            from core.learning_path.models import LearningState

            statement = (
                select(Word.id)
                .join(WordStatistics)
                .where(
                    Word.user_id == user_id,
                    Word.is_active == True,
                    WordStatistics.type == content_type_enum,
                    WordStatistics.learning_state != LearningState.LEARNED,
                )
            )

            word_ids = session.exec(statement).all()

            if not word_ids:
                logger.warning(
                    f"[LearningPath] No available words for user {user_id} to generate {content_type}"
                )
                return

            # Limitar a 10 palabras para generación
            word_ids = word_ids[:10]

            logger.info(
                f"[LearningPath] Enqueueing generation for {len(word_ids)} words "
                f"(user_id={user_id}, content_type={content_type})"
            )

            # Disparar evento de solicitud de generación
            from core.enums import ContentSourceType
            publish_event(
                'event.generation.content_requested',
                user_id=user_id,
                word_ids=word_ids,
                content_type=content_type_enum.value,
                amount=10,
                content_source_type=ContentSourceType.LEARNING_PATH.value,
            )

            logger.info(
                f"[LearningPath] Generation enqueued successfully for user {user_id} ({content_type})"
            )

        except Exception as e:
            logger.error(
                f"[LearningPath] Error processing content_exhausted event for user {user_id}: {e}",
                exc_info=True
            )


@subscribe_to('event.content.generated')
@celery_app.task(name="learning_path.on_content_generated")
def on_content_generated(
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
    Si el contenido es del módulo learning_path (no boost), actualiza el estado del monitor.
    """
    # Solo procesar si NO es del módulo boost
    if content_source_type == "boost":
        return

    logger.info(
        f"[LearningPath] Content generated event received for "
        f"content_type={content_type}, status={status}"
    )

    with Session(engine) as session:
        repository = LearningPathRepository(session)

        try:
            content_type_enum = ContentType(content_type)

            if status == GenerationAIStatus.COMPLETED.value:
                logger.info(
                    f"[LearningPath] Marking generation monitor as COMPLETED for "
                    f"content_type={content_type}"
                )
                repository.complete_generation_monitor(
                    user_id=user_id,
                    content_type=content_type_enum
                )
            elif status == GenerationAIStatus.FAILED.value:
                logger.info(
                    f"[LearningPath] Marking generation monitor as FAILED for "
                    f"content_type={content_type}"
                )
                repository.fail_generation_monitor(
                    user_id=user_id,
                    content_type=content_type_enum,
                    error_message=f"Content generation failed (content_id={content_id})"
                )
            else:
                logger.warning(
                    f"[LearningPath] Unknown status '{status}' for generation monitor "
                    f"(content_type={content_type})"
                )
        except ValueError as e:
            logger.error(f"[LearningPath] Invalid content_type '{content_type}': {e}")
