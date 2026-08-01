import random
from sqlmodel import Session, select
from celery_app import celery_app
from db import engine
import crud
import ai
from logging_config import logger
from models import BestOption, BestOptionQueue, QueueStatus, QueueType


def shuffle_options_with_correct_index(options: list, correct_option_idx: int) -> tuple:
    """
    Desordena una lista de opciones y retorna la lista desordenada
    junto con el nuevo índice de la opción correcta.
    Usa random.sample() para garantizar una permutación completamente aleatoria.

    Args:
        options: Lista de opciones
        correct_option_idx: Índice original de la opción correcta

    Returns:
        tuple: (opciones_desordenadas, nuevo_índice_correcto)
    """
    if not options or correct_option_idx >= len(options):
        return options, correct_option_idx

    # Generar una permutación completamente aleatoria de índices
    shuffled_indices = random.sample(range(len(options)), len(options))

    # Construir las opciones desordenadas y encontrar el nuevo índice de la correcta
    shuffled_options = [options[i] for i in shuffled_indices]
    new_correct_idx = shuffled_indices.index(correct_option_idx)

    return shuffled_options, new_correct_idx


@celery_app.task(name="tasks.best_options.refill_queue")
def refill_best_options_queue_task(user_id: int):
    """
    Tarea Celery para rellenar la cola de best_options de un usuario en segundo plano.
    - Busca 8 palabras que el usuario ya ha visto
    - Genera 8 ejercicios de best_options usando IA
    - Guarda los ejercicios en la cola sin vaciar registros previos
    """
    logger.info(f"[Celery BestOptions] Starting best options queue refill for user {user_id}...")

    try:
        with Session(engine) as db:
            # Marcar el refill como iniciado
            crud.start_queue_refill(db, user_id, QueueType.BEST_OPTION)

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

                if not questions or not word_id:
                    continue

                # Por cada pregunta, crear un BestOption
                # Los 4 ejercicios se guardan con sequence_order 1, 2, 3, 4
                best_option_ids = []
                for sequence_idx, question_data in enumerate(questions, start=1):
                    question_text = question_data.get("question")
                    options = question_data.get("options", [])
                    correct_option_idx = question_data.get("correct_option", 0)

                    if not question_text or not options:
                        continue

                    # Desordena las opciones para evitar sesgo hacia la posición 0
                    shuffled_options, new_correct_idx = shuffle_options_with_correct_index(
                        options, correct_option_idx
                    )

                    # Crear la cadena de opciones separadas por ";"
                    options_string = ";".join(shuffled_options)

                    # Crear el BestOption en DB con word_id y sequence_order
                    best_option = BestOption(
                        word_id=word_id,
                        sequence_order=sequence_idx,
                        question=question_text,
                        options=options_string,
                        correct_option=new_correct_idx
                    )
                    db.add(best_option)
                    db.flush()  # Generar el ID del BestOption
                    best_option_ids.append(best_option.id)

                # Encolar solo el PRIMER ejercicio (sequence_order = 1) para esta palabra
                if best_option_ids:
                    first_best_option_id = best_option_ids[0]

                    # Verificar que no esté ya en la cola del usuario
                    existing_queue = db.exec(
                        select(BestOptionQueue).where(
                            BestOptionQueue.user_id == user_id,
                            BestOptionQueue.best_option_id == first_best_option_id
                        )
                    ).first()

                    if not existing_queue:
                        # Agregar solo el primero a la cola con estado PENDING
                        queue_item = BestOptionQueue(
                            user_id=user_id,
                            best_option_id=first_best_option_id,
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
    finally:
        # Marcar el refill como completado (ya sea con éxito o error)
        # Usar una sesión nueva para asegurar que se ejecute
        with Session(engine) as db:
            crud.end_queue_refill(db, user_id, QueueType.BEST_OPTION)