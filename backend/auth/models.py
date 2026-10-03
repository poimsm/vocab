from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__: str = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, nullable=False)
    hashed_password: str = Field(nullable=False)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserProfile(SQLModel, table=True):
    """
    Perfil de usuario con contabilidad de recursos.
    Mantiene contadores actualizados de words, examples, best_options, etc.
    Esto evita hacer COUNT(*) constantemente y permite comparaciones rápidas con límites.
    """
    __tablename__: str = "user_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True, unique=True)

    # Contadores de recursos
    total_words: int = Field(default=0)
    total_examples: int = Field(default=0)
    total_best_options: int = Field(default=0)
    total_collocations: int = Field(default=0)
    total_quick_writes: int = Field(default=0)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
