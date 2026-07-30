# backend/tasks/words.py
import time
from typing import List
from sqlmodel import Session
from celery_app import celery_app
from db import engine
from models import WordLevel, ExampleType, BatchSource
from helpers import chunk_list
import crud
import ai
from logging_config import logger


@celery_app.task(name="tasks.words.process_bulk_words")
def process_bulk_words_task(texts: List[str], user_id: int):
    logger.info(
        f"[Celery Bulk] Starting batch processing for {len(texts)} lines (User: {user_id})."
    )

    with Session(engine) as db:
        chunk_size = crud.get_chunk_size(db)

    text_chunks = list(chunk_list(texts, chunk_size))

    with Session(engine) as db:
        try:
            # Obtener o crear el lote propicio inicial para el usuario
            current_batch = crud.get_or_create_propitious_batch(
                db, 
                user_id=user_id, 
                source=BatchSource.BULK_IMPORT,
                title="Importación masiva"
            )

            for chunk_idx, text_chunk in enumerate(text_chunks):
                start_index = chunk_idx * chunk_size

                logger.info(
                    f"--- Processing Chunk {chunk_idx + 1}/{len(text_chunks)} (Size: {len(text_chunk)}) ---"
                )

                # Step 1: Extraer intenciones de aprendizaje
                extracted_list = ai.extract_learning_intent(text_chunk)
                if not extracted_list or not isinstance(extracted_list, list):
                    logger.warning(
                        f"Could not extract words for chunk {chunk_idx + 1}. Skipping."
                    )
                    continue

                # Step 2: Términos limpios
                words_to_enrich = [
                    item["main"] for item in extracted_list if item.get("main")
                ]
                if not words_to_enrich:
                    logger.info("No valid words found in this chunk.")
                    continue

                # Step 3: Enriquecer con IA
                enriched_results = ai.enrich_words_bulk(words_to_enrich)
                if not enriched_results:
                    logger.warning("Could not enrich current chunk. Skipping.")
                    continue

                enriched_map = {
                    res["word"].lower().strip(): res
                    for res in enriched_results
                    if "word" in res
                }

                # Step 4: Guardar en Base de Datos asignando Lote
                for extracted in extracted_list:
                    main_word = extracted.get("main")
                    if not main_word:
                        continue

                    try:
                        enriched = enriched_map.get(main_word.lower().strip())
                        if not enriched:
                            logger.warning(
                                f"AI omitted details for '{main_word}'."
                            )
                            continue

                        # Validar si el lote actual ya alcanzó su capacidad (ej. 20 palabras)
                        # Si está lleno, se crea/asigna un nuevo Batch dinámicamente
                        if len(current_batch.words) >= current_batch.capacity:
                            logger.info(f"Current batch #{current_batch.id} reached capacity ({current_batch.capacity}). Creating new batch.")
                            current_batch = crud.get_or_create_propitious_batch(
                                db,
                                user_id=user_id,
                                source=BatchSource.BULK_IMPORT,
                                title="Importación masiva"
                            )

                        local_idx = extracted.get("raw_index", 0)
                        absolute_idx = start_index + local_idx
                        source_text = (
                            texts[absolute_idx]
                            if absolute_idx < len(texts)
                            else "Bulk input"
                        )

                        word_data = {
                            "main": main_word,
                            "type": extracted["type"],
                            "meaning": enriched.get("meaning"),
                            "synonyms": enriched.get("synonyms", []),
                            "frequency": enriched.get("frequency"),
                            "level": WordLevel.to_int(enriched.get("level")),
                            "context": enriched.get("category"),
                            "source_text": source_text,
                            "batch_id": current_batch.id,  # <-- ASIGNACIÓN DE BATCH
                        }

                        new_word = crud.create_word(db, word_data, user_id)

                        if new_word:
                            # Refrescar la relación de palabras del lote en memoria para el conteo de capacidad
                            db.refresh(current_batch)

                            if enriched.get("examples"):
                                raw_examples = [
                                    {
                                        "text": text_string,
                                        "words": [
                                            {"word_id": new_word.id, "text_form": ""}
                                        ],
                                    }
                                    for text_string in enriched.get("examples", [])
                                ]
                                crud.create_examples(
                                    db, raw_examples, example_type=ExampleType.INITIAL
                                )
                            logger.info(f"✓ Saved: '{new_word.main}' in Batch #{current_batch.id}")
                        else:
                            logger.info(
                                f"⚠ Saltada (Duplicada): '{main_word}'"
                            )

                    except Exception as item_error:
                        logger.error(
                            f"Error processing individual word '{main_word}': {item_error}"
                        )
                        continue

                # Pausa preventiva entre chunks
                if chunk_idx < len(text_chunks) - 1:
                    time.sleep(1.0)

            # Actualizar las métricas y estado del último lote procesado
            if current_batch and current_batch.id:
                crud.update_batch_metrics(db, current_batch.id)

            logger.info("[Celery Bulk] Batch processing completed successfully.")

        except Exception as e:
            logger.error(
                f"Critical error in Celery bulk task: {e}", exc_info=True
            )