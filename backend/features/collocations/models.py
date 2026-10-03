from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel


class Collocation(SQLModel, table=True):
    __tablename__: str = "collocations"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    word_id: Optional[int] = Field(foreign_key="words.id", nullable=True, index=True)
    phrase: str = Field(nullable=False, max_length=255)
    text_form: Optional[str] = Field(default=None, max_length=255)
    is_marked: bool = Field(default=False, index=True)
    is_in_use: bool = Field(default=False, index=True)
    in_use_at: Optional[datetime] = Field(default=None, index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
