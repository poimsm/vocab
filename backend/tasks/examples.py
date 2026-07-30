from sqlmodel import Session, select
from celery_app import celery_app
from db import engine
import crud
from logging_config import logger
from models import User


@celery_app.task(name="tasks.examples.refill_queue")
def refill_queue_task(user_id: int):  # <-- Recibe el user_id
    """
    Tarea Celery para rellenar la cola de ejemplos de un usuario en segundo plano.
    """
    logger.info(
        f"[Celery Examples] Starting example queue refill for user {user_id}..."
    )

    with Session(engine) as db:
        try:
            # Pasamos user_id a la lógica de CRUD
            crud.refill_example_queue(db, user_id=user_id)
            logger.info(
                f"[Celery Examples] Example queue successfully refilled for user {user_id}."
            )
        except Exception as e:
            logger.error(
                f"[Celery Examples] Critical error refilling example queue for user {user_id}: {e}",
                exc_info=True,
            )


@celery_app.task(name="tasks.examples.spaced_repetition_daily")
def spaced_repetition_daily_task():
    """
    Tarea Celery programada para ejecutarse diariamente.
    Reabre gradualmente batches completados (1 por usuario por día) para memoria espaciada.
    """
    logger.info("[Celery Spaced Repetition] Starting daily batch reopening process...")

    with Session(engine) as db:
        try:
            # Obtener todos los usuarios activos
            users = db.exec(select(User).where(User.is_active == True)).all()

            reactivated_count = 0
            for user in users:
                result = crud.reopen_batches_for_spaced_repetition(db, user.id)
                if result.get("reopened", 0) > 0:
                    reactivated_count += 1

            logger.info(
                f"[Celery Spaced Repetition] Process completed. Batches reopened in {reactivated_count} users."
            )

        except Exception as e:
            logger.error(
                f"[Celery Spaced Repetition] Critical error in daily process: {e}",
                exc_info=True,
            )