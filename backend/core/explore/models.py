from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone


class ExploreSession(SQLModel, table=True):
    """
    Trackea la sesión actual de explore del usuario.
    Persiste el buffer de DeliveryBuffer, items visitados e items resueltos.
    Soporta múltiples content types (EXAMPLE, BEST_OPTIONS, etc).
    """
    __tablename__: str = "explore_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    content_type: str = Field(default="EXAMPLE", index=True)  # EXAMPLE, BEST_OPTIONS, etc

    # Buffer actual de DeliveryBuffer items
    buffer_delivery_ids: str = Field(default="[]")  # JSON string de IDs del delivery buffer
    buffer_position: int = Field(default=0)  # Posición actual en el buffer

    # Items visitados en esta sesión (mostrados al usuario)
    visited_delivery_ids: str = Field(default="[]")  # JSON string de delivery buffer IDs visitados

    # Items resueltos en esta sesión (exposición registrada)
    resolved_delivery_ids: str = Field(default="[]")  # JSON string de delivery buffer IDs resueltos

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
