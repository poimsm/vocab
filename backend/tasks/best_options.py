from sqlmodel import Session, select
from celery_app import celery_app
from db import engine
import crud
import ai
from logging_config import logger
from models import BestOption, BestOptionQueue, QueueStatus


@celery_app.task(name="tasks.best_options.refill_queue")
def refill_best_options_queue_task(user_id: int):
    """
    Tarea Celery para rellenar la cola de best_options de un usuario en segundo plano.
    - Busca 8 palabras que el usuario ya ha visto
    - Genera 8 ejercicios de best_options usando IA
    - Guarda los ejercicios en la cola sin vaciar registros previos
    """
    logger.info(f"[Celery BestOptions] Starting best options queue refill for user {user_id}...")

    with Session(engine) as db:
        try:
            # 1. Obtener 8 palabras que el usuario ha visto (least seen words)
            words = crud.get_words_least_seen_ordered(db, user_id=user_id, limit=8)

            if not words or len(words) < 8:
                logger.warning(
                    f"[Celery BestOptions] Not enough words available for user {user_id}. "
                    f"Got {len(words) if words else 0}, need 8. Skipping refill."
                )
                return

            logger.info(f"[Celery BestOptions] Found {len(words)} words for user {user_id}")

            # 2. Generar ejercicios de best_options usando IA
            raw_best_options = ai.generate_best_options_from_words(words)

            if not raw_best_options:
                logger.error(f"[Celery BestOptions] Failed to generate best options for user {user_id}")
                return

            logger.info(f"[Celery BestOptions] Generated {len(raw_best_options)} exercise sets for user {user_id}")

            # 3. Procesar cada set de ejercicios del resultado de IA
            newly_queued = 0
            for exercise_set in raw_best_options:
                word_id = exercise_set.get("word_id")
                questions = exercise_set.get("questions", [])

                if not questions:
                    continue

                # Por cada pregunta, crear un BestOption y agregarlo a la cola
                for question_data in questions:
                    question_text = question_data.get("question")
                    options = question_data.get("options", [])
                    correct_option_idx = question_data.get("correct_option", 0)

                    if not question_text or not options:
                        continue

                    # Crear la cadena de opciones separadas por ";"
                    options_string = ";".join(options)

                    # Crear el BestOption en DB
                    best_option = BestOption(
                        question=question_text,
                        options=options_string,
                        correct_option=correct_option_idx
                    )
                    db.add(best_option)
                    db.flush()  # Generar el ID del BestOption

                    # Verificar que no esté ya en la cola del usuario
                    existing_queue = db.exec(
                        select(BestOptionQueue).where(
                            BestOptionQueue.user_id == user_id,
                            BestOptionQueue.best_option_id == best_option.id
                        )
                    ).first()

                    if not existing_queue:
                        # Agregar a la cola con estado PENDING
                        queue_item = BestOptionQueue(
                            user_id=user_id,
                            best_option_id=best_option.id,
                            status=QueueStatus.PENDING
                        )
                        db.add(queue_item)
                        newly_queued += 1

            db.commit()
            logger.info(
                f"[Celery BestOptions] Successfully queued {newly_queued} new best option exercises "
                f"for user {user_id}."
            )

        except Exception as e:
            logger.error(
                f"[Celery BestOptions] Critical error refilling best options queue for user {user_id}: {e}",
                exc_info=True,
            )