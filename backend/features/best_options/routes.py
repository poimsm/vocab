from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import Optional, List
from pydantic import BaseModel
import json
import uuid
import time
import asyncio
import jwt
from jwt import PyJWTError

from db import get_db
from logging_client import logger
from auth.repository import get_current_user, SECRET_KEY, ALGORITHM
from auth.models import User
from decorators import log_endpoint
from core.enums import ContentType
from features.best_options.schemas import BestOptionResponse, ExploreAckResponse
from core.explore.explore_actions import ExploreActions
from features.best_options.response_builder import BestOptionsResponseBuilder
from activity.user_activity_service import UserActivityService
from features.examples.repository import ExampleRepository
from core.delivery.service import DeliveryService
from core.realtime_event_bus import get_realtime_bus
from celery_app import celery_app
from core.celery_queues import CeleryQueue
from features.best_options.tasks import explore_best_options_task


class BestOptionExploreRequest(BaseModel):
    """Request para el endpoint de explore con acciones encadenables."""
    actions: List[str] = ["next"]  # Acciones a ejecutar: ["resolve", "next"], ["next"], etc.
    resolve_queue_item_id: Optional[int] = None  # Requerido si actions incluye "resolve"
    limit: int = 6  # Para la acción "next"
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
    import redis
    import os

    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))

    logger.info(f"[explore_best_options_stream] Iniciando SSE para user {current_user.id}")

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
        pubsub.psubscribe(f"user:{current_user.id}:best_options_explore.*")
        logger.info(f"[explore_best_options_stream] Suscrito a eventos de user {current_user.id}")
    except Exception as e:
        logger.error(f"[explore_best_options_stream] Redis connection error: {e}")
        return StreamingResponse(
            iter([f"event: error\ndata: {json.dumps({'error': 'Redis connection failed'})}\n\n"]),
            media_type="text/event-stream",
            status_code=500
        )

    async def event_generator():
        """Genera eventos SSE usando Redis pubsub"""
        try:
            logger.debug(f"[explore_best_options_stream] Event generator iniciado")
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
                                logger.debug(f"[explore_best_options_stream] Evento enviado: {event_type}")
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
                    logger.error(f"[explore_best_options_stream] Error en generador: {e}")
                    yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                    break

        except GeneratorExit:
            logger.debug(f"[explore_best_options_stream] Cliente desconectado")
        finally:
            try:
                pubsub.close()
            except:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/explore", response_model=ExploreAckResponse)
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
    request_id = str(uuid.uuid4())

    logger.info(
        f"[explore_best_options] User {current_user.id}: request_id={request_id}, "
        f"actions={request.actions}, limit={request.limit}, buffer_size={len(request.buffer_delivery_ids)}"
    )

    # Log detallado del request para debugging
    logger.info(
        f"[explore_best_options] DETAILED REQUEST: "
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
        feature_name="best_options_explore",
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
        channel=f"user:{current_user.id}:best_options_explore.started",
        data={
            "request_id": request_id,
            "actions": request.actions,
            "timestamp": time.time(),
        }
    )

    # Encolar tarea de background para ejecutar acciones
    explore_best_options_task.apply_async(
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

