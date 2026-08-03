from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select, func

import crud
from db import get_db
from logging_config import logger
from tasks.examples import refill_queue_task
from schemas.explore import ExploreResponse, ExploreExampleSchema, ExploreWordSchema
from auth import get_current_user
from models import (User, ExampleQueue, Example, Word,
                    Batch, QueueStatus, ExampleWord, QueueType, FeaturedType)
from batch_manager import BatchManager

router = APIRouter()


@router.get("/examples")
def get_examples(
    sort: str = "newest",
    word_id: int = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
):
    logger.info(
        f"[get_examples] Fetching examples (sort={sort}, word_id={word_id}, page={page}, limit={limit})")
    paginated_data = crud.get_examples(
        db, sort=sort, word_id=word_id, page=page, limit=limit
    )
    logger.debug(
        f"[get_examples] Retrieved {len(paginated_data['items'])} examples")

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
    logger.debug(
        f"[toggle_example_active] Toggling active status for example {example_id}")
    example = crud.toggle_example_active(db, example_id)

    if not example:
        logger.warning(
            f"[toggle_example_active] Example {example_id} not found")
        raise HTTPException(status_code=404, detail="example not found")

    status = "activated" if example.is_active else "deactivated"
    logger.info(f"[toggle_example_active] Example {example_id} {status}")
    return {"message": f"example {status}"}


@router.patch("/{example_id}/toggle-fav")
def toggle_example_favorite(example_id: int, db: Session = Depends(get_db)):
    logger.debug(
        f"[toggle_example_favorite] Toggling favorite status for example {example_id}")
    example = crud.toggle_example_favorite(db, example_id)

    if not example:
        logger.warning(
            f"[toggle_example_favorite] Example {example_id} not found")
        raise HTTPException(status_code=404, detail="example not found")

    logger.info(
        f"[toggle_example_favorite] Example {example_id} marked as {'favorited' if example.is_favorite else 'not favorited'}")
    return {
        "id": example.id,
        "is_favorite": example.is_favorite,
        "message": f"example marked as {'favorited' if example.is_favorite else 'not favorited'}",
    }


@router.get("/explore", response_model=ExploreResponse)
def get_explore_feed(
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el lote actual de ejemplos/oraciones para el Explore,
    basado en la jerarquía de Lotes (Batch) y palabras prioritarias.
    """
    logger.info(
        f"[get_explore_feed] User {current_user.id}: Fetching explore feed (limit={limit})")

    # 1. Obtener ejemplos listos desde la cola de ejemplos (ExampleQueue) del usuario
    from sqlalchemy.orm import selectinload

    queued_items = db.exec(
        select(ExampleQueue)
        .where(
            ExampleQueue.user_id == current_user.id,
            ExampleQueue.status == QueueStatus.PENDING
        )
        .options(selectinload(ExampleQueue.example).selectinload(Example.example_words).selectinload(ExampleWord.word))
        .order_by(ExampleQueue.created_at.asc())
        .limit(limit)
    ).all()
    logger.info(
        f"[get_explore_feed] Found {len(queued_items)} queued items from queue")

    if queued_items:
        logger.info(f"[get_explore_feed] Queue items: {[item.id for item in queued_items]}")

    # Determinar si está generando
    is_generating = False

    # 2. Si la cola está vacía o tiene muy pocos elementos, ejecutamos el generador de emergencia
    if len(queued_items) < limit:
        # Obtenemos las palabras prioritarias respetando la lógica de Lotes + Transición
        refill_limit = crud.get_refill_queue_emergency_limit(db)
        manager = BatchManager(db)
        priority_words = manager.get_words_with_transition(
            user_id=current_user.id,
            featured_type=FeaturedType.EXAMPLE,
            limit=refill_limit
        )

        logger.info(
            f"[get_explore_feed] Found {len(priority_words)} priority words")

        if not priority_words:
            # El usuario no tiene palabras agregadas aún
            return ExploreResponse(
                examples=[],
                active_batch_id=None,
                active_batch_title=None,
                total_queue_remaining=0,
                status="ok"
            )

        # Generar o rellenar la cola en segundo plano vía Celery para que la API no se bloquee
        # Pero solo si no hay un refill ya en progreso
        is_refilling = crud.is_queue_refilling(
            db, current_user.id, QueueType.EXAMPLE)
        if is_refilling:
            logger.info(
                f"[get_explore_feed] Queue refill already in progress for user {current_user.id}. Skipping.")
            is_generating = True
        else:
            refill_queue_task.delay(user_id=current_user.id)
            is_generating = True

    # 3. Formatear los ejemplos recuperados de la cola
    formatted_examples: List[ExploreExampleSchema] = []

    for item in queued_items:
        example = item.example
        logger.info(
            f"Example {example.id}: example_words count = {len(example.example_words) if example.example_words else 0}")

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
            # Una palabra está aprendida solo si TODOS sus stats del tipo EXAMPLE están marcados como learned
            word_is_learned = all(stat.is_learned for stat in word.statistics if stat.type == FeaturedType.EXAMPLE) if word.statistics else False
            if not word_is_learned:
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
            logger.info(
                f"Example {example.id}: all its words are learned, marking as RESOLVED")
            item.status = QueueStatus.RESOLVED
            db.add(item)

    db.commit()

    # 4. Contar cuántos elementos quedan en la cola
    remaining_count = db.exec(
        select(func.count(ExampleQueue.id)).where(
            ExampleQueue.user_id == current_user.id)
    ).one() or 0

    logger.info(
        f"[get_explore_feed] Returning {len(formatted_examples)} examples. Remaining in queue: {remaining_count}. Status: {'generating' if is_generating else 'ok'}")
    return ExploreResponse(
        examples=formatted_examples,
        total_queue_remaining=remaining_count,
        status="generating" if is_generating else "ok"
    )


@router.patch("/{example_id}/resolve-pending")
def resolve_example_pending(example_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    logger.debug(
        f"[resolve_example_pending] User {current_user.id}: Resolving example {example_id}")
    example = crud.resolve_and_increment_example(
        db, example_id=example_id, user_id=current_user.id)

    if not example:
        logger.warning(
            f"[resolve_example_pending] Example {example_id} not found or not pending")
        raise HTTPException(
            status_code=404,
            detail="Example no encontrado o ya no estaba marcado como pendiente",
        )

    logger.info(
        f"[resolve_example_pending] Example {example_id} resolved. Times seen: {example.times_seen}")
    return {
        "id": example.id,
        "times_seen": example.times_seen,
        "message": "El ejemplo ya no está pendiente. Visualizaciones incrementadas con éxito.",
    }
