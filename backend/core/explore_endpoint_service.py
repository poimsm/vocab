"""
Servicio para manejar endpoints de explore.

Proporciona una interfaz genérica para:
- Procesar requests de explore
- Encolar tasks de background
- Publicar eventos iniciales
- Logging de actividad
"""

import uuid
import time
from typing import List, Optional, Any, Dict
from sqlmodel import Session
from logging_client import logger
from activity.user_activity_service import UserActivityService
from core.realtime_event_bus import get_realtime_bus
from auth.models import User
from celery.app.task import Task
from core.celery_queues import CeleryQueue


class ExploreEndpointService:
    """
    Servicio genérico para endpoints de explore.

    Maneja:
    - Generación de request_id
    - Publicación de eventos iniciales
    - Encola tasks de background
    - Logging de actividad
    """

    def __init__(
        self,
        channel_prefix: str,
        feature_name: str,
        logger_name: str = "ExploreEndpointService",
    ):
        """
        Args:
            channel_prefix: Prefijo del canal para eventos (ej: "examples_explore", "best_options_explore")
            feature_name: Nombre de la feature para logging (ej: "examples_explore", "best_options_explore")
            logger_name: Nombre para logs
        """
        self.channel_prefix = channel_prefix
        self.feature_name = feature_name
        self.logger_name = logger_name

    def process_explore_request(
        self,
        db: Session,
        current_user: User,
        request_data: Dict[str, Any],
        task: Task,
    ) -> Dict[str, str]:
        """
        Procesa un request de explore.

        Args:
            db: Sesión de base de datos
            current_user: Usuario autenticado
            request_data: Datos del request (actions, limit, buffer_delivery_ids, etc.)
            task: Task de Celery para encolar

        Returns:
            Response dict con status, request_id, message
        """
        request_id = str(uuid.uuid4())

        logger.info(
            f"[{self.logger_name}] User {current_user.id}: request_id={request_id}, "
            f"actions={request_data['actions']}, limit={request_data['limit']}, "
            f"buffer_size={len(request_data['buffer_delivery_ids'])}"
        )

        # Log detallado del request para debugging
        logger.info(
            f"[{self.logger_name}] DETAILED REQUEST: "
            f"resolve_queue_item_id={request_data.get('resolve_queue_item_id')} "
            f"(type={type(request_data.get('resolve_queue_item_id')).__name__}), "
            f"actions={request_data['actions']}, "
            f"buffer_delivery_ids={request_data['buffer_delivery_ids']}, "
            f"buffer_position={request_data['buffer_position']}"
        )

        # Log de actividad
        UserActivityService.log_feature_interaction(
            db=db,
            user_id=current_user.id,
            feature_name=self.feature_name,
            interaction_type="_".join(request_data['actions']),
            details={
                "actions": request_data['actions'],
                "limit": request_data['limit'],
                "buffer_size": len(request_data['buffer_delivery_ids']),
                "request_id": request_id
            }
        )

        # Publicar evento inicial de inicio de exploración
        realtime_bus = get_realtime_bus()
        realtime_bus.publish(
            channel=f"user:{current_user.id}:{self.channel_prefix}.started",
            data={
                "request_id": request_id,
                "actions": request_data['actions'],
                "timestamp": time.time(),
            }
        )

        # Encolar tarea de background para ejecutar acciones
        task.apply_async(
            args=[current_user.id],
            kwargs={
                "request_id": request_id,
                "actions": request_data['actions'],
                "resolve_queue_item_id": request_data.get('resolve_queue_item_id'),
                "limit": request_data['limit'],
                "buffer_delivery_ids": request_data['buffer_delivery_ids'],
                "buffer_position": request_data['buffer_position'],
            },
            queue=CeleryQueue.BACKGROUND,
        )

        logger.debug(
            f"[{self.logger_name}] Task enqueued for user {current_user.id} "
            f"with request_id {request_id}"
        )

        return {
            "status": "ok",
            "request_id": request_id,
            "message": "Explore request enqueued. Results will be streamed via /explore-stream"
        }
