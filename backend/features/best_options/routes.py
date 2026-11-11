from fastapi import APIRouter, Depends
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
from core.sse_service import SSEStreamService, get_current_user_sse
from core.explore_endpoint_service import ExploreEndpointService


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


@router.get("/explore-stream")
async def explore_best_options_stream(
    current_user: User = Depends(get_current_user_sse),
):
    """
    SSE endpoint que transmite eventos de exploración en tiempo real.

    Clients pueden conectarse así:
        const eventSource = new EventSource('/api/best-options/explore-stream');
        eventSource.addEventListener('best_options_explore.started', (event) => {
            const data = JSON.parse(event.data);
            console.log('Explore iniciado:', data);
        });
        eventSource.addEventListener('best_options_explore.completed', (event) => {
            const data = JSON.parse(event.data);
            console.log('Explore completado:', data);
        });
        eventSource.addEventListener('best_options_explore.failed', (event) => {
            const data = JSON.parse(event.data);
            console.log('Explore fallido:', data);
        });

    Eventos transmitidos:
        - best_options_explore.started:   Exploración iniciada
        - best_options_explore.processing: Procesando acciones
        - best_options_explore.completed: Exploración completada (incluye buffer_ids, position, status)
        - best_options_explore.failed:    Error durante exploración
    """
    logger.info(f"[explore_best_options_stream] Iniciando SSE para user {current_user.id}")

    sse_service = SSEStreamService(
        user_id=current_user.id,
        channel_pattern=f"user:{current_user.id}:best_options_explore.*",
        logger_name="[explore_best_options_stream]"
    )

    return sse_service.get_stream_response()


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
