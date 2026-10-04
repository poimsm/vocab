import enum
from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship


class ExampleType(str, enum.Enum):
    INITIAL = "initial"
    EXPLORE = "explore"


class Example(SQLModel, table=True):
    __tablename__: str = "examples"

    id: Optional[int] = Field(default=None, primary_key=True)
    type: ExampleType = Field(index=True)
    text: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    favorited_at: Optional[datetime] = Field(default=None, index=True)
    normalized: Optional[str] = Field(default=None, max_length=255, index=True)
    times_seen: int = Field(default=0)
    sequence: int = Field(default=0, index=True)
    enqueued: bool = Field(default=False, index=True)
    is_favorite: bool = Field(default=False)
    is_marked: bool = Field(default=False, index=True)

    example_words: List["ExampleWord"] = Relationship(back_populates="example")


class ExploreConfiguration(SQLModel, table=True):
    __tablename__: str = "explore_configurations"

    id: Optional[int] = Field(default=None, primary_key=True)
    max_examples: int = Field(nullable=False, unique=True, index=True)
    ai_mixed_generation_amount: int = Field(default=0)
    ai_simple_generation_amount: int = Field(default=0)
    recycled_words_amount: int = Field(default=0)
