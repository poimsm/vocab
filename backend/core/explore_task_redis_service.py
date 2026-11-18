"""
Servicio para gestionar estados de tareas explore en Redis.

Almacena el status y progreso de tareas de explore (examples, best_options, etc.)
permitiendo que el frontend haga polling para saber si está completada o falló.
"""

import json
import time
import redis
import os
from logging_client import logger


class ExploreTaskRedisService:
    """Gestiona el estado de tareas explore en Redis."""

    # TTL para keys en Redis: 30 minutos
    TASK_TTL = 30 * 60

    # Cliente Redis singleton
    _redis_client = None

    @classmethod
    def _get_redis_client(cls):
        """Obtiene o crea el cliente Redis."""
        if cls._redis_client is None:
            redis_host = os.getenv("REDIS_HOST", "redis")
            redis_port = int(os.getenv("REDIS_PORT", 6379))

            try:
                cls._redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=0,
                    decode_responses=True,
                )
                # Verificar conexión
                cls._redis_client.ping()
                logger.info(f"[ExploreTaskRedisService] Conectado a Redis en {redis_host}:{redis_port}")
            except Exception as e:
                logger.error(f"[ExploreTaskRedisService] Error conectando a Redis: {e}")
                raise

        return cls._redis_client

    @staticmethod
    def get_task_status_key(request_id: str) -> str:
        """Genera la key de status para una tarea."""
        return f"explore_task:status:{request_id}"

    @staticmethod
    def get_task_results_key(request_id: str) -> str:
        """Genera la key de resultados para una tarea."""
        return f"explore_task:results:{request_id}"

    @classmethod
    def set_status(
        cls,
        request_id: str,
        status: str,
        message: str = "",
        additional_data: dict = None
    ) -> None:
        """
        Actualiza el status de una tarea en Redis.

        Args:
            request_id: ID único de la solicitud
            status: Estado ("processing", "completed", "failed")
            message: Mensaje descriptivo
            additional_data: Datos adicionales (error details, etc.)
        """
        redis_client = cls._get_redis_client()
        key = cls.get_task_status_key(request_id)

        status_data = {
            "status": status,
            "message": message,
            "timestamp": time.time(),
            **(additional_data or {})
        }

        try:
            redis_client.setex(
                key,
                cls.TASK_TTL,
                json.dumps(status_data)
            )
            logger.debug(f"[ExploreTaskRedisService] Status updated: {request_id} -> {status}")
        except Exception as e:
            logger.error(
                f"[ExploreTaskRedisService] Error setting status for {request_id}: {e}",
                exc_info=True
            )

    @classmethod
    def get_status(cls, request_id: str) -> dict:
        """
        Obtiene el status de una tarea desde Redis.

        Returns:
            {
                "status": "processing" | "completed" | "failed",
                "message": str,
                "timestamp": float,
                ...additional_data
            }
            O None si no existe
        """
        redis_client = cls._get_redis_client()
        key = cls.get_task_status_key(request_id)

        try:
            data = redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(
                f"[ExploreTaskRedisService] Error getting status for {request_id}: {e}",
                exc_info=True
            )
            return None

    @classmethod
    def set_results(
        cls,
        request_id: str,
        results: dict
    ) -> None:
        """
        Guarda los resultados de una tarea en Redis.

        Args:
            request_id: ID único de la solicitud
            results: Diccionario con resultados (buffer_ids, position, etc.)
        """
        redis_client = cls._get_redis_client()
        key = cls.get_task_results_key(request_id)

        try:
            redis_client.setex(
                key,
                cls.TASK_TTL,
                json.dumps(results, default=str)
            )
            logger.debug(f"[ExploreTaskRedisService] Results saved: {request_id}")
        except Exception as e:
            logger.error(
                f"[ExploreTaskRedisService] Error setting results for {request_id}: {e}",
                exc_info=True
            )

    @classmethod
    def get_results(cls, request_id: str) -> dict:
        """
        Obtiene los resultados de una tarea desde Redis.

        Returns:
            {
                "buffer_delivery_ids": [...],
                "buffer_position": int,
                "status": str,
                ...
            }
            O None si no existe
        """
        redis_client = cls._get_redis_client()
        key = cls.get_task_results_key(request_id)

        try:
            data = redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(
                f"[ExploreTaskRedisService] Error getting results for {request_id}: {e}",
                exc_info=True
            )
            return None

    @classmethod
    def set_processing(cls, request_id: str) -> None:
        """Marca una tarea como en procesamiento."""
        cls.set_status(request_id, "processing", "Processing explore actions...")

    @classmethod
    def set_completed(cls, request_id: str) -> None:
        """Marca una tarea como completada."""
        cls.set_status(request_id, "completed", "Explore completed successfully")

    @classmethod
    def set_failed(cls, request_id: str, error: str) -> None:
        """Marca una tarea como fallida."""
        cls.set_status(
            request_id,
            "failed",
            f"Explore failed: {error}",
            {"error": error}
        )

    @classmethod
    def cleanup(cls, request_id: str) -> None:
        """Limpia los datos de una tarea de Redis."""
        redis_client = cls._get_redis_client()
        status_key = cls.get_task_status_key(request_id)
        results_key = cls.get_task_results_key(request_id)

        try:
            redis_client.delete(status_key, results_key)
            logger.debug(f"[ExploreTaskRedisService] Cleaned up: {request_id}")
        except Exception as e:
            logger.error(
                f"[ExploreTaskRedisService] Error cleaning up {request_id}: {e}",
                exc_info=True
            )
