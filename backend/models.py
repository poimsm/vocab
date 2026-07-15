import enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import JSON, Integer


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


class ExampleWord(SQLModel, table=True):
    __tablename__: str = "example_words"

    example_id: int = Field(foreign_key="examples.id", primary_key=True)
    word_id: int = Field(foreign_key="words.id", primary_key=True)
    text_form: str = Field(max_length=255, nullable=False)

    # Relaciones inversas en SQLModel usando Relationship
    example: "Example" = Relationship(back_populates="example_words")
    word: "Word" = Relationship(back_populates="example_words")


class Word(SQLModel, table=True):
    __tablename__: str = "words"

    id: Optional[int] = Field(default=None, primary_key=True)
    main: str = Field(max_length=100, nullable=False, index=True)
    # Text en Postgres se maneja con str normal
    meaning: Optional[str] = Field(default=None)
    synonyms: Optional[List[str]] = Field(default=None, sa_type=JSON)
    # word | phrase | idiom | phrasal verb
    type: Optional[str] = Field(default=None, max_length=50)
    frequency: Optional[str] = Field(default=None, max_length=50)
    level: int = Field(default=WordLevel.INTERMEDIATE)
    context: Optional[str] = Field(default=None, max_length=50)
    source_text: Optional[str] = Field(max_length=100, default=None)

    normalized: Optional[str] = Field(
        default=None, max_length=100, unique=True, index=True)

    last_seen_at: Optional[datetime] = Field(default=None)
    times_seen: int = Field(default=0)
    is_favorite: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_learned: bool = Field(default=False)

    # Relaciones
    # sa_relationship_kwargs={"uselist": False} define la relación 1 a 1
    example_words: List[ExampleWord] = Relationship(back_populates="word")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))


class ExampleType(int, enum.Enum):
    INITIAL = 0
    EXPLORE = 1


class Example(SQLModel, table=True):
    __tablename__: str = "examples"

    id: Optional[int] = Field(default=None, primary_key=True)
    text: str = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    normalized: Optional[str] = Field(
        default=None, max_length=255, unique=True, index=True)
    is_active: bool = Field(default=True)
    is_favorite: bool = Field(default=False)
    times_seen: int = Field(default=0)

    type: ExampleType = Field(
        default=ExampleType.EXPLORE,
        sa_type=Integer,
        index=True,
        sa_column_kwargs={"server_default": str(ExampleType.EXPLORE.value)}
    )

    example_words: List[ExampleWord] = Relationship(back_populates="example")


class QueueStatus(str, enum.Enum):
    PENDING = "pending"   # Encolado listo para enviar
    SENT = "sent"         # Enviado al usuario en el explore (revisando en app)
    RESOLVED = "resolved"  # Ya procesado e incrementado


class ExampleQueue(SQLModel, table=True):
    __tablename__: str = "example_queue"

    id: Optional[int] = Field(default=None, primary_key=True)
    example_id: int = Field(foreign_key="examples.id", index=True)
    status: QueueStatus = Field(default=QueueStatus.PENDING, index=True)
    is_active: bool = Field(default=True, index=True)

    example: "Example" = Relationship()
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))


class ExploreConfiguration(SQLModel, table=True):
    __tablename__: str = "explore_configurations"

    id: Optional[int] = Field(default=None, primary_key=True)
    # El límite de ejemplos para este rango (ej: 30, 60, 120).
    # Usamos un valor muy alto o Nullable si quieres representar el "else" (infinito).
    max_examples: int = Field(nullable=False, unique=True, index=True)

    ai_mixed_generation_amount: int = Field(default=0)
    ai_simple_generation_amount: int = Field(default=0)
    recycled_words_amount: int = Field(default=0)


class Activity(SQLModel, table=True):
    __tablename__: str = "activities"

    id: Optional[int] = Field(default=None, primary_key=True)
    action: str = Field(max_length=100, nullable=False)

    # 🔥 CORRECCIÓN: Le decimos explícitamente a SQLModel que use el tipo JSON de SQLAlchemy
    payload: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
