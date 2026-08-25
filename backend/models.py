import enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import JSON, Integer
from sqlalchemy.orm import foreign
from enum import Enum


class User(SQLModel, table=True):
    __tablename__: str = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, nullable=False)
    hashed_password: str = Field(nullable=False)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    words: List["Word"] = Relationship(back_populates="user")


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


class ContentType(str, Enum):
    EXAMPLE = "example"
    BEST_OPTIONS = "best_options"


class ExampleWord(SQLModel, table=True):
    __tablename__: str = "example_words"

    example_id: int = Field(foreign_key="examples.id", primary_key=True)
    word_id: int = Field(foreign_key="words.id", primary_key=True)
    text_form: str = Field(max_length=255, nullable=False)

    example: "Example" = Relationship(back_populates="example_words")
    word: "Word" = Relationship(back_populates="example_words")


class LearningState(str, enum.Enum):
    NEW = "new"
    LEARNING = "learning"
    REINFORCING = "reinforcing"
    SPACING = "spacing"
    ALMOST_LEARNED = "almost_learned"
    LEARNED = "learned"
    REVIEW = "review"


class WordStatistics(SQLModel, table=True):
    __tablename__: str = "word_statistics"

    id: Optional[int] = Field(default=None, primary_key=True)
    word_id: int = Field(foreign_key="words.id", index=True)
    type: ContentType = Field(index=True)
    learning_state: LearningState = Field(index=True)
    last_seen_at: Optional[datetime] = Field(default=None)
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
    normalized: Optional[str] = Field(default=None, max_length=100, unique=True, index=True)
    is_favorite: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_boosted: bool = Field(default=False)
    boosted_at: Optional[datetime] = Field(default=None)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    user: User = Relationship(back_populates="words")

    statistics: List["WordStatistics"] = Relationship(back_populates="word")
    example_words: List["ExampleWord"] = Relationship(back_populates="word")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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
    normalized: Optional[str] = Field(default=None, max_length=255, unique=True, index=True)
    times_seen: int = Field(default=0)
    sequence: int = Field(default=0, index=True)
    enqueued: bool = Field(default=False, index=True)
    is_favorite: bool = Field(default=False)

    example_words: List["ExampleWord"] = Relationship(back_populates="example")


class BestOption(SQLModel, table=True):
    __tablename__: str = "best_options"

    id: Optional[int] = Field(default=None, primary_key=True)
    word_id: int = Field(foreign_key="words.id", index=True)
    question: str = Field(nullable=False)
    options: str = Field(nullable=False)  # guardar options separadas por ";"
    correct_option: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    normalized: Optional[str] = Field(default=None, max_length=255, unique=True, index=True)
    is_active: bool = Field(default=True)
    sequence: int = Field(default=0, index=True)
    enqueued: bool = Field(default=False, index=True)

    word: Optional["Word"] = Relationship()


class LearningPath(SQLModel, table=True):
    __tablename__ = "learning_path"

    id: Optional[int] = Field(default=None, primary_key=True)
    type: ContentType = Field(index=True)
    word_id: int = Field(foreign_key="words.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    segment: int = Field(index=True)
    position: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    word: Optional["Word"] = Relationship()

class LearningPathHistory(SQLModel, table=True):
    __tablename__ = "learning_path_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    type: ContentType = Field(index=True)
    word_id: int = Field(foreign_key="words.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    segment: int = Field(index=True)
    position: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    word: Optional["Word"] = Relationship()


class LearningPathCursor(SQLModel, table=True):
    __tablename__ = "learning_path_cursor"

    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="users.id",
        index=True,
    )

    type: ContentType = Field(index=True)

    current_segment: int = Field(default=1)
    current_position: int = Field(default=0)

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

class ContentQueueStatus(str, enum.Enum):
    PENDING = "pending"
    CONSUMED = "consumed"


class ContentQueue(SQLModel, table=True):
    __tablename__: str = "content_queue"

    id: Optional[int] = Field(default=None, primary_key=True)
    content_id: int = Field(index=True)
    type: ContentType = Field(index=True)
    status: ContentQueueStatus = Field(default=ContentQueueStatus.PENDING, index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    priority: float = Field(default=0.0, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GenerationQueueMonitorStatus(str, enum.Enum):
    IDLE = "idle"
    GENERATING = "generating"


class GenerationQueueMonitor(SQLModel, table=True):
    __tablename__: str = "generation_queue_monitor"

    id: Optional[int] = Field(default=None, primary_key=True)
    status: GenerationQueueMonitorStatus = Field(default=GenerationQueueMonitorStatus.IDLE, index=True)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExploreConfiguration(SQLModel, table=True):
    __tablename__: str = "explore_configurations"

    id: Optional[int] = Field(default=None, primary_key=True)
    max_examples: int = Field(nullable=False, unique=True, index=True)
    ai_mixed_generation_amount: int = Field(default=0)
    ai_simple_generation_amount: int = Field(default=0)
    recycled_words_amount: int = Field(default=0)


class GlobalConfiguration(SQLModel, table=True):
    __tablename__: str = "global_configurations"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, nullable=False, max_length=100)
    value: str = Field(nullable=False)
    description: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
