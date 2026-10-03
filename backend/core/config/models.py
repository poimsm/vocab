from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel


class GlobalConfiguration(SQLModel, table=True):
    __tablename__: str = "global_configurations"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, nullable=False, max_length=100)
    value: str = Field(nullable=False)
    description: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserConfiguration(SQLModel, table=True):
    """
    Configuración específica por usuario.
    Permite establecer límites diferentes para cada usuario.
    Si no tiene valor específico, usa el de GlobalConfiguration como fallback.
    """
    __tablename__: str = "user_configurations"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True, unique=True)

    # Límites específicos del usuario (None = usar global)
    max_words: Optional[int] = Field(default=None, nullable=True)
    max_examples: Optional[int] = Field(default=None, nullable=True)
    max_best_options: Optional[int] = Field(default=None, nullable=True)
    max_collocations: Optional[int] = Field(default=None, nullable=True)
    max_quick_writes: Optional[int] = Field(default=None, nullable=True)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
