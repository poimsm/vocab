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
from tasks.words import process_bulk_words_task

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
