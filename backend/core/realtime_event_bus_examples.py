# backend/core/realtime_event_bus_examples.py
"""
Ejemplos de uso del RealtimeEventBus con FastAPI.

Uso: Copiar estas funciones a tus routes para integrar RealtimeEventBus.
"""

import json
import asyncio
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from core.realtime_event_bus import get_realtime_bus
from database import get_session

router = APIRouter(prefix="/api/realtime", tags=["realtime"])


# ============================================================================
# EJEMPLO 1: Endpoint SSE que escucha eventos en tiempo real
# ============================================================================

@router.get("/events/user/{user_id}")
async def stream_user_events(user_id: int):
    """
    Endpoint SSE que transmite eventos en tiempo real para un usuario.

    Clientes pueden conectarse así:
        const eventSource = new EventSource(`/api/realtime/events/user/123`);
        eventSource.onmessage = (event) => {
            const { channel, data } = JSON.parse(event.data);
            console.log(`Evento en ${channel}:`, data);
        };

    Eventos que se transmiten:
        - user:123:content.ready      → Contenido listo para mostrar
        - user:123:generation.start   → Generación de contenido iniciada
        - user:123:generation.done    → Generación de contenido completada
        - user:123:boost.applied      → Boost aplicado a una palabra
        - user:123:word.completed     → Palabra completada
    """
    realtime_bus = get_realtime_bus()
    event_queue = asyncio.Queue()

    def callback(channel: str, data: dict):
        """Callback que agrega eventos a la cola"""
        try:
            asyncio.create_task(event_queue.put({"channel": channel, "data": data}))
        except Exception as e:
            print(f"Error en callback: {e}")

    # Suscribirse a eventos del usuario (patrón: user:123:*)
    realtime_bus.subscribe(f"user:{user_id}:*", callback)

    async def event_generator():
        """Genera eventos SSE"""
        try:
            # Iniciar listener en background
            listener_thread = realtime_bus.listen_async()

            while True:
                try:
                    # Esperar por eventos (timeout para mantener conexión viva)
                    event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Enviar keep-alive comment
                    yield f": keep-alive\n\n"
        except GeneratorExit:
            # Cliente desconectado
            realtime_bus.unsubscribe(f"user:{user_id}:*")
            realtime_bus.stop()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ============================================================================
# EJEMPLO 2: Endpoint HTTP que dispara eventos (usado por otros workers)
# ============================================================================

@router.post("/trigger-content-ready/{user_id}")
async def trigger_content_ready(
    user_id: int,
    items: list = None,
    db: Session = Depends(get_session),
):
    """
    Endpoint HTTP que dispara un evento "content.ready".

    Puede ser llamado desde:
    - Otro worker (ej: worker_background que completa una generación)
    - El mismo worker después de procesar algo
    - Un servicio externo

    Uso:
        POST /api/realtime/trigger-content-ready/123
        {
            "items": [
                {"type": "example", "content": "..."},
                {"type": "phrase", "content": "..."}
            ]
        }
    """
    realtime_bus = get_realtime_bus()

    # Preparar datos del evento
    event_data = {
        "user_id": user_id,
        "items": items or [],
        "timestamp": asyncio.get_event_loop().time(),
    }

    # Publicar evento a todos los subscribers de este usuario
    subscribers = realtime_bus.publish(
        channel=f"user:{user_id}:content.ready",
        data=event_data,
    )

    return {
        "status": "published",
        "channel": f"user:{user_id}:content.ready",
        "subscribers": subscribers,
        "data": event_data,
    }


@router.post("/trigger-generation-start/{user_id}")
async def trigger_generation_start(user_id: int, content_type: str):
    """Dispara evento de inicio de generación."""
    realtime_bus = get_realtime_bus()

    event_data = {
        "user_id": user_id,
        "content_type": content_type,
        "status": "starting",
    }

    subscribers = realtime_bus.publish(
        channel=f"user:{user_id}:generation.start",
        data=event_data,
    )

    return {"status": "published", "subscribers": subscribers}


@router.post("/trigger-generation-done/{user_id}")
async def trigger_generation_done(user_id: int, content_type: str, success: bool = True):
    """Dispara evento de finalización de generación."""
    realtime_bus = get_realtime_bus()

    event_data = {
        "user_id": user_id,
        "content_type": content_type,
        "success": success,
    }

    channel = "generation.done" if success else "generation.failed"
    subscribers = realtime_bus.publish(
        channel=f"user:{user_id}:{channel}",
        data=event_data,
    )

    return {"status": "published", "subscribers": subscribers}


# ============================================================================
# EJEMPLO 3: Listener en background (para procesar eventos en workers)
# ============================================================================

class RealtimeEventListener:
    """
    Clase para escuchar eventos en background dentro de un worker.

    Uso en backend/main.py o un archivo de inicialización:
        listener = RealtimeEventListener()
        listener.start()

    O en un endpoint de health check:
        @app.get("/health/realtime")
        def health_check():
            return listener.is_running()
    """

    def __init__(self):
        self.realtime_bus = get_realtime_bus()
        self.is_running_flag = False

    def start(self):
        """Inicia el listener en un thread separado."""
        if self.is_running_flag:
            print("Listener ya está corriendo")
            return

        # Registrar callbacks para eventos específicos
        self.realtime_bus.subscribe("*:generation.done", self._on_generation_done)
        self.realtime_bus.subscribe("*:content.ready", self._on_content_ready)
        self.realtime_bus.subscribe("*:boost.applied", self._on_boost_applied)

        # Iniciar listener en background
        self.realtime_bus.listen_async()
        self.is_running_flag = True
        print("RealtimeEventListener iniciado")

    def stop(self):
        """Detiene el listener."""
        self.realtime_bus.stop()
        self.is_running_flag = False
        print("RealtimeEventListener detenido")

    def is_running(self):
        """Retorna si el listener está activo."""
        return self.is_running_flag and self.realtime_bus.health_check()

    def _on_generation_done(self, channel: str, data: dict):
        """Callback: procesamiento cuando generación termina."""
        print(f"[GENERATION DONE] {channel}: {data}")
        # Aquí puedes agregar lógica adicional
        # Ej: actualizar BD, disparar más eventos, etc.

    def _on_content_ready(self, channel: str, data: dict):
        """Callback: procesamiento cuando contenido está listo."""
        print(f"[CONTENT READY] {channel}: {data}")

    def _on_boost_applied(self, channel: str, data: dict):
        """Callback: procesamiento cuando boost es aplicado."""
        print(f"[BOOST APPLIED] {channel}: {data}")


# ============================================================================
# EJEMPLO 4: Cómo llamar desde otro worker
# ============================================================================

def example_worker_usage():
    """
    Ejemplo de cómo usar RealtimeEventBus desde un worker (Celery task).

    Útil para disparar eventos después de completar tareas background.
    """
    from core.realtime_event_bus import get_realtime_bus

    # Esta función sería una Celery task en backend/core/generation_ai/tasks.py
    realtime_bus = get_realtime_bus()

    # Simulación de procesamiento
    user_id = 123
    content_type = "examples"

    # 1. Notificar que comienza la generación
    realtime_bus.publish(
        channel=f"user:{user_id}:generation.start",
        data={"content_type": content_type, "status": "starting"},
    )

    # 2. Hacer procesamiento pesado aquí...
    # (generación de contenido, etc.)

    # 3. Notificar que terminó con éxito
    realtime_bus.publish(
        channel=f"user:{user_id}:generation.done",
        data={
            "content_type": content_type,
            "success": True,
            "items_generated": 5,
        },
    )

    # 4. O si falla:
    # realtime_bus.publish(
    #     channel=f"user:{user_id}:generation.failed",
    #     data={"content_type": content_type, "error": "..."}
    # )


# ============================================================================
# EJEMPLO 5: Eventos de canales específicos (no SSE)
# ============================================================================

@router.post("/dispatch-event/{channel}")
async def dispatch_event(channel: str, data: dict):
    """
    Endpoint genérico para disparar eventos a un canal específico.

    Uso:
        POST /api/realtime/dispatch-event/user:123:custom.event
        {
            "message": "Esto es un evento personalizado",
            "metadata": {...}
        }
    """
    realtime_bus = get_realtime_bus()
    subscribers = realtime_bus.publish(channel=channel, data=data)
    return {"status": "published", "channel": channel, "subscribers": subscribers}


@router.get("/health")
def realtime_health_check():
    """Health check para el RealtimeEventBus."""
    realtime_bus = get_realtime_bus()
    is_healthy = realtime_bus.health_check()
    return {
        "realtime_bus": "healthy" if is_healthy else "unhealthy",
        "redis_connected": is_healthy,
    }
