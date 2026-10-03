import enum
from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import JSON

from auth.models import User
from core.enums import ContentType


class WordLevel:
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3

    _MAP = {
        BEGINNER: "beginner",
        INTERMEDIATE: "intermediate",
        ADVANCED: "advanced"
    }

    _REVERSE_MAP = {v: k for k, v in _MAP.items()}

    @classmethod
    def to_str(cls, value: int) -> str:
        return cls._MAP.get(value, "unknown")

    @classmethod
    def to_int(cls, value: str) -> int:
        if not value:
            return cls.BEGINNER
        value = value.lower().strip()
        return cls._REVERSE_MAP.get(value, cls.BEGINNER)

    @classmethod
    def is_valid_int(cls, value: int) -> bool:
        return value in cls._MAP

    @classmethod
    def is_valid_str(cls, value: str) -> bool:
        return value in cls._REVERSE_MAP


class WordStatistics(SQLModel, table=True):
    __tablename__: str = "word_statistics"

    id: Optional[int] = Field(default=None, primary_key=True)
    word_id: int = Field(foreign_key="words.id", index=True)
    type: ContentType = Field(index=True)
    learning_state: str = Field(index=True)  # Will be imported from learning_path.enums
    last_seen_at: Optional[datetime] = Field(default=None)
    learned_at: Optional[datetime] = Field(default=None, index=True)
    times_seen: int = Field(default=0)
    current_cycle_seen: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    word: "Word" = Relationship(back_populates="statistics")


class Word(SQLModel, table=True):
    __tablename__: str = "words"

    id: Optional[int] = Field(default=None, primary_key=True)
    main: str = Field(max_length=100, nullable=False, index=True)
    meaning: Optional[str] = Field(default=None)
    synonyms: Optional[List[str]] = Field(default=None, sa_type=JSON)
    type: Optional[str] = Field(default=None, max_length=50)
    frequency: Optional[str] = Field(default=None, max_length=50)
    level: int = Field(default=WordLevel.INTERMEDIATE)
    context: Optional[str] = Field(default=None, max_length=50)
    source_text: Optional[str] = Field(max_length=100, default=None)
    normalized: Optional[str] = Field(default=None, max_length=100, index=True)
    is_favorite: bool = Field(default=False)
    favorited_at: Optional[datetime] = Field(default=None, index=True)
    is_active: bool = Field(default=True)
    is_boosted: bool = Field(default=False)
    boosted_at: Optional[datetime] = Field(default=None)
    explanation: Optional[str] = Field(default=None, max_length=500)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    user: Optional[User] = Relationship()

    statistics: List["WordStatistics"] = Relationship(back_populates="word")
    example_words: List["ExampleWord"] = Relationship(back_populates="word")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExampleWord(SQLModel, table=True):
    __tablename__: str = "example_words"

    example_id: int = Field(foreign_key="examples.id", primary_key=True)
    word_id: int = Field(foreign_key="words.id", primary_key=True)
    text_form: str = Field(max_length=255, nullable=False)

    example: "Example" = Relationship(back_populates="example_words")
    word: "Word" = Relationship(back_populates="example_words")
