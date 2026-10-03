from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel


class ResolveLock(SQLModel, table=True):
    """
    Lock distribuido para coordinar entre resolve() y explore() endpoints.
    Previene race conditions cuando resolve() está actualizando items.
    """
    __tablename__: str = "resolve_locks"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    queue_item_id: int = Field(index=True, nullable=False)
    locked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
