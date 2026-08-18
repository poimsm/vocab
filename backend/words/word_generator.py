from typing import List
from sqlmodel import Session, select
from logging_client import logger
from celery_app import celery_app
import ai
from datetime import datetime, timezone
import time
from sqlalchemy.exc import IntegrityError


@celery_app.task(name="tasks.words.create_single")
def create_single_task(
    user_id: int,
    text: str,
) -> None:
    """
    Crea una palabra individual desde texto libre.

    Flujo:
    1. Usar ai.extract_learning_intent(text) para obtener main, meaning, etc.
    2. Crear Word en BD
    3. Generar examples automáticamente
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

    from db import engine
    from models import Word, WordStatistics, LearningState, ContentType, WordLevel
    from words.word_repository import WordRepository

    if not text or not text.strip():
        logger.warning(f"[WordGenerator] Empty text for user {user_id}")
        return

    logger.info(f"[WordGenerator] Creating single word from text for user {user_id}")

    try:
        # Extraer información de la palabra del texto
        extracted = ai.extract_learning_intent([text])

        if not extracted or len(extracted) == 0:
            logger.warning(f"[WordGenerator] Could not extract word data from text for user {user_id}")
            return

        # Obtener la palabra principal extraída
        main_word = extracted[0].get("main")
        word_type = extracted[0].get("type", "word")

        if not main_word:
            logger.warning(f"[WordGenerator] No main word extracted for user {user_id}")
            return

        # Enriquecer la palabra con detalles completos
        enriched = ai.enrich_word(main_word)

        if not enriched:
            logger.warning(f"[WordGenerator] Could not enrich word {main_word} for user {user_id}")
            return

        # Crear sesión
        with Session(engine) as db:
            word_repo = WordRepository(db)

            # Crear palabra
            word = word_repo.create(user_id, {
                "main": main_word,
                "meaning": enriched.get("meaning"),
                "synonyms": enriched.get("synonyms"),
                "type": word_type,
                "frequency": enriched.get("frequency"),
                "level": WordLevel.to_int(enriched.get("level")),
                "context": enriched.get("category"),
                "source_text": text,
            })

            logger.debug(f"[WordGenerator] Word {word.id} created for user {user_id}")

            # Crear estadísticas iniciales para ambos tipos de contenido
            for content_type in [ContentType.EXAMPLE, ContentType.BEST_OPTIONS]:
                stats = WordStatistics(
                    word_id=word.id,
                    type=content_type,
                    learning_state=LearningState.NEW,
                    times_seen=0,
                    current_cycle_seen=0,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(stats)

            db.commit()

            # Trigger de generación de ejemplos en background
            from examples.example_generator import ExampleGenerator
            from best_options.best_options_generator import BestOptionGenerator

            # Pasar ejemplos pre-generados del enriquecimiento (10 ejemplos)
            pre_generated_examples = {}
            if enriched.get("examples"):
                pre_generated_examples[str(word.id)] = enriched["examples"]

            ExampleGenerator.generate_simple(
                user_id=user_id,
                word_ids=[word.id],
                amount=2,  # Fallback si no hay pre-generated
                pre_generated_examples=pre_generated_examples,
            )

            BestOptionGenerator.generate(
                user_id=user_id,
                word_ids=[word.id],
            )

            logger.info(f"[WordGenerator] Successfully created word {word.id} for user {user_id}")

    except Exception as e:
        logger.error(
            f"[WordGenerator] Error creating word for user {user_id}: {e}",
            exc_info=True
        )


@celery_app.task(name="tasks.words.create_bulk")
def create_bulk_task(
    user_id: int,
    texts: List[str],
) -> None:
    """
    Crea múltiples palabras desde una lista de textos.

    Procesa sequencialmente:
    1. Usar ai.extract_learning_intent() para cada texto
    2. Crear Words en BD
    3. Trigger generación de ejemplos

    La generación de ejemplos se hace en background para no bloquear.
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

    from db import engine
    from models import Word, WordStatistics, LearningState, ContentType, WordLevel
    from words.word_repository import WordRepository

    if not texts:
        logger.warning(f"[BulkWordGenerator] No texts provided for user {user_id}")
        return

    logger.info(f"[BulkWordGenerator] Creating {len(texts)} words for user {user_id}")

    try:
        with Session(engine) as db:
            word_repo = WordRepository(db)
            created_words = []
            created_word_ids = []

            # Procesar en chunks de 15 textos
            chunk_size = 15
            total_items = len(texts)

            for chunk_idx in range(0, total_items, chunk_size):
                chunk_texts = texts[chunk_idx:chunk_idx + chunk_size]
                chunk_num = (chunk_idx // chunk_size) + 1
                total_chunks = (total_items + chunk_size - 1) // chunk_size
                start_idx = chunk_idx + 1

                logger.info(f"[BulkWordGenerator] Processing chunk {chunk_num}/{total_chunks} ({len(chunk_texts)} items)")

                try:
                    # Paso 1: Extraer información de los textos del chunk
                    extracted_items = []  # Lista de (idx, text, main_word, word_type)
                    for offset, text in enumerate(chunk_texts):
                        try:
                            idx = start_idx + offset

                            if not text or not text.strip():
                                logger.warning(f"[BulkWordGenerator] Skipping empty text (item {idx})")
                                continue

                            # Extraer información de la palabra
                            extracted = ai.extract_learning_intent([text])

                            if not extracted or len(extracted) == 0:
                                logger.warning(f"[BulkWordGenerator] Could not extract word data from text (item {idx})")
                                continue

                            # Obtener la palabra principal extraída
                            main_word = extracted[0].get("main")
                            word_type = extracted[0].get("type", "word")

                            if not main_word:
                                logger.warning(f"[BulkWordGenerator] No main word extracted (item {idx})")
                                continue

                            extracted_items.append((idx, text, main_word, word_type))

                        except Exception as e:
                            logger.error(
                                f"[BulkWordGenerator] Error extracting text item {start_idx + offset}: {e}",
                                exc_info=True
                            )
                            continue

                    if not extracted_items:
                        logger.warning(f"[BulkWordGenerator] No valid words extracted in chunk {chunk_num}")
                        continue

                    # Paso 2: Enriquecer palabras del chunk en lote
                    main_words = [item[2] for item in extracted_items]
                    enriched_list = ai.enrich_words_bulk(main_words)

                    if not enriched_list:
                        logger.warning(f"[BulkWordGenerator] Could not enrich words in chunk {chunk_num}")
                        continue

                    # Crear un mapa de palabra -> datos enriquecidos
                    enriched_map = {item["word"]: item for item in enriched_list}
                    # Mapa de palabra -> ejemplos pre-generados (10 ejemplos del enriquecimiento)
                    pre_generated_examples = {}
                    chunk_word_ids = []
                    chunk_word_id_to_main = {}  # Para mapping word_id -> main_word

                    # Paso 3: Crear palabras en BD usando datos enriquecidos
                    for idx, text, main_word, word_type in extracted_items:
                        try:
                            enriched = enriched_map.get(main_word)

                            if not enriched:
                                logger.warning(f"[BulkWordGenerator] No enriched data for word {main_word} (item {idx})")
                                continue

                            # Crear palabra
                            word = word_repo.create(user_id, {
                                "main": main_word,
                                "meaning": enriched.get("meaning"),
                                "synonyms": enriched.get("synonyms"),
                                "type": word_type,
                                "frequency": enriched.get("frequency"),
                                "level": WordLevel.to_int(enriched.get("level")),
                                "context": enriched.get("category"),
                                "source_text": text,
                            })

                            logger.debug(f"[BulkWordGenerator] Word {word.id} created (item {idx})")
                            created_words.append(word)
                            created_word_ids.append(word.id)
                            chunk_word_ids.append(word.id)
                            chunk_word_id_to_main[word.id] = main_word

                            # Guardar ejemplos pre-generados del enriquecimiento (10 ejemplos)
                            if enriched.get("examples"):
                                pre_generated_examples[str(word.id)] = enriched["examples"]

                            # Crear estadísticas iniciales
                            for content_type in [ContentType.EXAMPLE, ContentType.BEST_OPTIONS]:
                                stats = WordStatistics(
                                    word_id=word.id,
                                    type=content_type,
                                    learning_state=LearningState.NEW,
                                    times_seen=0,
                                    current_cycle_seen=0,
                                    created_at=datetime.now(timezone.utc),
                                )
                                db.add(stats)

                            db.commit()

                        except IntegrityError as e:
                            # Word already exists, skip it and continue
                            logger.warning(
                                f"[BulkWordGenerator] Word already exists (item {idx}: {main_word}), skipping..."
                            )
                            db.rollback()
                            continue
                        except Exception as e:
                            logger.error(
                                f"[BulkWordGenerator] Error creating word for item {idx}: {e}",
                                exc_info=True
                            )
                            db.rollback()
                            continue

                    # Paso 4: Generar contenido para el chunk
                    if chunk_word_ids:
                        from examples.example_generator import ExampleGenerator
                        from best_options.best_options_generator import BestOptionGenerator

                        ExampleGenerator.generate_simple(
                            user_id=user_id,
                            word_ids=chunk_word_ids,
                            amount=1,  # Fallback si no hay pre-generated
                            pre_generated_examples=pre_generated_examples,
                        )

                        BestOptionGenerator.generate(
                            user_id=user_id,
                            word_ids=chunk_word_ids,
                        )

                        logger.debug(f"[BulkWordGenerator] Generated content for chunk {chunk_num} ({len(chunk_word_ids)} words)")

                except Exception as e:
                    logger.error(
                        f"[BulkWordGenerator] Error processing chunk {chunk_num}: {e}",
                        exc_info=True
                    )
                    continue

                # Sleep entre chunks (excepto el último)
                if chunk_idx + chunk_size < total_items:
                    time.sleep(1)

            if created_word_ids:
                logger.info(f"[BulkWordGenerator] Successfully created {len(created_words)} words for user {user_id}")
            else:
                logger.warning(f"[BulkWordGenerator] No words were created for user {user_id}")

    except Exception as e:
        logger.error(
            f"[BulkWordGenerator] Error creating bulk words for user {user_id}: {e}",
            exc_info=True
        )


class WordGenerator:
    """Wrapper para llamar a tasks de generación de palabras"""

    @staticmethod
    def create_single(user_id: int, text: str):
        """Solicita creación de palabra individual"""
        return create_single_task.delay(user_id, text)

    @staticmethod
    def create_bulk(user_id: int, texts: List[str]):
        """Solicita creación de múltiples palabras"""
        return create_bulk_task.delay(user_id, texts)
