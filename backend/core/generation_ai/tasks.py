from datetime import datetime, timezone
from sqlmodel import Session, select
from db import engine
from celery_app import celery_app
from core.generation_ai.models import GenerationAIRegistry
from core.generation_ai.repository import GenerationAIRepository
from core.event_bus import subscribe_to
from logging_client import logger
from typing import List, Optional
from core.generation_ai.enums import GenerationAIStatus


@celery_app.task(name="generation_ai.on_ai_generation_side_event")
def on_ai_generation_side_event(item_id: int, payload: str, **kwargs):
    with Session(engine) as session:
        statement = select(GenerationAIRegistry).where(
            GenerationAIRegistry.central_queue_id == item_id)
        ai_record = session.exec(statement).first()

        if ai_record and ai_record.status == GenerationAIStatus.PENDING:
            ai_record.status = GenerationAIStatus.PROCESSING
            ai_record.updated_at = datetime.now(timezone.utc)
            session.add(ai_record)
            session.commit()


@subscribe_to('event.word.cancelled')
@celery_app.task(name="generation_ai.on_word_cancelled")
def on_word_cancelled(user_id: int, word_id: int, source_type: str = "BOOST", **kwargs):
    """
    Suscriptor al evento 'event.word.cancelled'.
    Procesa cuando una palabra es cancelada de forma global.
    """
    with Session(engine) as session:
        repository = GenerationAIRepository(session)
        cancelled_count = repository.cancel_pending_tasks_for_word(
            user_id=user_id,
            word_id=word_id,
            source_type=source_type
        )
        print(
            f"[GenerationAI] Global cancellation event triggered: {cancelled_count} pending AI task(s) discarded for word_id={word_id}.")


@subscribe_to('event.word.unboosted')
@celery_app.task(name="generation_ai.on_word_unboosted")
def on_word_unboosted(user_id: int, word_id: int, **kwargs):
    """
    Suscriptor al evento 'event.word.unboosted'.
    Cancela tareas pendientes cuando una palabra es desboosteada.
    """
    with Session(engine) as session:
        repository = GenerationAIRepository(session)
        cancelled_count = repository.cancel_pending_tasks_for_word(
            user_id=user_id,
            word_id=word_id,
            source_type='BOOST'
        )
        print(
            f"[GenerationAI] Global unboost event triggered: {cancelled_count} pending AI task(s) discarded for word_id={word_id}.")


@celery_app.task(name="generation_ai.on_ai_completed")
def on_ai_completed(central_queue_id: int, **kwargs):
    with Session(engine) as session:
        repository = GenerationAIRepository(session)
        repository.mark_as_completed(central_queue_id)


@celery_app.task(name="generation_ai.on_ai_failed")
def on_ai_failed(central_queue_id: int, **kwargs):
    with Session(engine) as session:
        repository = GenerationAIRepository(session)
        repository.mark_as_failed(central_queue_id)


@subscribe_to('event.content.generated')
@celery_app.task(name="generation_ai.on_content_generated")
def on_content_generated(
    user_id: int,
    word_id: Optional[int],
    content_id: int,
    queue_item_id: Optional[int],
    content_type: str,
    content_source_type: str,
    status: str,
    **kwargs
):
    """
    Suscriptor al evento 'event.content.generated'.
    Actualiza el status de la GenerationAIQueue según el resultado de la generación.
    Se recibe un evento por cada contenido generado.
    """
    if not queue_item_id:
        return

    with Session(engine) as session:
        repository = GenerationAIRepository(session)

        if status == GenerationAIStatus.COMPLETED.value:
            logger.info(f"[GenerationAI] Marking queue_item {queue_item_id} as COMPLETED (content_id={content_id})")
            repository.mark_as_completed(queue_item_id)
        elif status == GenerationAIStatus.FAILED.value:
            logger.info(f"[GenerationAI] Marking queue_item {queue_item_id} as FAILED (content_id={content_id})")
            repository.mark_as_failed(queue_item_id, error_message="Content generation failed")
        else:
            logger.warning(f"[GenerationAI] Unknown status '{status}' for queue_item {queue_item_id}")