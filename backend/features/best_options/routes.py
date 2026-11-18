from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import Optional, List
from pydantic import BaseModel

from db import get_db
from logging_client import logger
from auth.repository import get_current_user
from auth.models import User
from decorators import log_endpoint
from core.celery_queues import CeleryQueue
from features.best_options.tasks import explore_best_options_task
from core.explore_endpoint_service import ExploreEndpointService
from core.explore_task_redis_service import ExploreTaskRedisService


class BestOptionExploreRequest(BaseModel):
    """Request para el endpoint de explore con acciones encadenables."""
    actions: List[str] = ["next"]  # Acciones a ejecutar: ["resolve", "next"], ["next"], etc.
    resolve_queue_item_id: Optional[int] = None  # Requerido si actions incluye "resolve"
    limit: int = 6  # Para la acción "next"
    buffer_delivery_ids: List[int] = []  # IDs actuales del buffer
    buffer_position: int = 0  # Posición actual en el buffer


router = APIRouter()

# Servicio para endpoints de explore
explore_service = ExploreEndpointService(
    channel_prefix="best_options_explore",
    feature_name="best_options_explore",
    logger_name="[explore_best_options]"
)


@router.get("/explore/status/{request_id}")
@log_endpoint
def get_explore_status(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el status de una tarea explore consultando Redis.

    Returns:
        {
            "request_id": str,
            "status": "processing" | "completed" | "failed",
            "message": str,
            "timestamp": float
        }
    """
    logger.info(f"[get_explore_status] User {current_user.id}: Checking status for request {request_id}")

    status_data = ExploreTaskRedisService.get_status(request_id)

    if not status_data:
        raise HTTPException(status_code=404, detail="Request not found or expired")

    return {
        "request_id": request_id,
        **status_data
    }


@router.get("/explore/results/{request_id}")
@log_endpoint
def get_explore_results(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene los resultados de una tarea explore consultando Redis y Postgres.

    Returns:
        {
            "request_id": str,
            "status": str,
            "buffer_delivery_ids": list[int],
            "buffer_position": int,
            "best_options": list[dict],
            "best_options_count": int,
            "timestamp": float
        }
    """
    logger.info(f"[get_explore_results] User {current_user.id}: Fetching results for request {request_id}")

    # Obtener resultados desde Redis
    results = ExploreTaskRedisService.get_results(request_id)

    if not results:
        raise HTTPException(status_code=404, detail="Results not found or expired")

    return {
        "request_id": request_id,
        **results
    }


@router.post("/explore")
@log_endpoint
def explore_best_options(
    request: BestOptionExploreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint que encola acciones de explore para procesamiento asincrónico.

    Responde inmediatamente con confirmación. Los resultados se transmiten
    a través del SSE endpoint `/explore-stream` usando el RealtimeEventBus.

    Acciones disponibles:
    - "resolve": Resuelve un item (registra exposición) - requiere resolve_queue_item_id
    - "sync": Solo sincroniza la posición actual (sin tocar el buffer)
    - "sync-buffer": Valida y refill el buffer (para llenar después de marcar palabra como learned)
    - "resume": Resume sesión - carga nuevo buffer si todos fueron visitados, sino continúa
    - "next": Descarta buffer completamente, limpia visitados, carga nuevos items y posición=0

    Flow:
    1. Frontend → POST /explore con acciones
    2. Este endpoint → Responde inmediatamente con request_id
    3. Este endpoint → Encola task de background que ejecuta acciones
    4. Background task → Publica eventos a RealtimeEventBus
    5. Frontend → GET /explore-stream (SSE) → Recibe eventos en tiempo real
    """
    return explore_service.process_explore_request(
        db=db,
        current_user=current_user,
        request_data={
            "actions": request.actions,
            "resolve_queue_item_id": request.resolve_queue_item_id,
            "limit": request.limit,
            "buffer_delivery_ids": request.buffer_delivery_ids,
            "buffer_position": request.buffer_position,
        },
        task=explore_best_options_task
    )
