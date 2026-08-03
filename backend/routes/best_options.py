import collections
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select, func

import crud
from db import get_db
from logging_config import logger
from tasks.best_options import refill_best_options_queue_task
from auth import get_current_user
from models import User, BestOption, BestOptionQueue, QueueStatus, QueueType, ExampleType, ExampleWord

router = APIRouter()


@router.get("/explore")
def get_best_options(
    limit: int = 6,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene ejercicios best_option desde la cola del usuario.
    - Si hay ejercicios PENDING, devuelve hasta 'limit' ejercicios
    - Cambia su estado de PENDING a SENT
    - Si hay menos de 'limit', dispara la tarea de refill en background
    """
    logger.info(f"[get_best_options] User {current_user.id}: Fetching best options (limit={limit})")

    # 1. Obtener ejercicios PENDING de la cola del usuario
    from models import Word, Example
    pending_items = db.exec(
        select(BestOptionQueue)
        .where(
            BestOptionQueue.user_id == current_user.id,
            BestOptionQueue.status == QueueStatus.PENDING,
            BestOptionQueue.is_active == True
        )
        .options(
            joinedload(BestOptionQueue.best_option).joinedload(BestOption.word).joinedload(Word.example_words).joinedload(ExampleWord.example)
        )
        .order_by(BestOptionQueue.created_at.asc())
        .limit(limit)
    ).unique().all()

    logger.debug(f"[get_best_options] Found {len(pending_items)} pending items from queue")

    # 2. Determinar estado y disparar refill si es necesario
    is_refilling = crud.is_queue_refilling(db, current_user.id, QueueType.BEST_OPTION)

    if len(pending_items) < limit and not is_refilling:
        logger.info(f"[get_best_options] Queue has {len(pending_items)} items, less than {limit}. Triggering refill task.")
        refill_best_options_queue_task.delay(user_id=current_user.id)
        is_refilling = True  # Acaba de dispararse

    # 3. Cambiar estado de PENDING a SENT para los ejercicios que se van a devolver
    for item in pending_items:
        item.status = QueueStatus.SENT
        db.add(item)
    db.commit()

    # 4. Formatear los ejercicios para la respuesta
    formatted_options = []
    for item in pending_items:
        best_option = item.best_option
        word = best_option.word
        # Las opciones están separadas por ";" en el modelo
        options_list = best_option.options.split(";")

        # Obtener ejemplos de tipo INITIAL de la palabra
        initial_examples = []
        if word.example_words:
            for ew in word.example_words:
                example = ew.example
                if example and example.type == ExampleType.INITIAL and example.is_active:
                    initial_examples.append({
                        "id": example.id,
                        "text": example.text,
                        "is_favorite": example.is_favorite
                    })

        formatted_options.append({
            "id": best_option.id,
            "queue_item_id": item.id,
            "sequence_order": best_option.sequence_order,
            "word": {
                "id": word.id,
                "main": word.main,
                "meaning": word.meaning,
                "type": word.type,
                "level": word.level,
                "synonyms": word.synonyms,
                "frequency": word.frequency,
                "examples": initial_examples,
            },
            "question": best_option.question,
            "options": options_list,
            "correct_option": best_option.correct_option
        })

    # 5. Contar cuántos elementos quedan en la cola
    remaining_count = db.exec(
        select(func.count(BestOptionQueue.id)).where(
            BestOptionQueue.user_id == current_user.id,
            BestOptionQueue.status == QueueStatus.PENDING
        )
    ).one() or 0

    # Determinar el estado de la respuesta
    if len(formatted_options) > 0:
        status = "ok"
    elif is_refilling:
        status = "generating"
    else:
        status = "no_words"

    logger.info(f"[get_best_options] Returning {len(formatted_options)} best options. Remaining in queue: {remaining_count}. Status: {status}")

    return {
        "best_options": formatted_options,
        "total_queue_remaining": remaining_count,
        "status": status
    }


@router.patch("/{queue_item_id}/resolve")
def resolve_best_option(
    queue_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza el estado de un best_option de SENT a RESOLVED.
    Auto-encola el siguiente ejercicio de la misma palabra si existe.
    """
    logger.debug(f"[resolve_best_option] User {current_user.id}: Resolving best option queue item {queue_item_id}")

    # Buscar el item en la cola
    queue_item = db.exec(
        select(BestOptionQueue)
        .where(
            BestOptionQueue.id == queue_item_id,
            BestOptionQueue.user_id == current_user.id,
            BestOptionQueue.status == QueueStatus.SENT,
            BestOptionQueue.is_active == True
        )
        .options(joinedload(BestOptionQueue.best_option))
    ).first()

    if not queue_item:
        logger.warning(f"[resolve_best_option] Queue item {queue_item_id} not found or not in SENT status")
        raise HTTPException(
            status_code=404,
            detail="Best option queue item not found or not in SENT status"
        )

    # Obtener información del best_option
    best_option = queue_item.best_option
    word_id = best_option.word_id
    current_sequence = best_option.sequence_order

    # Cambiar estado a RESOLVED
    queue_item.status = QueueStatus.RESOLVED
    db.add(queue_item)
    db.commit()

    # Auto-encolar el siguiente ejercicio de la misma palabra (si existe)
    next_queue_item = crud.enqueue_next_best_option_for_word(
        db, current_user.id, word_id, current_sequence
    )

    logger.info(f"[resolve_best_option] Queue item {queue_item_id} resolved successfully")

    return {
        "id": queue_item_id,
        "status": "resolved",
        "message": "Best option exercise resolved successfully",
        "next_enqueued": next_queue_item is not None
    }