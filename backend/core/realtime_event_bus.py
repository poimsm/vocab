# backend/core/realtime_event_bus.py
"""
RealtimeEventBus para arquitectura pub/sub con Redis.
Permite comunicación síncrona/en tiempo real entre múltiples workers sin dependencia de memoria.

Diferencia con event_bus.py (RabbitMQ + Celery):
- event_bus.py: Para tareas asincrónicas/background (generación, procesamiento pesado)
- realtime_event_bus.py: Para eventos en tiempo real entre workers (SSE, notificaciones live)

Uso:
    # Publicar evento (desde cualquier worker)
    realtime_bus = RealtimeEventBus()
    realtime_bus.publish("user:123:content.ready", {"items": [...]})

    # Suscribirse a evento (en background)
    def handle_content_ready(channel: str, data: dict):
        print(f"Nuevo contenido en {channel}: {data}")

    realtime_bus.subscribe("user:123:content.ready", handle_content_ready)
    realtime_bus.subscribe("user:123:*", handle_content_ready)  # Patrón

    # En endpoint SSE
    @app.get("/events/user/{user_id}")
    async def stream_events(user_id: int):
        async def event_generator():
            realtime_bus = RealtimeEventBus()
            def callback(channel: str, data: dict):
                yield f"data: {json.dumps({'channel': channel, 'data': data})}\n\n"

            realtime_bus.subscribe(f"user:{user_id}:*", callback)
            realtime_bus.listen()

        return StreamingResponse(event_generator(), media_type="text/event-stream")
"""

import json
import redis
import threading
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass
from logging_client import logger
import os


@dataclass
class SubscriptionHandler:
    channel_pattern: str
    callback: Callable
    thread: Optional[threading.Thread] = None
    active: bool = True


class RealtimeEventBus:
    """Bus de eventos en tiempo real usando Redis pub/sub."""

    def __init__(self, redis_host: str = None, redis_port: int = None, redis_db: int = 0):
        """
        Inicializa el RealtimeEventBus.

        Args:
            redis_host: Host de Redis (por defecto: env REDIS_HOST o 'redis')
            redis_port: Puerto de Redis (por defecto: env REDIS_PORT o 6379)
            redis_db: Base de datos de Redis (por defecto: 0)
        """
        self.redis_host = redis_host or os.getenv("REDIS_HOST", "redis")
        self.redis_port = redis_port or int(os.getenv("REDIS_PORT", 6379))
        self.redis_db = redis_db

        try:
            self.client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
            )
            # Verificar conexión
            self.client.ping()
            logger.info(f"RealtimeEventBus conectado a Redis en {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.error(f"Error conectando a Redis: {e}")
            raise

        self.pubsub = self.client.pubsub()
        self.subscriptions: Dict[str, SubscriptionHandler] = {}
        self._listener_thread: Optional[threading.Thread] = None

    def publish(self, channel: str, data: dict) -> int:
        """
        Publica un evento a un canal.

        Args:
            channel: Nombre del canal (ej: "user:123:content.ready")
            data: Datos del evento (se serializa a JSON)

        Returns:
            Número de subscribers que recibieron el mensaje
        """
        try:
            message = json.dumps(data)
            subscribers_count = self.client.publish(channel, message)
            logger.info(f"Evento publicado en '{channel}' para {subscribers_count} subscribers")
            return subscribers_count
        except TypeError as e:
            logger.error(
                f"Error de serialización JSON al publicar evento en '{channel}': {e}\n"
                f"Data type: {type(data)}\n"
                f"Data keys: {data.keys() if isinstance(data, dict) else 'N/A'}\n"
                f"Data: {str(data)[:500]}...",
                exc_info=True
            )
            # Intentar de nuevo con default=str para convertir objetos no serializables
            try:
                logger.info(f"Reintentando publicar evento en '{channel}' con serialización flexible")
                message = json.dumps(data, default=str)
                subscribers_count = self.client.publish(channel, message)
                logger.info(f"Evento publicado (con conversion a str) en '{channel}' para {subscribers_count} subscribers")
                return subscribers_count
            except Exception as retry_error:
                logger.error(f"Falló reintento de publicación en '{channel}': {retry_error}")
                return 0
        except Exception as e:
            logger.error(f"Error publicando evento en '{channel}': {e}", exc_info=True)
            return 0

    def subscribe(self, channel_pattern: str, callback: Callable) -> None:
        """
        Se suscribe a un canal o patrón.

        Args:
            channel_pattern: Canal o patrón (ej: "user:123:*", "user:123:content.ready")
            callback: Función que se llama cuando llega un evento
                      Firma: callback(channel: str, data: dict)
        """
        if channel_pattern in self.subscriptions:
            logger.warning(f"Ya existe suscripción para '{channel_pattern}'")
            return

        handler = SubscriptionHandler(channel_pattern=channel_pattern, callback=callback)
        self.subscriptions[channel_pattern] = handler
        logger.info(f"Suscripción registrada para '{channel_pattern}'")

    def unsubscribe(self, channel_pattern: str) -> None:
        """
        Se desuscribe de un canal o patrón.

        Args:
            channel_pattern: Canal o patrón a desuscribirse
        """
        if channel_pattern in self.subscriptions:
            handler = self.subscriptions[channel_pattern]
            handler.active = False
            del self.subscriptions[channel_pattern]
            logger.info(f"Suscripción removida para '{channel_pattern}'")

    def listen(self) -> None:
        """
        Inicia a escuchar eventos en los canales suscritos.
        Bloquea el hilo hasta que se llame a stop().
        """
        if not self.subscriptions:
            logger.warning("No hay suscripciones activas")
            return

        try:
            # Suscribirse a todos los patrones en Redis
            for channel_pattern in self.subscriptions.keys():
                if "*" in channel_pattern:
                    self.pubsub.psubscribe(channel_pattern)
                else:
                    self.pubsub.subscribe(channel_pattern)
                logger.info(f"Escuchando en '{channel_pattern}'")

            # Escuchar mensajes
            for message in self.pubsub.listen():
                if message["type"] in ("message", "pmessage"):
                    channel = message.get("channel")
                    raw_data = message.get("data")

                    if channel and raw_data:
                        try:
                            data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            data = {"raw": raw_data}

                        # Encontrar el handler que coincida
                        handler = self._match_handler(channel)
                        if handler and handler.active:
                            try:
                                handler.callback(channel, data)
                            except Exception as e:
                                logger.error(f"Error en callback para '{channel}': {e}")

        except Exception as e:
            logger.error(f"Error escuchando en RealtimeEventBus: {e}")
        finally:
            self.pubsub.close()

    def listen_async(self) -> threading.Thread:
        """
        Inicia a escuchar eventos en un thread separado (no bloqueante).

        Returns:
            Thread en el que se ejecuta el listener
        """
        if self._listener_thread and self._listener_thread.is_alive():
            logger.warning("Listener ya está ejecutándose")
            return self._listener_thread

        self._listener_thread = threading.Thread(target=self.listen, daemon=True)
        self._listener_thread.start()
        logger.info("Listener iniciado en thread separado")
        return self._listener_thread

    def stop(self) -> None:
        """Detiene el listener."""
        self.pubsub.close()
        logger.info("RealtimeEventBus detenido")

    def _match_handler(self, channel: str) -> Optional[SubscriptionHandler]:
        """
        Encuentra el handler que coincida con el canal.
        Soporta patrones simples como "user:*:content.ready".

        Args:
            channel: Canal recibido

        Returns:
            Handler que coincide o None
        """
        # Primero intentar match exacto
        if channel in self.subscriptions:
            return self.subscriptions[channel]

        # Luego intentar match con patrones
        for pattern, handler in self.subscriptions.items():
            if self._pattern_match(pattern, channel):
                return handler

        return None

    @staticmethod
    def _pattern_match(pattern: str, channel: str) -> bool:
        """
        Verifica si un canal coincide con un patrón.
        Patrones soportados: "user:*:content" (simple globbing)

        Args:
            pattern: Patrón con wildcards
            channel: Canal a verificar

        Returns:
            True si coincide
        """
        if pattern == channel:
            return True

        # Convertir patrón a regex simple
        import fnmatch
        return fnmatch.fnmatch(channel, pattern)

    def health_check(self) -> bool:
        """Verifica que Redis esté conectado y funcional."""
        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Health check fallido: {e}")
            return False


# Singleton global (opcional, pero útil para casos sencillos)
_realtime_bus_instance: Optional[RealtimeEventBus] = None


def get_realtime_bus() -> RealtimeEventBus:
    """
    Obtiene la instancia global del RealtimeEventBus.
    Crea una si no existe.

    Returns:
        Instancia de RealtimeEventBus
    """
    global _realtime_bus_instance
    if _realtime_bus_instance is None:
        _realtime_bus_instance = RealtimeEventBus()
    return _realtime_bus_instance
