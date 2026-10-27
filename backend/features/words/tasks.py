"""
Tareas Celery para generación de palabras.

Celery autodiscover busca módulos llamados 'tasks.py'.
Las funciones decoradas con @celery_app.task() se registran automáticamente.
"""

from typing import List
from sqlmodel import Session, select
from logging_client import logger
from celery_app import celery_app
from core.celery_queues import CeleryQueue
import ai
from datetime import datetime, timezone
import time
from sqlalchemy.exc import IntegrityError
from features.examples.helpers import approximate_text_form
from config import UserProfileManager


@celery_app.task(name="tasks.words.create_single", queue=CeleryQueue.AI)
def create_single_task(
    user_id: int,
    text: str,
    target_word: str = None,
) -> None:
    """
    Crea una palabra individual desde texto libre.

    Flujo:
    1. Usar ai.extract_learning_intent(text) para obtener main, meaning, etc.
    2. Si target_word está presente, procesar con ai.target_meaning()
    3. Crear Word en BD
    4. Generar examples automáticamente
    """
    from db import engine
    from features.words.models import Word, WordStatistics, WordLevel
    from core.enums import ContentType
    from core.learning_path.models import LearningState
    from features.words.repository import WordRepository

    if not text or not text.strip():
        logger.warning(f"[WordGenerator] Empty text for user {user_id}")
        return

    logger.info(f"[WordGenerator] Creating single word from text for user {user_id}")

    try:
        # Determine main_word: use target_word if provided, otherwise extract from text
        main_word = None
        word_type = "word"

        if target_word:
            # When target is provided, use it directly as main_word
            main_word = target_word.strip()
            logger.info(f"[WordGenerator] Using target_word as main: {main_word}")
        else:
            # Extract main_word from text
            extracted = ai.extract_learning_intent([text])

            if not extracted or len(extracted) == 0:
                logger.warning(f"[WordGenerator] Could not extract word data from text for user {user_id}")
                return

            main_word = extracted[0].get("main")
            word_type = extracted[0].get("type", "word")

        if not main_word:
            logger.warning(f"[WordGenerator] No main word determined for user {user_id}")
            return

        # Crear sesión
        with Session(engine) as db:
            word_repo = WordRepository(db)

            # Verificar si la palabra ya existe (solo si está activa)
            existing_word = db.exec(
                select(Word)
                .where(
                    Word.user_id == user_id,
                    Word.main == main_word,
                    Word.is_active == True
                )
            ).first()

            if existing_word:
                logger.info(f"[WordGenerator] Word '{main_word}' already exists and is active for user {user_id}, skipping")
                return

            # Enriquecer la palabra con detalles completos
            enriched = ai.enrich_word(main_word)

            if not enriched:
                logger.warning(f"[WordGenerator] Could not enrich word {main_word} for user {user_id}")
                return

            # Procesar target si está presente
            target_synonym = None
            target_explanation = None
            if target_word:
                try:
                    logger.info(f"[WordGenerator] Processing target '{target_word}' for user {user_id}")
                    target_result = ai.target_meaning(text, target_word)
                    if target_result:
                        target_synonym = target_result.get("synonym")
                        target_explanation = target_result.get("explanation")
                        logger.debug(f"[WordGenerator] Target info retrieved: synonym={target_synonym}")
                except Exception as e:
                    logger.error(f"[WordGenerator] Error processing target meaning: {e}", exc_info=True)

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
                "target_word": target_word,
                "target_synonym": target_synonym,
                "target_explanation": target_explanation,
            })

            logger.debug(f"[WordGenerator] Word {word.id} created for user {user_id}")

            # Crear ejemplos pre-generados directamente en BD (10 ejemplos)
            if enriched.get("examples"):
                from features.examples.models import Example, ExampleType
                from core.learning_path.models import LearningPathQueue
                from core.learning_path.enums import LearningPathQueueStatus

                examples_list = enriched["examples"]
                sequence_counter = 1
                created_examples = []

                for idx, example_text in enumerate(examples_list):
                    normalized = example_text.lower().strip()

                    # Primeros 3 son INITIAL, resto EXPLORE
                    example_type = ExampleType.INITIAL if idx < 3 else ExampleType.EXPLORE

                    text_form = approximate_text_form(example_text, main_word)
                    if not text_form:
                        text_form = main_word

                    # Crear el Example con word_id y text_form
                    example = Example(
                        type=example_type,
                        text=example_text,
                        text_form=text_form,
                        word_id=word.id,
                        normalized=normalized,
                        sequence=sequence_counter,
                        enqueued=False,
                    )
                    db.add(example)
                    db.flush()
                    created_examples.append(example.id)
                    sequence_counter += 1

                logger.debug(f"[WordGenerator] Created {len(examples_list)} examples for word {word.id}")

                # ✅ Agregar ejemplos a LearningPathQueue para que estén disponibles inmediatamente
                for example_id in created_examples:
                    queue_item = LearningPathQueue(
                        user_id=user_id,
                        content_type=ContentType.EXAMPLE,
                        content_id=example_id,
                        word_id=word.id,
                        status=LearningPathQueueStatus.PENDING,
                        priority=0.5,
                    )
                    db.add(queue_item)
                db.commit()
                logger.debug(f"[WordGenerator] Added {len(examples_list)} examples to LearningPathQueue for word {word.id}")

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

            # ✅ Contar palabra creada en perfil de usuario
            UserProfileManager.increment_words(db, user_id)

            # ✅ Contar ejemplos creados
            if enriched.get("examples"):
                examples_count = len(enriched["examples"])
                UserProfileManager.increment_examples(db, user_id, amount=examples_count)
                logger.debug(f"[WordGenerator] Counted {examples_count} examples for user {user_id}")

            # Trigger de generación de best options en background
            from features.best_options.generator import BestOptionGenerator

            BestOptionGenerator.generate(
                user_id=user_id,
                word_ids=[word.id],
            )

            logger.info(f"[WordGenerator] Successfully created word {word.id} for user {user_id}")

            # ✅ Publicar evento SSE de completación
            try:
                from core.realtime_event_bus import get_realtime_bus
                event_bus = get_realtime_bus()
                event_bus.publish(
                    f"user:{user_id}:words_create.completed",
                    {
                        "word_id": word.id,
                        "word": word.main,
                        "meaning": word.meaning,
                        "status": "ok"
                    }
                )
                logger.debug(f"[WordGenerator] Event published: words_create.completed for word {word.id}")
            except Exception as e:
                logger.error(f"[WordGenerator] Error publishing completion event: {e}")

    except Exception as e:
        logger.error(
            f"[WordGenerator] Error creating word for user {user_id}: {e}",
            exc_info=True
        )

        # ✅ Publicar evento SSE de error
        try:
            from core.realtime_event_bus import get_realtime_bus
            event_bus = get_realtime_bus()
            event_bus.publish(
                f"user:{user_id}:words_create.failed",
                {
                    "status": "error",
                    "message": str(e)
                }
            )
            logger.debug(f"[WordGenerator] Event published: words_create.failed")
        except Exception as pub_error:
            logger.error(f"[WordGenerator] Error publishing error event: {pub_error}")


@celery_app.task(name="tasks.words.create_bulk", queue=CeleryQueue.AI)
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
    from db import engine
    from features.words.models import Word, WordStatistics, WordLevel
    from core.enums import ContentType
    from core.learning_path.models import LearningState
    from features.words.repository import WordRepository

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

                    # Paso 1.5: Verificar cuáles palabras ya existen en BD
                    main_words_all = [item[2] for item in extracted_items]
                    existing_words = db.exec(
                        select(Word.main)
                        .where(
                            Word.user_id == user_id,
                            Word.main.in_(main_words_all)
                        )
                    ).all()
                    existing_words_set = set(existing_words)

                    # Filtrar solo palabras nuevas (que no existen)
                    new_extracted_items = []
                    for item in extracted_items:
                        idx, text, main_word, word_type = item
                        if main_word in existing_words_set:
                            logger.info(f"[BulkWordGenerator] Word '{main_word}' already exists for user {user_id} (item {idx}), skipping")
                            continue
                        new_extracted_items.append(item)

                    if not new_extracted_items:
                        logger.info(f"[BulkWordGenerator] All words in chunk {chunk_num} already exist, skipping AI enrichment")
                        continue

                    extracted_items = new_extracted_items
                    logger.debug(f"[BulkWordGenerator] {len(extracted_items)} new words to enrich (chunk {chunk_num})")

                    # Paso 2: Enriquecer palabras del chunk en lote (solo las nuevas)
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

                            # Guardar ejemplos pre-generados del enriquecimiento (10 ejemplos)
                            if enriched.get("examples"):
                                pre_generated_examples[str(word.id)] = enriched["examples"]

                                # Crear los ejemplos directamente en BD (no pasar por Celery)
                                from features.examples.models import Example, ExampleType
                                from core.learning_path.models import LearningPathQueue
                                from core.learning_path.enums import LearningPathQueueStatus

                                examples_list = enriched["examples"]
                                sequence_counter = 1
                                created_examples = []

                                for idx, example_text in enumerate(examples_list):
                                    normalized = example_text.lower().strip()

                                    # Primeros 3 son INITIAL, resto EXPLORE
                                    example_type = ExampleType.INITIAL if idx < 3 else ExampleType.EXPLORE

                                    text_form = approximate_text_form(example_text, main_word)
                                    if not text_form:
                                        text_form = main_word

                                    # Crear el Example con word_id y text_form
                                    example = Example(
                                        type=example_type,
                                        text=example_text,
                                        text_form=text_form,
                                        word_id=word.id,
                                        normalized=normalized,
                                        sequence=sequence_counter,
                                        enqueued=False,
                                    )
                                    db.add(example)
                                    db.flush()
                                    created_examples.append(example.id)
                                    sequence_counter += 1

                                logger.debug(f"[BulkWordGenerator] Created {len(examples_list)} examples for word {word.id}")

                                # ✅ Agregar ejemplos a LearningPathQueue para que estén disponibles inmediatamente
                                for example_id in created_examples:
                                    queue_item = LearningPathQueue(
                                        user_id=user_id,
                                        content_type=ContentType.EXAMPLE,
                                        content_id=example_id,
                                        word_id=word.id,
                                        status=LearningPathQueueStatus.PENDING,
                                        priority=0.5,
                                    )
                                    db.add(queue_item)
                                db.commit()
                                logger.debug(f"[BulkWordGenerator] Added {len(examples_list)} examples to LearningPathQueue for word {word.id}")

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

                            # ✅ Contar palabra creada
                            UserProfileManager.increment_words(db, user_id)

                            # ✅ Contar ejemplos creados
                            if enriched.get("examples"):
                                examples_count = len(enriched["examples"])
                                UserProfileManager.increment_examples(db, user_id, amount=examples_count)

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
                        from features.examples.generator import ExampleGenerator
                        from features.best_options.generator import BestOptionGenerator

                        ExampleGenerator.generate_simple(
                            user_id=user_id,
                            word_ids=chunk_word_ids,
                            amount=1,  # Fallback si no hay pre-generated
                            pre_generated_examples=pre_generated_examples,
                            session=db,
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

                # ✅ Publicar evento SSE de completación
                try:
                    from core.realtime_event_bus import get_realtime_bus
                    event_bus = get_realtime_bus()
                    event_bus.publish(
                        f"user:{user_id}:words_create.completed",
                        {
                            "word_count": len(created_words),
                            "words": [{"id": w.id, "word": w.main} for w in created_words],
                            "status": "ok"
                        }
                    )
                    logger.debug(f"[BulkWordGenerator] Event published: words_create.completed for {len(created_words)} words")
                except Exception as e:
                    logger.error(f"[BulkWordGenerator] Error publishing completion event: {e}")
            else:
                logger.warning(f"[BulkWordGenerator] No words were created for user {user_id}")

    except Exception as e:
        logger.error(
            f"[BulkWordGenerator] Error creating bulk words for user {user_id}: {e}",
            exc_info=True
        )

        # ✅ Publicar evento SSE de error
        try:
            from core.realtime_event_bus import get_realtime_bus
            event_bus = get_realtime_bus()
            event_bus.publish(
                f"user:{user_id}:words_create.failed",
                {
                    "status": "error",
                    "message": str(e)
                }
            )
            logger.debug(f"[BulkWordGenerator] Event published: words_create.failed")
        except Exception as pub_error:
            logger.error(f"[BulkWordGenerator] Error publishing error event: {pub_error}")


@celery_app.task(name="tasks.words.generate_boost_examples", queue=CeleryQueue.AI)
def generate_boost_examples(
    user_id: int,
    word_id: int,
) -> None:
    """
    Genera 2-3 ejemplos adicionales para una palabra boosteada.

    Esto aumenta la exposición inmediata de la palabra sin esperar
    a que se genere contenido en el ciclo normal.

    Los ejemplos se agregan a ContentQueue con ALTA PRIORIDAD para que
    aparezcan frecuentemente intercalados con otros contenidos.
    """
    from db import engine
    from features.words.models import Word, WordStatistics
    from core.enums import ContentType
    from features.examples.models import ExampleType
    from features.examples.repository import ExampleRepository
    from core.learning_path.content_queue import ContentQueue as ContentQueueManager
    from core.learning_path.priority_engine import PriorityEngine

    logger.info(f"[GenerateBoostExamples] Generating additional examples for boosted word {word_id} (user {user_id})")

    try:
        with Session(engine) as db:
            # Obtener la palabra
            word = db.exec(
                select(Word).where(
                    Word.id == word_id,
                    Word.user_id == user_id,
                    Word.is_boosted == True
                )
            ).first()

            if not word:
                logger.warning(f"[GenerateBoostExamples] Boosted word {word_id} not found for user {user_id}")
                return

            # Obtener estadísticas para calcular prioridad
            stats = db.exec(
                select(WordStatistics).where(
                    WordStatistics.word_id == word_id,
                    WordStatistics.type == ContentType.EXAMPLE
                )
            ).first()

            # Calcular prioridad usando PriorityEngine
            priority_engine = PriorityEngine()
            boost_priority = 0.85  # Prioridad alta para boost
            if stats:
                boost_priority = priority_engine.calculate_priority(word, stats)

            # Generar solo 1 ejemplo para evitar que domine la cola
            example_count = 1
            queue_mgr = ContentQueueManager(db)
            generated_count = 0

            for i in range(example_count):
                try:
                    # Usar AI para generar un ejemplo
                    generated = ai.generate_example(word.main, word.meaning)

                    if not generated:
                        logger.warning(f"[GenerateBoostExamples] Could not generate example {i+1} for word {word_id}")
                        continue

                    # Crear ejemplo en BD
                    example_repo = ExampleRepository(db)
                    new_example = example_repo.create(
                        word_id=word_id,
                        example_text=generated.get("example"),
                        definition=generated.get("definition"),
                        type=ExampleType.EXPLORE,
                    )

                    if not new_example:
                        logger.warning(f"[GenerateBoostExamples] Could not create example for word {word_id}")
                        continue

                    # Agregar a ContentQueue con ALTA PRIORIDAD
                    queue_mgr.enqueue(
                        user_id=user_id,
                        content_type=ContentType.EXAMPLE,
                        content_id=new_example.id,
                        word_id=word_id,
                        priority=boost_priority,  # Usar prioridad calculada
                    )

                    logger.info(f"[GenerateBoostExamples] Created example {i+1} for boosted word {word_id} with priority {boost_priority}")
                    generated_count += 1

                except Exception as e:
                    logger.error(f"[GenerateBoostExamples] Error generating example {i+1}: {e}", exc_info=True)
                    continue

            logger.info(f"[GenerateBoostExamples] Completed generating {generated_count} examples for boosted word {word_id}")

    except Exception as e:
        logger.error(
            f"[GenerateBoostExamples] Error generating boost examples for word {word_id}, user {user_id}: {e}",
            exc_info=True
        )
