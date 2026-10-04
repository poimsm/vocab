from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship

from features.words.models import Word


class BestOption(SQLModel, table=True):
    __tablename__: str = "best_options"

    id: Optional[int] = Field(default=None, primary_key=True)
    word_id: int = Field(foreign_key="words.id", index=True)
    question: str = Field(nullable=False)
    options: str = Field(nullable=False)  # guardar options separadas por ";"
    correct_option: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    normalized: Optional[str] = Field(default=None, max_length=255, index=True)
    is_active: bool = Field(default=True)
    sequence: int = Field(default=0, index=True)
    enqueued: bool = Field(default=False, index=True)

    word: Optional["Word"] = Relationship()
