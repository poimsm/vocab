import csv
import io
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.responses import StreamingResponse
from sqlmodel import Session  # CAMBIO: Usamos la sesión de SQLModel

# CORRECCIÓN: Ajustamos las importaciones al mismo nivel (sin el prefijo app.)
from db import get_db
import crud
import schemas
import ai
from models import WordLevel

router = APIRouter()


@router.get("/words")
def get_words(
    sort: str = "newest",
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db)  # CAMBIO: Tipado de sesión
):
    paginated_data = crud.get_words(db, sort=sort, page=page, limit=limit)

    paginated_data["items"] = [
        {
            "id": w.id,
            "main": w.main,
            "meaning": w.meaning,
            "type": w.type,
            "frequency": w.frequency,
            "level": WordLevel.to_str(w.level),
            "context": w.context,
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
    db: Session = Depends(get_db)  # CAMBIO: Tipado de sesión
):
    word = crud.get_word_by_id(db, word_id)

    if not word:
        raise HTTPException(status_code=404, detail="Palabra no encontrada")

    # Extraemos todos los textos de los ejemplos asociados a través de la intermedia
    all_examples = [
        ew.example.text for ew in word.example_words if ew.example.is_active
    ]

    return {
        "id": word.id,
        "main": word.main,
        "meaning": word.meaning,
        "type": word.type,
        "frequency": word.frequency,
        "level": word.level,
        "context": word.context,
        "source_text": word.source_text,
        "is_favorite": word.is_favorite,
        "is_learned": word.is_learned,
        "created_at": word.created_at,
        "total_examples": len(all_examples),
        "examples": all_examples[:3]
    }


@router.post("")
def create_word(word: schemas.WordCreate, db: Session = Depends(get_db)):  # CAMBIO: Tipado de sesión
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

    new_word = crud.create_word(db, word_data)
    return new_word


@router.post("/bulk")
def create_words_bulk(texts: List[str], db: Session = Depends(get_db)):  # CAMBIO: Tipado de sesión
    created_words = []

    for text in texts:
        extracted = ai.extract_learning_intent(text)

        if not extracted:
            continue

        enriched = ai.enrich_word(extracted["main"])

        word_data = {
            "main": extracted["main"],
            "type": extracted["type"],
            "meaning": enriched.get("meaning"),
            "frequency": enriched.get("frequency"),
            "level": WordLevel.to_int(enriched.get("level")),
            "context": enriched.get("category"),
            "source_text": text
        }

        new_word = crud.create_word(db, word_data)

        if new_word:
            created_words.append(new_word)

    return {
        "created": len(created_words),
        "words": created_words
    }


@router.patch("/{word_id}/toggle-active")
def toggle_word_active(word_id: int, db: Session = Depends(get_db)):  # CAMBIO: Tipado de sesión
    word = crud.toggle_word_active(db, word_id)

    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    status = "activated" if word.is_active else "deactivated"
    return {"message": f"Word {status}"}


@router.patch("/{word_id}/toggle-learned")
def toggle_word_learned(word_id: int, db: Session = Depends(get_db)):  # CAMBIO: Tipado de sesión
    word = crud.toggle_word_learned(db, word_id)

    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    return {
        "id": word.id,
        "is_learned": word.is_learned,
        "message": f"Word marked as {'learned' if word.is_learned else 'not learned'}"
    }


@router.patch("/{word_id}/toggle-fav")
def toggle_word_favorite(word_id: int, db: Session = Depends(get_db)):  # CAMBIO: Tipado de sesión
    word = crud.toggle_word_favorite(db, word_id)

    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    return {
        "id": word.id,
        "is_favorite": word.is_favorite,
        "message": f"Word marked as {'favorited' if word.is_favorite else 'not favorited'}"
    }


@router.get("/export/csv")
def export_words_csv(db: Session = Depends(get_db)):  # CAMBIO: Tipado de sesión
    # NOTA: Asegúrate de tener implementado 'get_all_words' en tu crud.py si vas a usar este endpoint
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