import collections
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select, func

import crud
from db import get_db
from logging_config import logger
from tasks.examples import refill_queue_task
from schemas.explore import ExploreResponse, ExploreExampleSchema, ExploreWordSchema
from auth import get_current_user
from models import User, ExampleQueue, Example, Word, Batch, QueueStatus, ExampleWord

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


@router.get("/explore", response_model=ExploreResponse)
def get_explore_feed(
    limit: int = 5,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el lote actual de ejemplos/oraciones para el Explore,
    basado en la jerarquía de Lotes (Batch) y palabras prioritarias.
    """

    # 1. Obtener ejemplos listos desde la cola de ejemplos (ExampleQueue) del usuario
    queued_items = db.exec(
        select(ExampleQueue)
        .join(Example)
        .where(
            ExampleQueue.user_id == current_user.id,
            ExampleQueue.status == QueueStatus.PENDING
        )
        .options(
            joinedload(ExampleQueue.example).joinedload(Example.example_words).joinedload(ExampleWord.word)
        )
        .order_by(ExampleQueue.created_at.asc())
        .limit(limit)
    ).unique().all()

    # 2. Si la cola está vacía o tiene muy pocos elementos, ejecutamos el generador de emergencia
    if len(queued_items) < limit:
        # Obtenemos las palabras prioritarias respetando la lógica de Lotes + Transición
        priority_words = crud.get_priority_words_via_batches(
            db, user_id=current_user.id, limit=8)
        
        logger.info(f"priority_words {len(priority_words)}")

        if not priority_words:
            # El usuario no tiene palabras agregadas aún
            return ExploreResponse(
                examples=[],
                active_batch_id=None,
                active_batch_title=None,
                total_queue_remaining=0
            )

        # Generar o rellenar la cola en segundo plano vía Celery para que la API no se bloquee
        refill_queue_task.delay(user_id=current_user.id)

    # 3. Formatear los ejemplos recuperados de la cola
    formatted_examples: List[ExploreExampleSchema] = []

    for item in queued_items:
        example = item.example
        logger.info(f"Example {example.id}: example_words count = {len(example.example_words) if example.example_words else 0}")

        # Mapeamos las palabras involucradas en este ejemplo
        words_in_example = []
        has_unlearned_word = False
        for word in example.words:  # Asumiendo relación N:M entre Example y Word
            words_in_example.append(
                ExploreWordSchema(
                    id=word.id,
                    main=word.main,
                    type=word.type,
                    meaning=word.meaning,
                    level=word.level,
                    is_boosted=word.is_boosted,
                    batch_id=word.batch_id
                )
            )
            # Verificar si al menos una palabra no ha sido aprendida
            if not word.is_learned:
                has_unlearned_word = True

        # Solo incluir el ejemplo si tiene al menos una palabra no aprendida
        if has_unlearned_word:
            formatted_examples.append(
                ExploreExampleSchema(
                    id=example.id,
                    text=example.text,
                    target_words=words_in_example
                )
            )

            # Marcar como entregado de la cola ExampleQueue
            item.status = QueueStatus.SENT
            db.add(item)
        else:
            # Si todas las palabras ya fueron aprendidas, marcar como RESOLVED
            logger.info(f"Example {example.id}: todas sus palabras son learned, marcando como RESOLVED")
            item.status = QueueStatus.RESOLVED
            db.add(item)        

    db.commit()

    # 4. Obtener la metadata del Lote Activo principal para contexto en el Frontend
    active_batch = db.exec(
        select(Batch)
        .where(Batch.user_id == current_user.id, Batch.status == "active")
        .order_by(Batch.priority.desc(), Batch.created_at.asc())
    ).first()

    # Contar cuántos elementos quedan en la cola
    remaining_count = db.exec(
        select(func.count(ExampleQueue.id)).where(
            ExampleQueue.user_id == current_user.id)
    ).one() or 0

    return ExploreResponse(
        examples=formatted_examples,
        active_batch_id=active_batch.id if active_batch else None,
        active_batch_title=active_batch.title if active_batch else None,
        total_queue_remaining=remaining_count
    )


@router.patch("/{example_id}/resolve-pending")
def resolve_example_pending(example_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    example = crud.resolve_and_increment_example(db, example_id=example_id, user_id=current_user.id)

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
