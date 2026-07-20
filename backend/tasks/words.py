# backend/tasks/words.py
import time
from typing import List
from sqlmodel import Session
from celery_app import celery_app
from db import engine
from models import WordLevel, ExampleType
from helpers import chunk_list
import crud
import ai
from logging_config import logger


@celery_app.task(name="tasks.words.process_bulk_words")
def process_bulk_words_task(texts: List[str], user_id: int):
    logger.info(
        f"[Celery Bulk] Iniciando procesamiento por lotes para {len(texts)} líneas (Usuario: {user_id})."
    )

    CHUNK_SIZE = 15
    text_chunks = list(chunk_list(texts, CHUNK_SIZE))

    with Session(engine) as db:
        try:
            for chunk_idx, text_chunk in enumerate(text_chunks):
                start_index = chunk_idx * CHUNK_SIZE

                logger.info(
                    f"--- Procesando Lote {chunk_idx + 1}/{len(text_chunks)} (Tamaño: {len(text_chunk)}) ---"
                )

                # Step 1: Extraer intenciones de aprendizaje
                extracted_list = ai.extract_learning_intent(text_chunk)
                if not extracted_list or not isinstance(extracted_list, list):
                    logger.warning(
                        f"No se pudieron extraer palabras para el lote {chunk_idx + 1}. Saltando."
                    )
                    continue

                # Step 2: Términos limpios
                words_to_enrich = [
                    item["main"] for item in extracted_list if item.get("main")
                ]
                if not words_to_enrich:
                    logger.info(
                        "No se encontraron palabras válidas en este lote.")
                    continue

                # Step 3: Enriquecer con IA
                enriched_results = ai.enrich_words_bulk(words_to_enrich)
                if not enriched_results:
                    logger.warning(
                        f"No se pudo enriquecer el lote actual. Saltando."
                    )
                    continue

                enriched_map = {
                    res["word"].lower().strip(): res
                    for res in enriched_results
                    if "word" in res
                }

                # Step 4: Guardar en Base de Datos
                for extracted in extracted_list:
                    main_word = extracted.get("main")
                    if not main_word:
                        continue

                    try:
                        enriched = enriched_map.get(main_word.lower().strip())
                        if not enriched:
                            logger.warning(
                                f"La IA omitió los detalles para '{main_word}'."
                            )
                            continue

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
                        }

                        new_word = crud.create_word(db, word_data, user_id)

                        if new_word and enriched.get("examples"):
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
                            logger.info(f"✓ Guardada: '{new_word.main}'")
                        else:
                            logger.info(
                                f"⚠ Saltada (Duplicada o sin ejemplos): '{main_word}'"
                            )

                    except Exception as item_error:
                        logger.error(
                            f"Error procesando palabra individual '{main_word}': {item_error}"
                        )
                        continue

                # Pausa preventiva entre lotes internos de la misma solicitud
                if chunk_idx < len(text_chunks) - 1:
                    time.sleep(1.0)

            logger.info("[Celery Bulk] Procesamiento completado exitosamente.")

        except Exception as e:
            logger.error(
                f"Error crítico en la tarea Celery bulk: {e}", exc_info=True)
