from typing import List
from sqlmodel import Session, select
from logging_client import logger
from celery_app import celery_app
import ai


@celery_app.task(name="tasks.examples.generate_simple")
def generate_simple_examples_task(
    user_id: int,
    word_ids: List[int],
    amount: int = 1,
) -> None:
    """
    Genera examples simples, donde cada example está asociado
    principalmente a una sola word.

    Obtiene las words, solicita a la AI la cantidad indicada y
    persiste los examples junto con sus relaciones ExampleWord.

    Usar ai.generate_examples_for_single_word(word, amount)
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

    from db import engine
    from models import Word, Example, ExampleWord, ExampleType

    if not word_ids:
        logger.warning(f"[ExampleGenerator] No words provided for user {user_id}")
        return

    logger.info(
        f"[ExampleGenerator] Generating simple examples for {len(word_ids)} words (user {user_id})"
    )

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

            # Obtener el máximo sequence actual para continuar secuencia
            from sqlalchemy import func as sql_func
            max_sequence = db.exec(
                select(sql_func.max(Example.sequence))
            ).first() or 0

            sequence_counter = max_sequence + 1

            # Generar ejemplos usando IA para cada palabra
            for word in words:
                try:
                    raw_examples = ai.generate_examples_for_single_word(word, amount)

                    if not raw_examples:
                        logger.warning(
                            f"[ExampleGenerator] No examples generated for word {word.id}"
                        )
                        continue

                    for example_text in raw_examples:
                        # Crear el Example con sequence
                        example = Example(
                            type=ExampleType.EXPLORE,
                            text=example_text,
                            normalized=example_text.lower(),
                            sequence=sequence_counter,
                            enqueued=False,
                        )
                        db.add(example)
                        db.flush()

                        # Crear relación con la palabra
                        example_word = ExampleWord(
                            example_id=example.id,
                            word_id=word.id,
                            text_form=word.main,
                        )
                        db.add(example_word)

                        sequence_counter += 1

                except Exception as e:
                    logger.error(
                        f"[ExampleGenerator] Error generating examples for word {word.id}: {e}",
                        exc_info=True,
                    )
                    continue

            db.commit()
            logger.info(
                f"[ExampleGenerator] Successfully created simple examples for user {user_id}"
            )

    except Exception as e:
        logger.error(
            f"[ExampleGenerator] Error generating simple examples for user {user_id}: {e}",
            exc_info=True,
        )


@celery_app.task(name="tasks.examples.generate_mixed")
def generate_mixed_examples_task(
    user_id: int,
    word_ids: List[int],
    amount: int,
) -> None:
    """
    Genera examples mixed a partir de un grupo de words.

    La AI decide qué combinación de words utilizar en cada example.
    El task persiste cada example y todas las relaciones ExampleWord
    devueltas por la AI.

    Usar ai.generate_mixed_examples_from_words(words)
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

    from db import engine
    from models import Word, Example, ExampleWord, ExampleType

    if not word_ids or amount <= 0:
        logger.warning(f"[MixedExampleGenerator] Invalid params for user {user_id}")
        return

    logger.info(
        f"[MixedExampleGenerator] Generating mixed examples for {len(word_ids)} words (user {user_id})"
    )

    try:
        # Crear nueva sesión para la tarea
        with Session(engine) as db:
            # Cargar palabras por sus IDs
            words = db.exec(
                select(Word).where(Word.id.in_(word_ids), Word.user_id == user_id)
            ).all()

            if not words or len(words) < 2:
                logger.warning(
                    f"[MixedExampleGenerator] Not enough words for mixed examples (user {user_id})"
                )
                return

            # Generar ejemplos mixtos usando IA
            raw_mixed_examples = ai.generate_mixed_examples_from_words(words, amount)

            if not raw_mixed_examples:
                logger.warning(
                    f"[MixedExampleGenerator] No mixed examples generated (user {user_id})"
                )
                return

            # Obtener el máximo sequence actual para continuar secuencia
            from sqlalchemy import func as sql_func
            max_sequence = db.exec(
                select(sql_func.max(Example.sequence))
            ).first() or 0

            sequence_counter = max_sequence + 1

            for example_data in raw_mixed_examples:
                try:
                    example_text = example_data.get("text")
                    associated_word_ids = example_data.get("word_ids", [])

                    if not example_text:
                        logger.warning(
                            f"[MixedExampleGenerator] No text in example data"
                        )
                        continue

                    # Crear el Example con sequence
                    example = Example(
                        type=ExampleType.EXPLORE,
                        text=example_text,
                        normalized=example_text.lower(),
                        sequence=sequence_counter,
                        enqueued=False,
                    )
                    db.add(example)
                    db.flush()

                    # Crear relaciones con todas las palabras asociadas
                    for word_id in associated_word_ids:
                        word = db.get(Word, word_id)
                        if word:
                            example_word = ExampleWord(
                                example_id=example.id,
                                word_id=word_id,
                                text_form=word.main,
                            )
                            db.add(example_word)

                    sequence_counter += 1

                except Exception as e:
                    logger.error(
                        f"[MixedExampleGenerator] Error processing example: {e}",
                        exc_info=True,
                    )
                    continue

            db.commit()
            logger.info(
                f"[MixedExampleGenerator] Successfully created mixed examples for user {user_id}"
            )

    except Exception as e:
        logger.error(
            f"[MixedExampleGenerator] Error generating mixed examples for user {user_id}: {e}",
            exc_info=True,
        )


class ExampleGenerator:
    """Wrapper para llamar a tasks de generación de ejemplos desde ContentPlanner"""

    @staticmethod
    def generate_simple(user_id: int, word_ids: List[int], amount: int = 1):
        """Solicita generación de ejemplos simples"""
        return generate_simple_examples_task.delay(user_id, word_ids, amount)

    @staticmethod
    def generate_mixed(user_id: int, word_ids: List[int], amount: int):
        """Solicita generación de ejemplos mixtos"""
        return generate_mixed_examples_task.delay(user_id, word_ids, amount)
