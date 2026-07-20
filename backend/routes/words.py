import csv
import io
import time
import crud
import schemas
import ai
from typing import List
from logging_config import logger
from fastapi import (APIRouter, Depends, HTTPException,
                     Query, Path, BackgroundTasks, status)
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from db import get_db, engine
from models import WordLevel, ExampleType, User
from helpers import TextFormatter, chunk_list
from auth import get_current_user

router = APIRouter()


@router.get("/words")
def get_words(
    sort: str = "newest",
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    paginated_data = crud.get_words(
        db, current_user.id, sort=sort, page=page, limit=limit)

    paginated_data["items"] = [
        {
            "id": w.id,
            "main": TextFormatter.capitalize(w.main),
            "meaning": TextFormatter.capitalize(w.meaning),
            "synonyms": TextFormatter.capitalize(w.synonyms),
            "type": w.type,
            "frequency": w.frequency,
            "level": WordLevel.to_str(w.level),
            "context": TextFormatter.capitalize(w.context),
            "is_favorite": w.is_favorite,
            "is_learned": w.is_learned,
            "total_examples": total_examples
        }
        for w, total_examples in paginated_data["items"]
    ]

    return paginated_data


@router.get("/words/{word_id}")
def get_word(
    word_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    word = crud.get_word_by_id(db, word_id)

    if not word:
        raise HTTPException(status_code=404, detail="Palabra no encontrada")

    explore_examples_count = sum(
        1 for ew in word.example_words
        if ew.example.is_active and ew.example.type == ExampleType.EXPLORE
    )

    initial_examples = [
        ew.example.text for ew in word.example_words
        if ew.example.is_active and ew.example.type == ExampleType.INITIAL
    ]

    return {
        "id": word.id,
        "main": TextFormatter.capitalize(word.main),
        "meaning": TextFormatter.capitalize(word.meaning),
        "synonyms": TextFormatter.capitalize(word.synonyms),
        "type": word.type,
        "frequency": word.frequency,
        "level": word.level,
        "context": TextFormatter.capitalize(word.context),
        "source_text": word.source_text,
        "is_favorite": word.is_favorite,
        "is_learned": word.is_learned,
        "created_at": word.created_at,
        "total_examples": explore_examples_count,
        "examples": initial_examples
    }


@router.post("")
def create_word(word: schemas.WordCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    extracted = ai.extract_learning_intent(word.text)

    if not extracted:
        return {"error": "No se pudo extraer vocabulario"}

    enriched = ai.enrich_word(extracted["main"])

    word_data = {
        "main": extracted["main"],
        "type": extracted["type"],
        "meaning": enriched.get("meaning"),
        "frequency": enriched.get("frequency"),
        "level": WordLevel.to_int(enriched.get("level")),
        "context": enriched.get("category"),
        "source_text": word.text
    }

    new_word = crud.create_word(db, word_data, current_user.id)

    if new_word and enriched.get("examples"):
        raw_examples = [
            {
                "text": text_string,
                "words": [{"word_id": new_word.id, "word": new_word.main}]
            }
            for text_string in enriched.get("examples", [])
        ]
        crud.create_examples(
            db, raw_examples, example_type=ExampleType.INITIAL)

    return new_word


def process_bulk_words_task(texts: List[str], user_id):
    logger.info(
        f"Iniciando procesamiento por lotes (bulk) para {len(texts)} líneas.")

    CHUNK_SIZE = 15

    # Convertimos el generador en una lista para poder rastrear el índice del lote
    text_chunks = list(chunk_list(texts, CHUNK_SIZE))

    with Session(engine) as db:
        try:
            for chunk_idx, text_chunk in enumerate(text_chunks):
                # Calculamos el índice base en la lista original de textos 'texts'
                # para poder asociar correctamente el source_text original
                start_index = chunk_idx * CHUNK_SIZE

                logger.info(
                    f"--- Procesando Lote {chunk_idx + 1}/{len(text_chunks)} (Tamaño: {len(text_chunk)}) ---")

                # Step 1: Extraer intenciones de aprendizaje SOLO para este lote de 15
                extracted_list = ai.extract_learning_intent(text_chunk)
                if not extracted_list or not isinstance(extracted_list, list):
                    logger.warning(
                        f"No se pudieron extraer palabras para el lote {chunk_idx + 1}. Saltando lote.")
                    continue

                # Step 2: Obtener los términos limpios ('main') a enriquecer
                words_to_enrich = [item["main"]
                                   for item in extracted_list if item.get("main")]
                if not words_to_enrich:
                    logger.info(
                        "No se encontraron palabras válidas para enriquecer en este lote.")
                    continue

                logger.info(
                    f"Palabras extraídas en este lote: {words_to_enrich}. Solicitando enriquecimiento...")

                # Step 3: Enriquecer el lote de palabras
                enriched_results = ai.enrich_words_bulk(words_to_enrich)
                if not enriched_results:
                    logger.warning(
                        f"No se pudo enriquecer el lote actual. Saltando guardado de este lote.")
                    continue

                # Mapeamos los resultados por palabra (en minúsculas) para asociarlos fácilmente
                enriched_map = {res["word"].lower().strip(
                ): res for res in enriched_results if "word" in res}

                # Step 4: Guardar en Base de Datos
                for extracted in extracted_list:
                    main_word = extracted.get("main")
                    if not main_word:
                        continue

                    try:
                        # Buscamos su enriquecimiento correspondiente
                        enriched = enriched_map.get(main_word.lower().strip())
                        if not enriched:
                            logger.warning(
                                f"La IA omitió los detalles para '{main_word}'.")
                            continue

                        # Calculamos el índice absoluto en el array global 'texts'
                        local_idx = extracted.get("raw_index", 0)
                        absolute_idx = start_index + local_idx

                        source_text = texts[absolute_idx] if absolute_idx < len(
                            texts) else "Bulk input"

                        word_data = {
                            "main": main_word,
                            "type": extracted["type"],
                            "meaning": enriched.get("meaning"),
                            "synonyms": enriched.get("synonyms", []),
                            "frequency": enriched.get("frequency"),
                            "level": WordLevel.to_int(enriched.get("level")),
                            "context": enriched.get("category"),
                            "source_text": source_text
                        }

                        # Guardamos palabra
                        new_word = crud.create_word(db, word_data, user_id)

                        # Guardamos sus ejemplos iniciales si se creó con éxito
                        if new_word and enriched.get("examples"):
                            raw_examples = [
                                {
                                    "text": text_string,
                                    "words": [{"word_id": new_word.id, "text_form": ""}],
                                }
                                for text_string in enriched.get("examples", [])
                            ]
                            crud.create_examples(
                                db, raw_examples, example_type=ExampleType.INITIAL)
                            logger.info(f"✓ Guardada: '{new_word.main}'")
                        else:
                            logger.info(
                                f"⚠ Saltada (Duplicada o sin ejemplos): '{main_word}'")

                    except Exception as item_error:
                        logger.error(
                            f"Error procesando palabra individual '{main_word}': {item_error}")
                        continue

                # Pequeña pausa para mitigar límites de Rate Limit (RPM/TPM) de la API
                if chunk_idx < len(text_chunks) - 1:
                    time.sleep(1.0)

            logger.info("Procesamiento bulk completado exitosamente.")

        except Exception as e:
            logger.error(f"Error crítico en la tarea bulk: {e}", exc_info=True)


@router.post("/bulk", status_code=status.HTTP_202_ACCEPTED)
def create_words_bulk(
    texts: List[str],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Lanzamos la tarea pasando solo los textos
    background_tasks.add_task(process_bulk_words_task, texts, current_user.id)

    return {
        "status": "processing",
        "message": f"Processing {len(texts)} texts in the background."
    }


@router.patch("/{word_id}/toggle-active")
# CAMBIO: Tipado de sesión
def toggle_word_active(word_id: int, db: Session = Depends(get_db)):
    word = crud.toggle_word_active(db, word_id)

    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    status = "activated" if word.is_active else "deactivated"
    return {"message": f"Word {status}"}


@router.patch("/{word_id}/toggle-learned")
# CAMBIO: Tipado de sesión
def toggle_word_learned(word_id: int, db: Session = Depends(get_db)):
    word = crud.toggle_word_learned(db, word_id)

    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    return {
        "id": word.id,
        "is_learned": word.is_learned,
        "message": f"Word marked as {'learned' if word.is_learned else 'not learned'}"
    }


@router.patch("/{word_id}/toggle-fav")
# CAMBIO: Tipado de sesión
def toggle_word_favorite(word_id: int, db: Session = Depends(get_db)):
    word = crud.toggle_word_favorite(db, word_id)

    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    return {
        "id": word.id,
        "is_favorite": word.is_favorite,
        "message": f"Word marked as {'favorited' if word.is_favorite else 'not favorited'}"
    }


@router.get("/export/csv")
def export_words_csv(db: Session = Depends(get_db)):
    words_list = crud.get_all_words(db)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "id",
        "word",
        "type",
        "meaning",
        "is_active",
        "is_learned"
    ])

    for word in words_list:
        writer.writerow([
            word.id,
            word.main,
            word.type,
            word.meaning,
            word.is_active,
            word.is_learned
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=words.csv"
        }
    )
