from sqlmodel import Session
from db import engine
from celery_app import celery_app
from core.boost.repository import BoostRepository
from core.boost.strategies import BoostDemandStrategy
from core.generation_ai.repository import GenerationAIRepository
from core.event_bus import subscribe_to_background
from core.celery_queues import CeleryQueue
from core.enums import ContentType
from core.generation_ai.enums import GenerationAIStatus
from logging_client import logger
from typing import Optional


@subscribe_to_background('word.unboosted')
@celery_app.task(name="boost.on_word_unboosted", queue=CeleryQueue.BACKGROUND)
def deactivate_word_task(user_id: int, word_id: int) -> None:
    """Suscriptor al evento 'event.word.unboosted'. Desactiva el boost cuando se des-boostea."""
    logger.info(f"[Celery] Procesando desactivación de boost para user_id={user_id}, word_id={word_id}")

    with Session(engine) as session:
        repository = BoostRepository(session)
        repository.deactivate(user_id, word_id)

        # Limpiar monitoreo de generación para esta palabra
        cleared = repository.clear_generation_monitor(user_id, word_id)
        if cleared > 0:
            logger.info(f"[Boost] Limpiados {cleared} registros de monitoreo para word_id={word_id}")

        logger.info(f"[Boost] Boost desactivado exitosamente para word_id={word_id}.")


@subscribe_to_background('boost.content.exhausted')
@celery_app.task(name="boost.on_content_exhausted", queue=CeleryQueue.BACKGROUND)
def refill_boost_content_task(
    user_id: int,
    word_id: int,
    content_type: str,
    **kwargs
) -> None:
    """
    Suscriptor al evento 'event.boost.content_exhausted'.
    Encola la regeneración de contenido cuando se agota el contenido boosteado.
    Usa get_refill_pack pero solo para el content_type que se agotó.
    Registra el inicio de generación en el monitor.
    """
    logger.info(
        f"[Boost] Content exhausted for boosted word {word_id}: {content_type}. Enqueueing refill..."
    )

    with Session(engine) as session:
        boost_repo = BoostRepository(session)
        generation_repo = GenerationAIRepository(session)

        # Registrar el inicio de generación en el monitor
        content_type_enum = ContentType(content_type)
        monitor = boost_repo.start_generation_monitor(
            user_id=user_id,
            word_id=word_id,
            content_type=content_type_enum
        )
        logger.info(f"[Boost] Generation monitor started for word_id={word_id}, content_type={content_type}")

        # Obtener el pack de reposición
        refill_demands = BoostDemandStrategy.get_refill_pack()

        # Filtrar para solo el content_type que se agotó
        filtered_demands = [d for d in refill_demands if d.skill_type == content_type]

        if not filtered_demands:
            logger.warning(
                f"[Boost] No refill demand found for content_type: {content_type}"
            )
            return

        # Encolar la demanda de regeneración
        for demand in filtered_demands:
            logger.info(
                f"[Boost] Enqueueing {demand.quantity} {demand.skill_type} for word {word_id}"
            )
            generation_repo.enqueue_demand(
                user_id=user_id,
                word_id=word_id,
                skill_type=demand.skill_type,
                quantity=demand.quantity,
                is_boost=True,
            )

        logger.info(
            f"[Boost] Refill demand enqueued successfully for word {word_id} ({content_type})"
        )


@subscribe_to_background('content.generated')
@celery_app.task(name="boost.on_content_generated", queue=CeleryQueue.BACKGROUND)
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
    Si el contenido es del módulo boost, actualiza el estado del monitor de generación.
    """
    # Solo procesar si es del módulo boost y hay word_id
    if content_source_type != "boost" or not word_id:
        return

    logger.info(
        f"[Boost] Content generated event received for word_id={word_id}, "
        f"content_type={content_type}, status={status}"
    )

    with Session(engine) as session:
        repository = BoostRepository(session)

        try:
            content_type_enum = ContentType(content_type)

            if status == GenerationAIStatus.COMPLETED.value:
                logger.info(
                    f"[Boost] Marking generation monitor as COMPLETED for word_id={word_id}, "
                    f"content_type={content_type}"
                )
                repository.complete_generation_monitor(
                    user_id=user_id,
                    word_id=word_id,
                    content_type=content_type_enum
                )
            elif status == GenerationAIStatus.FAILED.value:
                logger.info(
                    f"[Boost] Marking generation monitor as FAILED for word_id={word_id}, "
                    f"content_type={content_type}"
                )
                repository.fail_generation_monitor(
                    user_id=user_id,
                    word_id=word_id,
                    content_type=content_type_enum,
                    error_message=f"Content generation failed (content_id={content_id})"
                )
            else:
                logger.warning(
                    f"[Boost] Unknown status '{status}' for generation monitor "
                    f"(word_id={word_id}, content_type={content_type})"
                )
        except ValueError as e:
            logger.error(f"[Boost] Invalid content_type '{content_type}': {e}")