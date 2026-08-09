from typing import List
from sqlmodel import Session, select, func
from logging_client import logger
from celery_app import celery_app

import ai
from examples import repository as ExampleRepository
from models import Example, ExampleWord, ExampleType, Word, ExploreConfiguration


def _get_explore_configuration(db: Session, user_id: int) -> dict:
    """
    Obtiene la configuración de exploración basada en el total de ejemplos del usuario.
    """
    total_examples = db.exec(
        select(func.count())
        .select_from(Example)
        .join(Example.example_words)
        .join(ExampleWord.word)
        .where(
            Word.user_id == user_id,
            Example.is_active == True,
            Example.type == ExampleType.EXPLORE
        )
    ).one() or 0

    config = db.exec(
        select(ExploreConfiguration)
        .where(ExploreConfiguration.max_examples >= total_examples)
        .order_by(ExploreConfiguration.max_examples.asc())
    ).first()

    if not config:
        return {
            "ai_mixed_generation_amount": 6,
            "ai_simple_generation_amount": 6,
            "recycled_words_amount": 2
        }

    return {
        "ai_mixed_generation_amount": config.ai_mixed_generation_amount,
        "ai_simple_generation_amount": config.ai_simple_generation_amount,
        "recycled_words_amount": config.recycled_words_amount
    }


@celery_app.task(name="tasks.examples.generate")
def generate(user_id: int, word_ids: List[int]) -> None:
    """
    Genera ejemplos de uso para una lista de palabras usando IA.

    Args:
        user_id: ID del usuario
        word_ids: Lista de IDs de palabras
    """
    from db import engine

    if not word_ids:
        logger.warning(f"[ExampleGenerator] No words provided for user {user_id}")
        return

    logger.info(f"[ExampleGenerator] Starting example generation for {len(word_ids)} words (user {user_id})")

    try:
        # Crear nueva sesión para la tarea
        with Session(engine) as db:
            # Cargar palabras por sus IDs
            words = db.exec(
                select(Word).where(Word.id.in_(word_ids), Word.user_id == user_id)
            ).all()

            if not words:
                logger.warning(f"[ExampleGenerator] Words not found for user {user_id}")
                return

            # Obtener configuración
            config = _get_explore_configuration(db, user_id)
            ai_simple_amount = config.get("ai_simple_generation_amount", 0)
            ai_mixed_amount = config.get("ai_mixed_generation_amount", 0)

            if ai_simple_amount == 0 and ai_mixed_amount == 0:
                logger.info(f"[ExampleGenerator] No examples to generate for user {user_id} (config amounts = 0)")
                return

            total_ai_required = ai_simple_amount + ai_mixed_amount
            logger.info(f"[ExampleGenerator] Config: simple={ai_simple_amount}, mixed={ai_mixed_amount} (total={total_ai_required})")

            all_generated = []

            # 1. Generar ejemplos simples
            if ai_simple_amount > 0:
                simple_words = words[:ai_simple_amount]
                logger.info(f"[ExampleGenerator] Generating {ai_simple_amount} simple examples")

                raw_simple = ai.generate_examples_from_words(simple_words)
                if raw_simple:
                    simple_examples = ExampleRepository.create(
                        db,
                        raw_simple[:ai_simple_amount],
                        example_type=ExampleType.EXPLORE
                    )
                    all_generated.extend(simple_examples)
                    logger.info(f"[ExampleGenerator] Created {len(simple_examples)} simple examples")

            # 2. Generar ejemplos mixtos
            if ai_mixed_amount > 0:
                # Usar diferentes palabras para mixed
                mixed_words = words[ai_simple_amount:ai_simple_amount + ai_mixed_amount]
                if not mixed_words and len(words) > ai_simple_amount:
                    mixed_words = words[ai_simple_amount:]

                if mixed_words:
                    logger.info(f"[ExampleGenerator] Generating {ai_mixed_amount} mixed examples")

                    raw_mixed = ai.generate_mixed_examples_from_words(mixed_words)
                    if raw_mixed:
                        mixed_examples = ExampleRepository.create(
                            db,
                            raw_mixed[:ai_mixed_amount],
                            example_type=ExampleType.EXPLORE
                        )
                        all_generated.extend(mixed_examples)
                        logger.info(f"[ExampleGenerator] Created {len(mixed_examples)} mixed examples")

            logger.info(f"[ExampleGenerator] Successfully generated {len(all_generated)} total examples for user {user_id}")

    except Exception as e:
        logger.error(
            f"[ExampleGenerator] Error generating examples for user {user_id}: {e}",
            exc_info=True
        )
