import csv
import io
import time
import crud
import schemas
import ai
from typing import List
from logging_client import logger
from fastapi import (APIRouter, Depends, HTTPException,
                     Query, Path, BackgroundTasks, status, Body)
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from db import get_db, engine
from models import WordLevel, ExampleType, User, BatchSource, Word, WordStatistics, FeaturedType
from helpers import TextFormatter, chunk_list
from auth import get_current_user
from tasks.words import process_bulk_words_task
from datetime import datetime, timezone
from schemas.words import WordCreate

router = APIRouter()


@router.get("/words")
def get_words(
    sort: str = "newest",
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"[get_words] User {current_user.id}: Fetching words (sort={sort}, page={page}, limit={limit})")
    paginated_data = crud.get_words(
        db, current_user.id, sort=sort, page=page, limit=limit)
    logger.debug(f"[get_words] Retrieved {len(paginated_data['items'])} words")

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
            "is_learned": all(stat.is_learned for stat in w.statistics if stat.type == FeaturedType.EXAMPLE) if w.statistics else False,
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
    logger.debug(f"[get_word] User {current_user.id}: Fetching word {word_id}")
    word = crud.get_word_by_id(db, word_id)

    if not word:
        logger.warning(f"[get_word] Word {word_id} not found")
        raise HTTPException(status_code=404, detail="Palabra no encontrada")

    explore_examples_count = sum(
        1 for ew in word.example_words
        if ew.example.is_active and ew.example.type == ExampleType.EXPLORE
    )

    initial_examples = [
        ew.example.text for ew in word.example_words
        if ew.example.is_active and ew.example.type == ExampleType.INITIAL
    ]

    is_learned = all(stat.is_learned for stat in word.statistics if stat.type == FeaturedType.EXAMPLE) if word.statistics else False

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
        "is_learned": is_learned,
        "created_at": word.created_at,
        "total_examples": explore_examples_count,
        "examples": initial_examples
    }


@router.post("/old")
def create_word(word: WordCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
        examples_list = enriched.get("examples", [])
        initial_examples = examples_list[:3]
        explore_examples = examples_list[3:]

        # Create INITIAL examples (first 3)
        if initial_examples:
            raw_initial = [
                {
                    "text": text_string,
                    "words": [{"word_id": new_word.id, "word": new_word.main}]
                }
                for text_string in initial_examples
            ]
            crud.create_examples(db, raw_initial, example_type=ExampleType.INITIAL)

        # Create EXPLORE examples (rest)
        if explore_examples:
            raw_explore = [
                {
                    "text": text_string,
                    "words": [{"word_id": new_word.id, "word": new_word.main}]
                }
                for text_string in explore_examples
            ]
            crud.create_examples(db, raw_explore, example_type=ExampleType.EXPLORE)

    return new_word


@router.post("/test")
def test_create_word(data: dict):
    """Endpoint de prueba para verificar que POST funciona"""
    logger.info(f"[test_create_word] Data received: {data}")
    return {"received": data}


@router.post("")
def create_single_word(
    request_data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crea una palabra individual procesando texto libre.
    Extrae la palabra, la enriquece con IA, y la asigna a un batch.
    """
    try:
        text = request_data.get("text")
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="El campo 'text' es requerido")

        logger.info(f"[create_single_word] Processing word for user {current_user.id}: '{text}'")

        # 1. Extraer la palabra del texto
        extracted_list = ai.extract_learning_intent([text.strip()])
        if not extracted_list or len(extracted_list) == 0:
            raise HTTPException(status_code=400, detail="No se pudo extraer una palabra válida del texto")

        extracted = extracted_list[0]
        main_word = extracted.get("main")
        if not main_word:
            raise HTTPException(status_code=400, detail="No se pudo determinar la palabra principal")

        logger.info(f"[create_single_word] Extracted word: '{main_word}'")

        # 2. Enriquecer la palabra con IA
        enriched = ai.enrich_word(main_word)
        if not enriched:
            raise HTTPException(status_code=400, detail="No se pudo enriquecer la palabra")

        logger.info(f"[create_single_word] Word enriched with: meaning, synonyms, level, category")

        # 3. Obtener o crear el lote más propicio para palabras sueltas
        propitious_batch = crud.get_or_create_propitious_batch(
            db,
            user_id=current_user.id,
            source=BatchSource.ORGANIC
        )
        logger.info(f"[create_single_word] Assigned batch: {propitious_batch.id} ({propitious_batch.title})")

        # 4. Preparar datos para crear la palabra
        word_data = {
            "main": main_word,
            "type": extracted.get("type"),
            "meaning": enriched.get("meaning"),
            "synonyms": enriched.get("synonyms", []),
            "frequency": enriched.get("frequency"),
            "level": WordLevel.to_int(enriched.get("level")),
            "context": enriched.get("category"),
            "source_text": text.strip(),
            "batch_id": propitious_batch.id,
        }

        # 5. Crear la palabra
        new_word = crud.create_word(db, word_data, user_id=current_user.id)
        if not new_word:
            raise HTTPException(status_code=400, detail="La palabra ya existe")

        logger.info(f"[create_single_word] Word created: {new_word.id} - {new_word.main}")

        # 6. Crear ejemplos iniciales si existen
        if enriched.get("examples"):
            examples_list = enriched.get("examples", [])
            initial_examples = examples_list[:3]
            explore_examples = examples_list[3:]

            # Create INITIAL examples (first 3)
            if initial_examples:
                raw_initial = [
                    {
                        "text": example_text,
                        "words": [
                            {"word_id": new_word.id, "text_form": ""}
                        ],
                    }
                    for example_text in initial_examples
                ]
                crud.create_examples(db, raw_initial, example_type=ExampleType.INITIAL)
                logger.info(f"[create_single_word] Initial examples created: {len(raw_initial)}")

            # Create EXPLORE examples (rest)
            if explore_examples:
                raw_explore = [
                    {
                        "text": example_text,
                        "words": [
                            {"word_id": new_word.id, "text_form": ""}
                        ],
                    }
                    for example_text in explore_examples
                ]
                crud.create_examples(db, raw_explore, example_type=ExampleType.EXPLORE)
                logger.info(f"[create_single_word] Explore examples created: {len(raw_explore)}")

        return {
            "id": new_word.id,
            "main": new_word.main,
            "meaning": new_word.meaning,
            "type": new_word.type,
            "level": new_word.level,
            "synonyms": new_word.synonyms,
            "frequency": new_word.frequency,
            "context": new_word.context,
            "batch_id": new_word.batch_id,
            "created_at": new_word.created_at,
            "message": "Palabra creada exitosamente"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[create_single_word] Error creating word: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk", status_code=status.HTTP_202_ACCEPTED)
def create_words_bulk(
    texts: List[str],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = process_bulk_words_task.delay(texts, current_user.id)

    return {
        "status": "queued",
        "task_id": task.id,
        "message": f"Processing {len(texts)} texts sequentially in background."
    }


@router.patch("/{word_id}/mark-learned")
def mark_word_learned(
    word_id: int,
    featured_type: FeaturedType = Query(FeaturedType.EXAMPLE),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Marca una palabra como dominada/aprendida para un tipo específico y actualiza
    las métricas de su lote correspondiente.
    """
    word = crud.get_word_by_id(db, word_id)
    if not word or word.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Palabra no encontrada")

    # Marcar como aprendida solo para el tipo específico
    from models import WordStatistics
    word_stats = db.exec(
        select(WordStatistics).where(
            WordStatistics.word_id == word_id,
            WordStatistics.type == featured_type
        )
    ).all()
    for stat in word_stats:
        stat.is_learned = True
        db.add(stat)
    db.commit()

    return {"message": "Palabra marcada como aprendida", "word_id": word.id}


@router.patch("/{word_id}/toggle-boost")
def toggle_word_boost(
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Permite al usuario dar prioridad absoluta (Boost) a una palabra.
    """
    logger.debug(f"[toggle_word_boost] User {current_user.id}: Toggling boost for word {word_id}")
    word = crud.get_word_by_id(db, word_id)
    if not word or word.user_id != current_user.id:
        logger.warning(f"[toggle_word_boost] Word {word_id} not found or unauthorized")
        raise HTTPException(status_code=404, detail="Palabra no encontrada")

    word.is_boosted = not word.is_boosted
    word.boosted_at = datetime.now(timezone.utc) if word.is_boosted else None

    db.add(word)
    db.commit()
    logger.info(f"[toggle_word_boost] Word {word_id} boost set to {word.is_boosted}")

    return {"id": word.id, "is_boosted": word.is_boosted}


@router.patch("/{word_id}/toggle-active")
# CAMBIO: Tipado de sesión
def toggle_word_active(word_id: int, db: Session = Depends(get_db)):
    logger.debug(f"[toggle_word_active] Toggling active status for word {word_id}")
    word = crud.toggle_word_active(db, word_id)

    if not word:
        logger.warning(f"[toggle_word_active] Word {word_id} not found")
        raise HTTPException(status_code=404, detail="Word not found")

    status = "activated" if word.is_active else "deactivated"
    logger.info(f"[toggle_word_active] Word {word_id} {status}")
    return {"message": f"Word {status}"}


@router.patch("/{word_id}/toggle-learned")
# CAMBIO: Tipado de sesión
def toggle_word_learned(word_id: int, db: Session = Depends(get_db)):
    logger.debug(f"[toggle_word_learned] Toggling learned status for word {word_id}")
    word = crud.toggle_word_learned(db, word_id)

    if not word:
        logger.warning(f"[toggle_word_learned] Word {word_id} not found")
        raise HTTPException(status_code=404, detail="Word not found")

    is_learned = all(stat.is_learned for stat in word.statistics if stat.type == FeaturedType.EXAMPLE) if word.statistics else False
    logger.info(f"[toggle_word_learned] Word {word_id} marked as {'learned' if is_learned else 'not learned'}")
    return {
        "id": word.id,
        "is_learned": is_learned,
        "message": f"Word marked as {'learned' if is_learned else 'not learned'}"
    }


@router.patch("/{word_id}/toggle-fav")
# CAMBIO: Tipado de sesión
def toggle_word_favorite(word_id: int, db: Session = Depends(get_db)):
    logger.debug(f"[toggle_word_favorite] Toggling favorite status for word {word_id}")
    word = crud.toggle_word_favorite(db, word_id)

    if not word:
        logger.warning(f"[toggle_word_favorite] Word {word_id} not found")
        raise HTTPException(status_code=404, detail="Word not found")

    logger.info(f"[toggle_word_favorite] Word {word_id} marked as {'favorited' if word.is_favorite else 'not favorited'}")
    return {
        "id": word.id,
        "is_favorite": word.is_favorite,
        "message": f"Word marked as {'favorited' if word.is_favorite else 'not favorited'}"
    }




@router.get("/export/csv")
def export_words_csv(db: Session = Depends(get_db)):
    logger.info("[export_words_csv] Starting CSV export")
    words_list = crud.get_all_words(db)
    logger.info(f"[export_words_csv] Exporting {len(words_list)} words to CSV")

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
        is_learned = all(stat.is_learned for stat in word.statistics if stat.type == FeaturedType.EXAMPLE) if word.statistics else False
        writer.writerow([
            word.id,
            word.main,
            word.type,
            word.meaning,
            word.is_active,
            is_learned
        ])

    output.seek(0)
    logger.debug("[export_words_csv] CSV file generated successfully")

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=words.csv"
        }
    )
