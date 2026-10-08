from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Session, select
from core.learning_path.models import LearningPathGenerationMonitor, LearningPathGenerationHistory
from core.learning_path.enums import LearningPathGenerationMonitorStatus, LearningPathGenerationHistoryStatus
from core.enums import ContentType
from core.event_bus import publish_event_background
from logging_client import logger


class LearningPathRepository:
    """Repository para operaciones de monitoreo de generación del learning path."""

    def __init__(self, session: Session):
        self.session = session

    def start_generation_monitor(
        self,
        user_id: int,
        content_type: ContentType
    ) -> LearningPathGenerationMonitor:
        """Registra que comenzó la generación de contenido para el learning path."""
        now = datetime.now(timezone.utc)

        # Buscar si ya existe un monitor para este user y content_type
        statement = select(LearningPathGenerationMonitor).where(
            LearningPathGenerationMonitor.user_id == user_id,
            LearningPathGenerationMonitor.content_type == content_type,
        )
        existing = self.session.exec(statement).first()

        if existing:
            # Actualizar el existente
            existing.status = LearningPathGenerationMonitorStatus.GENERATING
            existing.started_at = now
            existing.updated_at = now
            existing.error_message = None
            self.session.add(existing)
        else:
            # Crear uno nuevo
            monitor = LearningPathGenerationMonitor(
                user_id=user_id,
                content_type=content_type,
                status=LearningPathGenerationMonitorStatus.GENERATING,
                started_at=now,
            )
            self.session.add(monitor)

        self.session.commit()
        return existing or monitor

    def complete_generation_monitor(
        self,
        user_id: int,
        content_type: ContentType
    ) -> Optional[LearningPathGenerationMonitor]:
        """Marca que la generación de contenido fue completada."""
        now = datetime.now(timezone.utc)

        statement = select(LearningPathGenerationMonitor).where(
            LearningPathGenerationMonitor.user_id == user_id,
            LearningPathGenerationMonitor.content_type == content_type,
        )
        monitor = self.session.exec(statement).first()

        if monitor:
            # Cambiar monitor a IDLE (se liberó de la generación)
            monitor.status = LearningPathGenerationMonitorStatus.IDLE
            monitor.updated_at = now
            self.session.add(monitor)

            # Guardar en historial como COMPLETED
            history = LearningPathGenerationHistory(
                user_id=user_id,
                content_type=content_type,
                status=LearningPathGenerationHistoryStatus.COMPLETED,
            )
            self.session.add(history)
            self.session.commit()

            # Disparar evento de generación completada
            publish_event_background(
                'learning_path.generation.completed',
                user_id=user_id,
                content_type=content_type.value,
            )
            logger.info(
                f"[LearningPathRepository] Generation completed for user {user_id} "
                f"(content_type={content_type.value}). Event dispatched."
            )

        return monitor

    def fail_generation_monitor(
        self,
        user_id: int,
        content_type: ContentType,
        error_message: str
    ) -> Optional[LearningPathGenerationMonitor]:
        """Marca que la generación de contenido falló."""
        now = datetime.now(timezone.utc)

        statement = select(LearningPathGenerationMonitor).where(
            LearningPathGenerationMonitor.user_id == user_id,
            LearningPathGenerationMonitor.content_type == content_type,
        )
        monitor = self.session.exec(statement).first()

        if monitor:
            # Cambiar monitor a IDLE (se liberó de la generación)
            monitor.status = LearningPathGenerationMonitorStatus.IDLE
            monitor.updated_at = now
            self.session.add(monitor)

            # Guardar en historial como FAILED
            history = LearningPathGenerationHistory(
                user_id=user_id,
                content_type=content_type,
                status=LearningPathGenerationHistoryStatus.FAILED,
                error_message=error_message,
            )
            self.session.add(history)
            self.session.commit()

            # Disparar evento de generación fallida
            publish_event_background(
                'learning_path.generation.failed',
                user_id=user_id,
                content_type=content_type.value,
                error_message=error_message,
            )
            logger.info(
                f"[LearningPathRepository] Generation failed for user {user_id} "
                f"(content_type={content_type.value}). Event dispatched."
            )

        return monitor

    def get_generation_monitor(
        self,
        user_id: int,
        content_type: ContentType
    ) -> Optional[LearningPathGenerationMonitor]:
        """Obtiene el estado actual del monitoreo de generación."""
        statement = select(LearningPathGenerationMonitor).where(
            LearningPathGenerationMonitor.user_id == user_id,
            LearningPathGenerationMonitor.content_type == content_type,
        )
        return self.session.exec(statement).first()

    def is_generating(
        self,
        user_id: int,
        content_type: ContentType
    ) -> bool:
        """Chequea si actualmente se está generando contenido."""
        monitor = self.get_generation_monitor(user_id, content_type)
        return monitor is not None and monitor.status == LearningPathGenerationMonitorStatus.GENERATING
