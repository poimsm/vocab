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
from models import User, BestOption, BestOptionQueue, QueueStatus

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
    pending_items = db.exec(
        select(BestOptionQueue)
        .where(
            BestOptionQueue.user_id == current_user.id,
            BestOptionQueue.status == QueueStatus.PENDING,
            BestOptionQueue.is_active == True
        )
        .options(joinedload(BestOptionQueue.best_option))
        .order_by(BestOptionQueue.created_at.asc())
        .limit(limit)
    ).unique().all()

    logger.debug(f"[get_best_options] Found {len(pending_items)} pending items from queue")

    # 2. Si hay menos de 'limit' ejercicios, dispara la tarea de refill en background
    if len(pending_items) < limit:
        logger.info(f"[get_best_options] Queue has {len(pending_items)} items, less than {limit}. Triggering refill task.")
        refill_best_options_queue_task.delay(user_id=current_user.id)

    # 3. Cambiar estado de PENDING a SENT para los ejercicios que se van a devolver
    for item in pending_items:
        item.status = QueueStatus.SENT
        db.add(item)
    db.commit()

    # 4. Formatear los ejercicios para la respuesta
    formatted_options = []
    for item in pending_items:
        best_option = item.best_option
        # Las opciones están separadas por ";" en el modelo
        options_list = best_option.options.split(";")

        formatted_options.append({
            "id": best_option.id,
            "queue_item_id": item.id,
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

    logger.info(f"[get_best_options] Returning {len(formatted_options)} best options. Remaining in queue: {remaining_count}")

    return {
        "best_options": formatted_options,
        "total_queue_remaining": remaining_count,
        "status": "generating" if len(pending_items) < limit else "ok"
    }


@router.patch("/{queue_item_id}/resolve")
def resolve_best_option(
    queue_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza el estado de un best_option de SENT a RESOLVED.
    """
    logger.debug(f"[resolve_best_option] User {current_user.id}: Resolving best option queue item {queue_item_id}")

    # Buscar el item en la cola
    queue_item = db.exec(
        select(BestOptionQueue).where(
            BestOptionQueue.id == queue_item_id,
            BestOptionQueue.user_id == current_user.id,
            BestOptionQueue.status == QueueStatus.SENT,
            BestOptionQueue.is_active == True
        )
    ).first()

    if not queue_item:
        logger.warning(f"[resolve_best_option] Queue item {queue_item_id} not found or not in SENT status")
        raise HTTPException(
            status_code=404,
            detail="Best option queue item not found or not in SENT status"
        )

    # Cambiar estado a RESOLVED
    queue_item.status = QueueStatus.RESOLVED
    db.add(queue_item)
    db.commit()

    logger.info(f"[resolve_best_option] Queue item {queue_item_id} resolved successfully")
    return {
        "id": queue_item_id,
        "status": "resolved",
        "message": "Best option exercise resolved successfully"
    }