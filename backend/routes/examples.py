from fastapi import HTTPException, Query, Body, APIRouter, Depends
from sqlmodel import Session  # CAMBIO: Usamos la sesión de SQLModel

# CORRECCIÓN: Ajustamos las importaciones locales eliminando el prefijo app.
from db import get_db
import crud
import ai

router = APIRouter()


@router.get("/examples")
def get_examples(
    sort: str = "newest",
    word_id: int = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db)  # CAMBIO: Tipado de sesión
):
    paginated_data = crud.get_examples(
        db, sort=sort, word_id=word_id, page=page, limit=limit
    )

    paginated_data["items"] = [
        {
            "id": e.id,
            "text": e.text,
            "is_favorite": e.is_favorite,
            "words": [
                {
                    "word_id": ew.word_id,
                    "main": ew.word.main,
                    "text_form": ew.text_form
                }
                for ew in e.example_words
            ]
        }
        for e in paginated_data["items"]
    ]

    return paginated_data


@router.post("/generate")
def generate_examples(
    word_id: int = Body(None, embed=True),
    db: Session = Depends(get_db)  # CAMBIO: Tipado de sesión
):
    # CASO 1: Viene un word_id
    if word_id is not None:
        word = crud.get_word_by_id(db, word_id)
        if not word:
            # CORRECCIÓN: Cambiado typo de status_with_code a status_code
            raise HTTPException(
                status_code=404, detail="Palabra no encontrada")

        raw_strings = ai.generate_examples_for_single_word(word, amount=3)
        if not raw_strings:
            raise HTTPException(
                status_code=500, detail="Error generando ejemplos con IA"
            )

        raw_examples = [
            {
                "text": text_string,
                "words": [{"word_id": word.id, "word": word.main}]
            }
            for text_string in raw_strings
        ]

        words_to_increment = [word]

    # CASO 2: No viene word_id
    else:
        words_to_increment = crud.get_words_least_seen(db)
        if not words_to_increment:
            return []

        raw_examples = ai.generate_examples_from_words(words_to_increment)

    examples = crud.create_examples(db, raw_examples)
    crud.increment_words_seen(db, words_to_increment)

    return [{"id": e.id, "text": e.text} for e in examples]


@router.get("/random")
def get_random_examples(db: Session = Depends(get_db)):  # CAMBIO: Tipado de sesión
    words = crud.get_words_least_seen(db, 4)
    if not words:
        return []

    word_ids = [w.id for w in words]
    examples = crud.get_random_examples_by_words(db, word_ids=word_ids)

    crud.increment_words_seen(db, words)

    return [
        {
            "id": e.id,
            "text": e.text,
            "words": [
                {
                    "word_id": ew.word_id,
                    "main": ew.word.main,
                    "text_form": ew.text_form
                }
                for ew in e.example_words
            ]
        }
        for e in examples
    ]


@router.patch("/{example_id}/toggle-active")
# CAMBIO: Tipado de sesión
def toggle_example_active(example_id: int, db: Session = Depends(get_db)):
    example = crud.toggle_example_active(db, example_id)

    if not example:
        raise HTTPException(status_code=404, detail="example not found")

    status = "activated" if example.is_active else "deactivated"
    return {"message": f"example {status}"}


@router.patch("/{example_id}/toggle-fav")
# CAMBIO: Tipado de sesión
def toggle_example_favorite(example_id: int, db: Session = Depends(get_db)):
    example = crud.toggle_example_favorite(db, example_id)

    if not example:
        raise HTTPException(status_code=404, detail="example not found")

    return {
        "id": example.id,
        "is_favorite": example.is_favorite,
        "message": f"example marked as {'favorited' if example.is_favorite else 'not favorited'}"
    }
