from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel
from sqlalchemy import JSON


class QuickWrite(SQLModel, table=True):
    __tablename__: str = "quick_write"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    prompt: str = Field(nullable=False, max_length=255)
    emoji: str = Field(default="✍️", max_length=10)
    words: Optional[List[str]] = Field(default=None, sa_type=JSON)
    original_content: Optional[str] = Field(default=None, max_length=500)
    corrected_content: Optional[str] = Field(default=None, max_length=500)
    has_corrections: bool = Field(default=False)
    is_favorite: bool = Field(default=False)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
