import collections
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlmodel import Session

import crud
from db import get_db
from logging_config import logger
from tasks.examples import refill_queue_task

router = APIRouter()


@router.get("/examples")
def get_examples(
    sort: str = "newest",
    word_id: int = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
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
                    "text_form": ew.text_form,
                }
                for ew in e.example_words
            ],
        }
        for e in paginated_data["items"]
    ]

    return paginated_data


@router.patch("/{example_id}/toggle-active")
def toggle_example_active(example_id: int, db: Session = Depends(get_db)):
    example = crud.toggle_example_active(db, example_id)

    if not example:
        raise HTTPException(status_code=404, detail="example not found")

    status = "activated" if example.is_active else "deactivated"
    return {"message": f"example {status}"}


@router.patch("/{example_id}/toggle-fav")
def toggle_example_favorite(example_id: int, db: Session = Depends(get_db)):
    example = crud.toggle_example_favorite(db, example_id)

    if not example:
        raise HTTPException(status_code=404, detail="example not found")

    return {
        "id": example.id,
        "is_favorite": example.is_favorite,
        "message": f"example marked as {'favorited' if example.is_favorite else 'not favorited'}",
    }


@router.post("/explore")
def explore_examples(
    total_amount: int = Body(
        15, ge=3, le=20, description="Total de ejemplos a retornar", embed=True
    ),
    db: Session = Depends(get_db),
):
    # 1. Obtenemos candidatos de la cola para filtrar
    raw_queue_examples = crud.get_examples_from_queue(
        db, limit=total_amount * 3
    )

    # Si la cola está vacía, delegamos el refill pesado a Celery en segundo plano
    if not raw_queue_examples:
        logger.info("Cola vacía al iniciar. Encolando refill en Celery.")
        refill_queue_task.delay()
        raw_queue_examples = crud.get_examples_from_queue(
            db, limit=total_amount * 3
        )

    # Helper para calcular la puntuación de un ejemplo (puntuaciones BAJAS = prioridad alta)
    def calculate_example_score(example) -> float:
        if not example.example_words:
            return 999.0

        views = [ew.word.times_seen for ew in example.example_words]
        min_views = min(views)
        avg_views = sum(views) / len(views)

        # Penalización por palabras que superan las 5 vistas
        penalty = sum(15.0 for v in views if v > 5)

        return min_views + (avg_views * 0.1) + penalty

    # 2. Selección balanceada con control de diversidad
    def select_balanced_examples(candidates, limit: int) -> List:
        sorted_candidates = sorted(candidates, key=calculate_example_score)

        selected = []
        word_usage_counter = collections.Counter()
        MAX_REPETITIONS_PER_WORD = 2

        for e in sorted_candidates:
            has_overused_word = any(
                word_usage_counter[ew.word_id] >= MAX_REPETITIONS_PER_WORD
                for ew in e.example_words
            )

            if has_overused_word:
                continue

            selected.append(e)
            for ew in e.example_words:
                word_usage_counter[ew.word_id] += 1

            if len(selected) >= limit:
                break

        # Si no llenamos el cupo por el filtro estricto, hacemos una segunda pasada relajada
        if len(selected) < limit:
            for e in sorted_candidates:
                if e not in selected:
                    selected.append(e)
                if len(selected) >= limit:
                    break

        return selected

    filtered_examples = select_balanced_examples(
        raw_queue_examples, total_amount
    )

    # 3. Control de déficit: Si quedan menos ejemplos de los solicitados,
    # disparamos el refill asíncrono para reponer inventario sin bloquear la respuesta.
    deficit = total_amount - len(filtered_examples)
    if deficit > 0:
        logger.info(f"Déficit de {deficit} ejemplos. Encolando refill en Celery.")
        refill_queue_task.delay()

    # 4. Incrementar vistas de palabras entregadas al usuario
    if filtered_examples:
        try:
            for e in filtered_examples:
                for ew in e.example_words:
                    ew.word.times_seen += 1
                    db.add(ew.word)
            db.commit()

            for e in filtered_examples:
                db.refresh(e)
        except Exception as write_error:
            db.rollback()
            logger.error(f"Error al actualizar vistas de palabras: {write_error}")

    # 5. Respuesta mapeada
    return [
        {
            "id": e.id,
            "text": e.text,
            "words": [
                {
                    "word_id": ew.word_id,
                    "main": ew.word.main,
                    "text_form": ew.text_form,
                }
                for ew in e.example_words
            ],
        }
        for e in filtered_examples
    ]


@router.patch("/{example_id}/resolve-pending")
def resolve_example_pending(example_id: int, db: Session = Depends(get_db)):
    example = crud.resolve_and_increment_example(db, example_id)

    if not example:
        raise HTTPException(
            status_code=404,
            detail="Example no encontrado o ya no estaba marcado como pendiente",
        )

    return {
        "id": example.id,
        "times_seen": example.times_seen,
        "message": "El ejemplo ya no está pendiente. Visualizaciones incrementadas con éxito.",
    }