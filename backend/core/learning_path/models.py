from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship
from features.words.models import Word

from core.learning_path.enums import (
    LearningState,
    LearningPathQueueStatus,
    PathAnomalyType,
    LearningPathGenerationMonitorStatus,
    LearningPathGenerationHistoryStatus,
)

from core.enums import ContentType


class LearningPath(SQLModel, table=True):
    """
    Representa el learning path actual del usuario.
    Contiene la secuencia de palabras que el usuario debe aprender.
    """
    __tablename__ = "learning_path"

    id: Optional[int] = Field(default=None, primary_key=True)
    type: ContentType = Field(index=True)
    word_id: int = Field(foreign_key="words.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    segment: int = Field(index=True)
    position: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    word: Word = Relationship()


class LearningPathHistory(SQLModel, table=True):
    """
    Historial de cambios en el learning path del usuario.
    Permite auditar y diagnosticar cambios en el path.
    """
    __tablename__ = "learning_path_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    type: ContentType = Field(index=True)
    word_id: int = Field(foreign_key="words.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    segment: int = Field(index=True)
    position: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    word: Word = Relationship()


class LearningPathCursor(SQLModel, table=True):
    """
    Posición actual del cursor en el learning path del usuario.
    Trackea dónde está el usuario en su aprendizaje.
    """
    __tablename__ = "learning_path_cursor"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="users.id",
        index=True,
    )

    type: ContentType = Field(index=True)

    current_segment: int = Field(default=1)
    current_position: int = Field(default=0)

    # Último word_id seleccionado para rotación entre palabras
    last_selected_word_id: Optional[int] = Field(default=None, index=True)

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class LearningPathQueue(SQLModel, table=True):
    """
    Cola de contenido preparado para el usuario.
    Contiene ejemplos y best_options listos para ser consumidos.

    Este modelo pertenece al módulo de learning_path.
    Siempre debe incluir el word_id asociado al contenido.
    """
    __tablename__: str = "learning_path_queue"

    id: Optional[int] = Field(default=None, primary_key=True)
    content_id: int = Field(index=True)
    content_type: ContentType = Field(index=True)
    # Palabra asociada al contenido (obligatorio)
    word_id: int = Field(foreign_key="words.id", index=True)
    status: LearningPathQueueStatus = Field(default=LearningPathQueueStatus.PENDING, index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    priority: float = Field(default=0.0, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


class LearningPathAnomaly(SQLModel, table=True):
    """
    Registra anomalías detectadas en el learning path.
    Permite auditar y diagnosticar problemas automáticamente.
    """
    __tablename__: str = "learning_path_anomalies"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    type: ContentType = Field(index=True)
    anomaly_type: PathAnomalyType = Field(index=True)

    # Descripción detallada
    description: str = Field(nullable=False)

    # Datos de diagnóstico (JSON)
    details: str = Field(default="{}")  # JSON con datos específicos del problema

    # Auto-reparación
    auto_repair_attempted: bool = Field(default=False, index=True)
    auto_repair_successful: bool = Field(default=False, index=True)
    repair_description: Optional[str] = Field(default=None)

    # Seguimiento
    is_resolved: bool = Field(default=False, index=True)
    resolved_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RecentWordHistory(SQLModel, table=True):
    """
    Tracks recently shown words for a user in a given content type.
    Used for band-pass filtering to prevent immediate word repetition.

    Each record represents one word selection. Older records are automatically
    pruned to maintain a sliding window of N most recent selections.
    Example: With window_size=3, keeps the 3 most recent word selections.
    """
    __tablename__: str = "recent_word_history"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="users.id",
        index=True,
        nullable=False
    )

    type: ContentType = Field(index=True, nullable=False)

    # Word ID that was shown
    word_id: int = Field(index=True, nullable=False)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True
    )


class BandPassConfig(SQLModel, table=True):
    """
    Configuration for band-pass filtering in learning path.
    Controls how many recent words to track and how much to penalize them.

    Allows fine-tuning of word repetition prevention:
    - window_size: How many recent words to track (default 3, can be 4, 5, etc.)
    - inflation_factor: How much to reduce priority of recent words (default 0.2, reduces priority by 20%)
    """
    __tablename__: str = "band_pass_config"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="users.id",
        index=True,
        nullable=False
    )

    type: ContentType = Field(index=True, nullable=False)

    # Window size for tracking recent words (e.g., 3 means track last 3 words)
    # Default is 3, but can be adjusted to 4, 5, etc. for stronger prevention
    window_size: int = Field(default=3, ge=1, le=10)

    # Inflation factor applied to penalize recent words
    # E.g., 0.2 means reduce priority by 20%, 0.5 means reduce by 50%
    # Applied as: new_priority = original_priority * (1 - inflation_factor)
    inflation_factor: float = Field(default=0.2, ge=0.0, le=1.0)

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True
    )


class PathRepairLog(SQLModel, table=True):
    """
    Registra todas las reparaciones ejecutadas en el learning path.
    Útil para auditoría y entender el historial de problemas.
    """
    __tablename__: str = "path_repair_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    type: ContentType = Field(index=True)

    # Qué se reparó
    repair_type: str = Field(max_length=100, nullable=False)  # "delete_oversized_path", "remove_inactive_words", etc

    # Antes y después
    before_state: str = Field(nullable=False)  # JSON con estado anterior
    after_state: str = Field(nullable=False)  # JSON con estado posterior

    # Resultados
    items_affected: int = Field(default=0)
    success: bool = Field(default=True, index=True)
    error_message: Optional[str] = Field(default=None)

    # Trigger
    triggered_by: str = Field(max_length=100, default="auto_repair")  # "auto_repair", "manual", "api_call"

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


class LearningPathGenerationMonitor(SQLModel, table=True):
    """
    Monitorea el estado actual de generación de contenido para el learning path.
    Solo tiene 2 estados: IDLE (sin generar) o GENERATING (generando).
    El historial de resultados (COMPLETED/FAILED) se guarda en LearningPathGenerationHistory.
    """
    __tablename__: str = "learning_path_generation_monitors"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="users.id",
        index=True,
        nullable=False
    )

    content_type: ContentType = Field(index=True, nullable=False)

    # Estado de generación: IDLE | GENERATING
    status: LearningPathGenerationMonitorStatus = Field(
        default=LearningPathGenerationMonitorStatus.IDLE,
        index=True,
        nullable=False
    )

    # Auditoría temporal
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True
    )
    started_at: Optional[datetime] = Field(default=None, index=True)


class LearningPathGenerationHistory(SQLModel, table=True):
    """
    Historial de resultados de generación de contenido para el learning path.
    Guarda los estados finales (COMPLETED/FAILED) y mensajes de error.
    El monitor actual (LearningPathGenerationMonitor) solo trackea IDLE/GENERATING.
    """
    __tablename__: str = "learning_path_generation_history"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="users.id",
        index=True,
        nullable=False
    )

    content_type: ContentType = Field(index=True, nullable=False)

    # Estado final: COMPLETED | FAILED
    status: LearningPathGenerationHistoryStatus = Field(
        index=True,
        nullable=False
    )

    # Información de error (solo si status=FAILED)
    error_message: Optional[str] = Field(default=None)

    # Auditoría temporal
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True
    )
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True
    )
