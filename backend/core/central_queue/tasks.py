# tasks.py (ejemplo con Celery)
from celery_app import celery_app
from core.central_queue.processor import CentralQueueProcessor
from sqlmodel import Session
from logging_client import logger


@celery_app.task(queue='background_queue')
def process_central_queue(queue_type: str):
    """Tarea de Celery para drenar la cola central de forma síncrona en un worker dedicado."""
    print(f"Processing central queue in background: {queue_type}")

    from db import engine
    try:
        with Session(engine) as db:

            processor = CentralQueueProcessor(engine=db, queue_type=queue_type)
            processor.process_sync()

    except Exception as e:
        logger.error(
            f"[CentralQueue] ....: {e}",
            exc_info=True,
        )
