
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import Optional, List
from pydantic import BaseModel
import json
import uuid
import queue
import time
import asyncio
import jwt
from jwt import PyJWTError

from db import get_db
from logging_client import logger
from auth.repository import get_current_user, SECRET_KEY, ALGORITHM
from auth.models import User
from features.examples.models import Example
from decorators import log_endpoint
from core.enums import ContentType
from features.examples.schemas import ExploreResponse, FavoritesResponse
from core.explore.explore_actions import ExploreActions
from features.examples.explore_response_builder import ExploreResponseBuilder
from features.examples.repository import ExampleRepository
from core.delivery.service import DeliveryService
from activity.user_activity_service import UserActivityService
from core.realtime_event_bus import get_realtime_bus
from celery_app import celery_app
from core.celery_queues import CeleryQueue
from features.examples.tasks import explore_examples_task


class ExploreRequest(BaseModel):
    """Request para el endpoint de explore con acciones encadenables."""
    actions: List[str] = ["next"]  # Acciones a ejecutar: ["resolve", "next"], ["next"], ["sync"], etc.
    resolve_queue_item_id: Optional[int] = None  # Requerido si actions incluye "resolve"
    limit: int = 5  # Para la acción "next"
    buffer_delivery_ids: List[int] = []  # IDs actuales del buffer
    buffer_position: int = 0  # Posición actual en el buffer


async def get_current_user_sse(
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None),  # Token como query parameter (para SSE)
) -> User:
    """
    Autenticación para SSE endpoint.
    Intenta obtener el usuario del token en query param (para SSE que no soporta headers)
    o usa la autenticación estándar.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Si hay token en query param, usarlo
    if token:
        logger.debug(f"[SSE Auth] Attempting to authenticate via query token")
        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM]
            )
            email: str = payload.get("sub")
            if email is None:
                logger.warning("[SSE Auth] Token validation failed: no email in payload")
                raise credentials_exception

            user = db.exec(
                select(User).where(User.email == email)
            ).first()

            if user is None:
                logger.warning(f"[SSE Auth] User not found for email: {email}")
                raise credentials_exception

            logger.debug(f"[SSE Auth] User authenticated via query token: {user.id} ({email})")
            return user

        except PyJWTError as e:
            logger.warning(f"[SSE Auth] JWT validation error: {str(e)}")
            raise credentials_exception
        except Exception as e:
            logger.error(f"[SSE Auth] Unexpected error: {str(e)}", exc_info=True)
            raise credentials_exception

    # Si no hay token en query param, usar autenticación estándar (header)
    logger.debug("[SSE Auth] No query token, falling back to standard auth")
    return get_current_user(token=None, db=db)


router = APIRouter()


@router.get("/explore-stream")
async def explore_examples_stream(
    current_user: User = Depends(get_current_user_sse),
):
    """
    SSE endpoint que transmite eventos de exploración en tiempo real.

    Clients pueden conectarse así:
        const eventSource = new EventSource('/api/examples/explore-stream');
        eventSource.addEventListener('explore.started', (event) => {
            const data = JSON.parse(event.data);
            console.log('Explore iniciado:', data);
        });
        eventSource.addEventListener('explore.completed', (event) => {
            const data = JSON.parse(event.data);
            console.log('Explore completado:', data);
        });
        eventSource.addEventListener('explore.failed', (event) => {
            const data = JSON.parse(event.data);
            console.log('Explore fallido:', data);
        });

    Eventos transmitidos:
        - explore.started:   Exploración iniciada
        - explore.processing: Procesando acciones
        - explore.completed: Exploración completada (incluye buffer_ids, position, status)
        - explore.failed:    Error durante exploración
    """
    import redis
    import os
    import time

    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))

    logger.info(f"[explore_examples_stream] Iniciando SSE para user {current_user.id}")

    # Conexión Redis para escuchar eventos
    try:
        r = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=0,
            decode_responses=True,
            socket_timeout=2,
        )
        pubsub = r.pubsub()
        pubsub.psubscribe(f"user:{current_user.id}:explore.*")
        logger.info(f"[explore_examples_stream] Suscrito a eventos de user {current_user.id}")
    except Exception as e:
        logger.error(f"[explore_examples_stream] Redis connection error: {e}")
        return StreamingResponse(
            iter([f"event: error\ndata: {json.dumps({'error': 'Redis connection failed'})}\n\n"]),
            media_type="text/event-stream",
            status_code=500
        )

    async def event_generator():
        """Genera eventos SSE usando Redis pubsub"""
        try:
            logger.debug(f"[explore_examples_stream] Event generator iniciado")
            last_keep_alive = time.time()

            while True:
                try:
                    # Usar get_message() no-bloqueante con timeout muy corto
                    message = pubsub.get_message()

                    if message and message.get("type") in ("message", "pmessage"):
                        channel = message.get("channel")
                        raw_data = message.get("data")

                        if channel and raw_data:
                            try:
                                data = json.loads(raw_data)
                                event_type = channel.split(":")[-1]
                                yield f"event: {event_type}\n"
                                yield f"data: {json.dumps(data)}\n\n"
                                logger.debug(f"[explore_examples_stream] Evento enviado: {event_type}")
                                last_keep_alive = time.time()
                            except json.JSONDecodeError:
                                logger.error(f"Invalid JSON: {raw_data}")
                    else:
                        # Keep-alive cada 30 segundos sin eventos
                        now = time.time()
                        if now - last_keep_alive > 30:
                            yield ": keep-alive\n\n"
                            last_keep_alive = now
                        else:
                            # Pequeña pausa para no consumir CPU
                            await asyncio.sleep(0.2)

                except Exception as e:
                    logger.error(f"[explore_examples_stream] Error en generador: {e}")
                    yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                    break

        except GeneratorExit:
            logger.debug(f"[explore_examples_stream] Cliente desconectado")
        finally:
            try:
                pubsub.close()
            except:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
    request_id = str(uuid.uuid4())

    logger.info(
        f"[explore_examples] User {current_user.id}: request_id={request_id}, "
        f"actions={request.actions}, limit={request.limit}, buffer_size={len(request.buffer_delivery_ids)}"
    )

    # Log detallado del request para debugging
    logger.info(
        f"[explore_examples] DETAILED REQUEST: "
        f"resolve_queue_item_id={request.resolve_queue_item_id} "
        f"(type={type(request.resolve_queue_item_id).__name__}), "
        f"actions={request.actions}, "
        f"buffer_delivery_ids={request.buffer_delivery_ids}, "
        f"buffer_position={request.buffer_position}"
    )

    # Log de actividad
    UserActivityService.log_feature_interaction(
        db=db,
        user_id=current_user.id,
        feature_name="examples_explore",
        interaction_type="_".join(request.actions),
        details={
            "actions": request.actions,
            "limit": request.limit,
            "buffer_size": len(request.buffer_delivery_ids),
            "request_id": request_id
        }
    )

    # Publicar evento inicial de inicio de exploración
    realtime_bus = get_realtime_bus()
    realtime_bus.publish(
        channel=f"user:{current_user.id}:explore.started",
        data={
            "request_id": request_id,
            "actions": request.actions,
            "timestamp": time.time(),
        }
    )

    # Encolar tarea de background para ejecutar acciones
    explore_examples_task.apply_async(
        args=[current_user.id],
        kwargs={
            "request_id": request_id,
            "actions": request.actions,
            "resolve_queue_item_id": request.resolve_queue_item_id,
            "limit": request.limit,
            "buffer_delivery_ids": request.buffer_delivery_ids,
            "buffer_position": request.buffer_position,
        },
        queue=CeleryQueue.BACKGROUND,
    )

    return {
        "status": "ok",
        "request_id": request_id,
        "message": "Explore request enqueued. Results will be streamed via /explore-stream"
    }


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

