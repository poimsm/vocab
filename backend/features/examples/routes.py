
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import Optional, List
from pydantic import BaseModel
import json

from db import get_db
from logging_client import logger
from auth.repository import get_current_user
from auth.models import User
from features.examples.models import Example
from decorators import log_endpoint
from core.enums import ContentType
from features.examples.schemas import ExploreResponse, FavoritesResponse
from core.explore.explore_actions import ExploreActions
from features.examples.explore_response_builder import ExploreResponseBuilder
from features.examples.repository import ExampleRepository
from core.delivery.service import DeliveryService
from core.realtime_event_bus import get_realtime_bus
from celery_app import celery_app
from core.celery_queues import CeleryQueue
from features.examples.tasks import explore_examples_task
from core.sse_service import SSEStreamService, get_current_user_sse
from core.explore_endpoint_service import ExploreEndpointService


class ExploreRequest(BaseModel):
    """Request para el endpoint de explore con acciones encadenables."""
    actions: List[str] = ["next"]  # Acciones a ejecutar: ["resolve", "next"], ["next"], etc.
    resolve_queue_item_id: Optional[int] = None  # Requerido si actions incluye "resolve"
    limit: int = 5  # Para la acción "next"
    buffer_delivery_ids: List[int] = []  # IDs actuales del buffer
    buffer_position: int = 0  # Posición actual en el buffer


router = APIRouter()

# Servicio para endpoints de explore
explore_service = ExploreEndpointService(
    channel_prefix="examples_explore",
    feature_name="examples_explore",
    logger_name="[explore_examples]"
)


@router.get("/explore-stream")
async def explore_examples_stream(
    current_user: User = Depends(get_current_user_sse),
):
    """
    SSE endpoint que transmite eventos de exploración en tiempo real.

    Clients pueden conectarse así:
        const eventSource = new EventSource('/api/examples/explore-stream');
        eventSource.addEventListener('examples_explore.started', (event) => {
            const data = JSON.parse(event.data);
            console.log('Explore iniciado:', data);
        });
        eventSource.addEventListener('examples_explore.completed', (event) => {
            const data = JSON.parse(event.data);
            console.log('Explore completado:', data);
        });
        eventSource.addEventListener('examples_explore.failed', (event) => {
            const data = JSON.parse(event.data);
            console.log('Explore fallido:', data);
        });

    Eventos transmitidos:
        - examples_explore.started:   Exploración iniciada
        - examples_explore.processing: Procesando acciones
        - examples_explore.completed: Exploración completada (incluye buffer_ids, position, status)
        - examples_explore.failed:    Error durante exploración
    """
    logger.info(f"[explore_examples_stream] Iniciando SSE para user {current_user.id}")

    sse_service = SSEStreamService(
        user_id=current_user.id,
        channel_pattern=f"user:{current_user.id}:examples_explore.*",
        logger_name="[explore_examples_stream]"
    )

    return sse_service.get_stream_response()


@router.post("/explore")
@log_endpoint
def explore_examples(
    request: ExploreRequest,
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
        task=explore_examples_task
    )


@router.patch("/{example_id}/toggle-favorite")
@log_endpoint
def toggle_example_favorite(
    example_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Alterna el estado de favorito de un ejemplo.

    Cuando se marca como favorito:
    - Se resetea is_marked a False
    - Se actualiza favorited_at (aparecerá primero en listado)

    Retorna: is_favorite, is_marked, unmarked_favorites_count
    """
    logger.info(f"[toggle_example_favorite] User {current_user.id}: Toggling favorite for example {example_id}")

    example_repo = ExampleRepository(db)
    is_favorite = example_repo.toggle_favorite(current_user.id, example_id)

    # Obtener el ejemplo actualizado para devolver el estado is_marked
    example = db.exec(
        select(Example).where(Example.id == example_id)
    ).first()

    if not example:
        raise HTTPException(status_code=404, detail="Example not found")

    logger.debug(f"[toggle_example_favorite] Example {example_id} is_favorite: {is_favorite}, is_marked: {example.is_marked}")

    # Log de actividad
    from activity.user_activity_service import UserActivityService
    UserActivityService.log_button_click(
        db=db,
        user_id=current_user.id,
        button_name="toggle_example_favorite",
        details={
            "example_id": example_id,
            "is_favorite": is_favorite,
            "is_marked": example.is_marked
        }
    )

    # Obtener el contador actualizado de favoritos no marcados
    unmarked_count = example_repo.count_unmarked_favorites(current_user.id)

    return {
        "example_id": example_id,
        "is_favorite": is_favorite,
        "is_marked": example.is_marked,
        "unmarked_favorites_count": unmarked_count
    }


@router.patch("/{example_id}/toggle-marked")
@log_endpoint
def toggle_example_marked(
    example_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Alterna el estado de marcado de un ejemplo.

    Retorna el nuevo estado de is_marked.
    """
    logger.info(f"[toggle_example_marked] User {current_user.id}: Toggling marked status for example {example_id}")

    example_repo = ExampleRepository(db)
    is_marked = example_repo.toggle_marked(current_user.id, example_id)

    logger.debug(f"[toggle_example_marked] Example {example_id} is_marked: {is_marked}")

    # Log de actividad
    from activity.user_activity_service import UserActivityService
    UserActivityService.log_button_click(
        db=db,
        user_id=current_user.id,
        button_name="toggle_example_marked",
        details={
            "example_id": example_id,
            "is_marked": is_marked
        }
    )

    # Obtener el contador actualizado de favoritos no marcados
    example_repo = ExampleRepository(db)
    unmarked_count = example_repo.count_unmarked_favorites(current_user.id)

    return {
        "example_id": example_id,
        "is_marked": is_marked,
        "unmarked_favorites_count": unmarked_count
    }


@router.get("/favorites", response_model=FavoritesResponse)
@log_endpoint
def get_favorite_examples(
    page: int = 1,
    limit: int = 15,
    is_marked: Optional[bool] = None,
    sort_by: str = 'not_marked_first',
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene ejemplos marcados como favoritos con paginación.

    Parámetros:
    - page: Número de página
    - limit: Items por página
    - is_marked: Filtrar por estado de marcado (true/false/null) - DEPRECATED, usar sort_by
    - sort_by: Modo de ordenamiento ('done', 'random', 'not_marked_first')
        - 'done': Solo favoritos marcados
        - 'not_marked_first': Todos, primero no marcados
        - 'random': Solo no marcados en orden aleatorio

    Retorna:
    - items: Lista de ejemplos favoritos con texto segmentado
    - total: Total de ejemplos favoritos
    - page: Página actual
    - limit: Items por página
    - pages: Total de páginas
    - status: "ok"
    """
    logger.info(f"[get_favorite_examples] User {current_user.id}: Fetching favorite examples (page={page}, limit={limit}, is_marked={is_marked}, sort_by={sort_by})")

    # Log de actividad
    from activity.user_activity_service import UserActivityService
    UserActivityService.log_page_view(
        db=db,
        user_id=current_user.id,
        page_name="examples_favorites",
        details={
            "page": page,
            "limit": limit,
            "sort_by": sort_by
        }
    )

    example_repo = ExampleRepository(db)
    paginated_data = example_repo.get_examples(current_user.id, page=page, limit=limit, is_marked=is_marked, sort_by=sort_by)

    # Segmentar el texto de cada ejemplo
    examples_response = []
    for example in paginated_data["items"]:
        text_segments = example_repo.segment_example_text(example)
        extracted_words = []  # Por ahora vacío, se puede implementar después
        examples_response.append({
            "id": example.id,
            "text": text_segments,
            "extracted_words": extracted_words,
            "is_favorite": example.is_favorite,
            "is_marked": example.is_marked
        })

    logger.debug(f"[get_favorite_examples] Retrieved {len(examples_response)} favorite examples")

    return {
        "items": examples_response,
        "total": paginated_data["total"],
        "page": paginated_data["page"],
        "limit": paginated_data["limit"],
        "pages": paginated_data["pages"],
        "status": "ok"
    }


@router.get("/favorites/count")
@log_endpoint
def get_favorites_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el contador de ejemplos favoritos no marcados del usuario.

    Retorna:
    - count: Total de ejemplos donde is_favorite=True e is_marked=False
    - status: "ok"
    """
    logger.info(f"[get_favorites_count] User {current_user.id}: Fetching unmarked favorites count")

    example_repo = ExampleRepository(db)
    count = example_repo.count_unmarked_favorites(current_user.id)

    logger.debug(f"[get_favorites_count] User {current_user.id} has {count} unmarked favorites")

    return {
        "count": count,
        "status": "ok"
    }

