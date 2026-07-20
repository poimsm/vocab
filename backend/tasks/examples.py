from sqlmodel import Session
from celery_app import celery_app
from db import engine
import crud
from logging_config import logger


@celery_app.task(name="tasks.examples.refill_queue")
def refill_queue_task():
    """
    Tarea Celery secuencial para rellenar la cola de ejemplos en segundo plano
    usando la IA sin bloquear la API.
    """
    logger.info("[Celery Examples] Iniciando rellenado de la cola de ejemplos (refill_example_queue)...")
    
    with Session(engine) as db:
        try:
            crud.refill_example_queue(db)
            logger.info("[Celery Examples] Cola de ejemplos rellenada con éxito.")
        except Exception as e:
            logger.error(
                f"[Celery Examples] Error crítico rellenando la cola de ejemplos: {e}",
                exc_info=True
            )