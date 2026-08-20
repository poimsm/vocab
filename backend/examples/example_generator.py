from typing import List
from sqlmodel import Session, select
from logging_client import logger
from celery_app import celery_app
from sqlalchemy.exc import IntegrityError
import ai
from examples.helpers import approximate_text_form
from examples.example_repository import ExampleRepository


@celery_app.task(name="tasks.examples.generate_simple")
def generate_simple_examples_task(
    user_id: int,
    word_ids: List[int],
    amount: int = 1,
    pre_generated_examples: dict = None,
) -> None:
    """
    Genera examples simples, donde cada example está asociado
    principalmente a una sola word.

    Puede usar ejemplos pre-generados (del enriquecimiento) o generar nuevos.

    Si pre_generated_examples viene con formato {word_id: [example_texts]},
    usa esos ejemplos. De los 10 ejemplos: primeros 3 son INITIAL, resto EXPLORE.

    Si no viene, genera ejemplos nuevos con ai.generate_examples_for_single_word().
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
            successfully_created = 0

            # Generar ejemplos para cada palabra
            example_repo = ExampleRepository(db)
            for word in words:
                try:
                    # Verificar cuántos ejemplos disponibles hay para esta palabra
                    available_count = example_repo.count_available_examples_for_word(word.id)

                    # Si hay suficientes ejemplos disponibles, no generar
                    if available_count >= 3:
                        logger.info(
                            f"[ExampleGenerator] Word {word.id} already has {available_count} available examples, skipping generation"
                        )
                        continue

                    # Intentar obtener ejemplos pre-generados (del enriquecimiento)
                    is_pre_generated = False
                    if pre_generated_examples and str(word.id) in pre_generated_examples:
                        raw_examples = pre_generated_examples[str(word.id)]
                        is_pre_generated = True
                        logger.debug(f"[ExampleGenerator] Using pre-generated examples for word {word.id}")
                    else:
                        # Generar nuevos ejemplos con IA solo si hace falta
                        logger.info(
                            f"[ExampleGenerator] Word {word.id} has only {available_count} available examples, generating new ones..."
                        )
                        raw_examples = ai.generate_examples_for_single_word(word, amount, db)
                        logger.debug(f"[ExampleGenerator] Generated new examples for word {word.id}")

                    if not raw_examples:
                        logger.warning(
                            f"[ExampleGenerator] No examples available for word {word.id}"
                        )
                        continue

                    # Deduplicar ejemplos por normalized (evitar IntegrityError)
                    seen_normalized = set()
                    filtered_examples = []
                    for idx, example_text in enumerate(raw_examples):
                        normalized = example_text.lower().strip()
                        if normalized and normalized not in seen_normalized:
                            seen_normalized.add(normalized)
                            filtered_examples.append((idx, example_text))

                    # Verificar cuáles normalizados ya existen en BD
                    existing_normalized = set(
                        db.exec(
                            select(Example.normalized)
                            .where(Example.normalized.in_(list(seen_normalized)))
                        ).all()
                    )

                    # Asignar tipos:
                    # - Si son pre-generados: primeros 3 INITIAL, resto EXPLORE
                    # - Si son generados por IA: todos EXPLORE
                    word_examples_count = 0
                    for idx, example_text in filtered_examples:
                        normalized = example_text.lower().strip()

                        # Saltar si ya existe en BD
                        if normalized in existing_normalized:
                            logger.debug(
                                f"[ExampleGenerator] Example already in DB for word {word.id} "
                                f"(normalized: '{normalized}'), skipping..."
                            )
                            continue

                        try:
                            if is_pre_generated and idx < 3:
                                example_type = ExampleType.INITIAL
                            else:
                                example_type = ExampleType.EXPLORE

                            # Crear el Example con sequence
                            example = Example(
                                type=example_type,
                                text=example_text,
                                normalized=normalized,
                                sequence=sequence_counter,
                                enqueued=False,
                            )
                            db.add(example)
                            db.flush()

                            # Crear relación con la palabra
                            # Usar el word.main como text_form y aproximar si es necesario
                            text_form = approximate_text_form(example_text, word.main)
                            if not text_form:
                                text_form = word.main

                            example_word = ExampleWord(
                                example_id=example.id,
                                word_id=word.id,
                                text_form=text_form,
                            )
                            db.add(example_word)
                            db.commit()
                            word_examples_count += 1
                            sequence_counter += 1

                        except Exception as e:
                            logger.error(
                                f"[ExampleGenerator] Error creating example for word {word.id}: {e}",
                                exc_info=True,
                            )
                            db.rollback()
                            continue

                    if word_examples_count > 0:
                        successfully_created += word_examples_count
                        logger.debug(f"[ExampleGenerator] Created {word_examples_count} examples for word {word.id}")

                except Exception as e:
                    logger.error(
                        f"[ExampleGenerator] Error generating examples for word {word.id}: {e}",
                        exc_info=True,
                    )
                    db.rollback()  # Limpiar sesión en error outer también
                    continue

            logger.info(
                f"[ExampleGenerator] Successfully created {successfully_created} examples for user {user_id}"
            )

    except Exception as e:
        logger.error(
            f"[ExampleGenerator] Error generating simple examples for user {user_id}: {e}",
            exc_info=True,
        )
        db.rollback()


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
            successfully_created = 0

            # Deduplicar ejemplos por normalized antes de procesar
            seen_normalized = set()
            filtered_examples = []
            for example_data in raw_mixed_examples:
                example_text = example_data.get("text", "").strip()
                if example_text:
                    normalized = example_text.lower()
                    if normalized not in seen_normalized:
                        seen_normalized.add(normalized)
                        filtered_examples.append(example_data)

            # Verificar cuáles normalizados ya existen en BD
            existing_normalized = set(
                db.exec(
                    select(Example.normalized)
                    .where(Example.normalized.in_(list(seen_normalized)))
                ).all()
            )

            for example_data in filtered_examples:
                example_text = example_data.get("text", "").strip()
                normalized = example_text.lower()

                if not example_text:
                    logger.warning(
                        f"[MixedExampleGenerator] No text in example data"
                    )
                    continue

                # Saltar si ya existe en BD
                if normalized in existing_normalized:
                    logger.debug(
                        f"[MixedExampleGenerator] Example already in DB "
                        f"(normalized: '{normalized}'), skipping..."
                    )
                    continue

                try:
                    words_data = example_data.get("words", [])

                    # Crear el Example con sequence
                    example = Example(
                        type=ExampleType.EXPLORE,
                        text=example_text,
                        normalized=normalized,
                        sequence=sequence_counter,
                        enqueued=False,
                    )
                    db.add(example)
                    db.flush()

                    # Crear relaciones con todas las palabras asociadas
                    # La IA devuelve: [{"word_id": 1, "text_form": "hustled"}, ...]
                    for word_info in words_data:
                        word_id = word_info.get("word_id")
                        suggested_text_form = word_info.get("text_form", "")

                        word = db.get(Word, word_id)
                        if word:
                            # Aproximar el text_form si está vacío o no coincide
                            text_form = approximate_text_form(
                                example_text,
                                suggested_text_form
                            )
                            if not text_form:
                                text_form = word.main

                            example_word = ExampleWord(
                                example_id=example.id,
                                word_id=word_id,
                                text_form=text_form,
                            )
                            db.add(example_word)

                    db.commit()
                    successfully_created += 1
                    sequence_counter += 1

                except Exception as e:
                    logger.error(
                        f"[MixedExampleGenerator] Error creating example: {e}",
                        exc_info=True,
                    )
                    db.rollback()
                    continue

            logger.info(
                f"[MixedExampleGenerator] Successfully created {successfully_created} mixed examples for user {user_id}"
            )

    except Exception as e:
        logger.error(
            f"[MixedExampleGenerator] Error generating mixed examples for user {user_id}: {e}",
            exc_info=True,
        )


class ExampleGenerator:
    """Wrapper para llamar a tasks de generación de ejemplos desde ContentPlanner"""

    @staticmethod
    def generate_simple(user_id: int, word_ids: List[int], amount: int = 1, pre_generated_examples: dict = None):
        """Solicita generación de ejemplos simples (con o sin ejemplos pre-generados)"""
        return generate_simple_examples_task.delay(user_id, word_ids, amount, pre_generated_examples)

    @staticmethod
    def generate_mixed(user_id: int, word_ids: List[int], amount: int):
        """Solicita generación de ejemplos mixtos"""
        return generate_mixed_examples_task.delay(user_id, word_ids, amount)
