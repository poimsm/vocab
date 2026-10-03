from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from core.enums import ContentType


class BoostGenerationMonitor(SQLModel, table=True):
    """
    Monitorea el estado de generación de contenido para palabras boosteadas.
    Permite saber si actualmente se está generando contenido para una palabra específica.
    """
    __tablename__: str = "boost_generation_monitors"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="users.id",
        index=True,
        nullable=False
    )
    word_id: int = Field(
        foreign_key="words.id",
        index=True,
        nullable=False
    )

    content_type: ContentType = Field(index=True, nullable=False)

    # Estados: "idle" (sin generar), "generating" (generando), "completed" (completado), "failed" (error)
    status: str = Field(
        default="idle",
        max_length=20,
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
    completed_at: Optional[datetime] = Field(default=None, index=True)

    # Información de error (si aplica)
    error_message: Optional[str] = Field(default=None)
