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
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))

    words: List["Word"] = Relationship(back_populates="user")
    activities: List["Activity"] = Relationship(back_populates="user")


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


class BatchStatus(str, Enum):
    OPEN = "open"            # Aceptando palabras sueltas
    COMPLETED = "completed"  # Alcanzó su capacidad máxima
    ARCHIVED = "archived"    # Pausado/archivado por el usuario


class BatchFeaturedStatus(str, Enum):
    ACTIVE = "active"        # En proceso de estudio
    MASTERED = "mastered"    # Todas sus palabras dominadas


class BatchSource(str, Enum):
    BULK_IMPORT = "bulk_import"  # Carga masiva (ej. texto largo)
    ORGANIC = "organic"          # Palabras agregadas una a una


class ContentType(str, Enum):
    EXAMPLE = "example"                  # Generación de ejemplos
    BEST_OPTIONS = "best_options"        # Ejercicios de opciones


class Batch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)

    title: str = Field(default="Lote sin título")
    source: BatchSource = Field(default=BatchSource.ORGANIC)
    capacity: int = Field(default=15)
    status: BatchStatus = Field(default=BatchStatus.OPEN, index=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(default=None)

    # Relación con las palabras
    words: List["Word"] = Relationship(back_populates="batch")
    featured: List["BatchFeatured"] = Relationship(back_populates="batch")


class BatchFeatured(SQLModel, table=True):
    __tablename__: str = "batch_featured"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="batch.id", index=True)
    type: ContentType = Field(index=True)
    status: BatchFeaturedStatus = Field(
        default=BatchFeaturedStatus.ACTIVE, index=True)

    # Estadísticas y progreso
    mastery_progress: float = Field(default=0.0)  # 0.0 a 100.0%

    # Seguimiento temporal
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(default=None)

    is_active: bool = Field(default=True, index=True)

    batch: "Batch" = Relationship(back_populates="featured")


class ExampleWord(SQLModel, table=True):
    __tablename__: str = "example_words"

    example_id: int = Field(foreign_key="examples.id", primary_key=True)
    word_id: int = Field(foreign_key="words.id", primary_key=True)
    text_form: str = Field(max_length=255, nullable=False)

    example: "Example" = Relationship(back_populates="example_words")
    word: "Word" = Relationship(back_populates="example_words")


class WordStatistics(SQLModel, table=True):
    __tablename__: str = "word_statistics"

    id: Optional[int] = Field(default=None, primary_key=True)
    word_id: int = Field(foreign_key="words.id", index=True)
    type: ContentType = Field(index=True)

    is_learned: bool = Field(default=False, index=True)
    last_seen_at: Optional[datetime] = Field(default=None)
    times_seen: int = Field(default=0)
    current_cycle_seen: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))

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

    normalized: Optional[str] = Field(
        default=None, max_length=100, unique=True, index=True)

    is_favorite: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_boosted: bool = Field(default=False)
    boosted_at: Optional[datetime] = Field(default=None)

    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    user: User = Relationship(back_populates="words")
    example_words: List[ExampleWord] = Relationship(back_populates="word")
    statistics: List["WordStatistics"] = Relationship(back_populates="word")

    batch_id: Optional[int] = Field(default=None, foreign_key="batch.id")
    batch: Optional["Batch"] = Relationship(back_populates="words")

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
    is_pristine: bool = Field(default=True, index=True)
    times_seen: int = Field(default=0)

    type: ExampleType = Field(
        default=ExampleType.EXPLORE,
        sa_type=Integer,
        index=True,
        sa_column_kwargs={"server_default": str(ExampleType.EXPLORE.value)}
    )

    example_words: List[ExampleWord] = Relationship(back_populates="example")

    @property
    def words(self) -> List["Word"]:
        """Retorna la lista de objetos Word asociados a través de la tabla intermedia."""
        return [assoc.word for assoc in self.example_words if assoc.word]


class BestOption(SQLModel, table=True):
    __tablename__: str = "best_options"

    id: Optional[int] = Field(default=None, primary_key=True)
    word_id: int = Field(foreign_key="words.id", index=True)
    # 1, 2, 3, o 4 (cuál de los 4 ejercicios es)
    sequence_order: int = Field(default=1)
    question: str = Field(nullable=False)
    options: str = Field(nullable=False)  # guardar options separadas por ";"
    correct_option: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    normalized: Optional[str] = Field(
        default=None, max_length=255, unique=True, index=True)
    is_active: bool = Field(default=True)
    is_pristine: bool = Field(default=True)

    word: "Word" = Relationship()


class QueueStatus(str, enum.Enum):
    PENDING = "pending"   # Encolado listo para enviar
    SENT = "sent"         # Enviado al usuario
    RESOLVED = "resolved"  # Ya procesado


class GenerationQueue(SQLModel, table=True):
    __tablename__: str = "generation_queue"

    id: Optional[int] = Field(default=None, primary_key=True)
    content_id: int = Field(index=True)
    type: ContentType = Field(index=True)
    status: QueueStatus = Field(default=QueueStatus.PENDING, index=True)
    is_active: bool = Field(default=True, index=True)

    user_id: int = Field(foreign_key="users.id", index=True)

    example: Optional["Example"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "and_(foreign(generation_queue.c.content_id)==examples.c.id, generation_queue.c.type=='example')",
            "viewonly": True,
            "uselist": False
        }
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))


class ExploreConfiguration(SQLModel, table=True):
    __tablename__: str = "explore_configurations"

    id: Optional[int] = Field(default=None, primary_key=True)
    max_examples: int = Field(nullable=False, unique=True, index=True)

    ai_mixed_generation_amount: int = Field(default=0)
    ai_simple_generation_amount: int = Field(default=0)
    recycled_words_amount: int = Field(default=0)


class Activity(SQLModel, table=True):
    __tablename__: str = "activities"

    id: Optional[int] = Field(default=None, primary_key=True)
    action: str = Field(max_length=100, nullable=False)

    payload: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))

    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    user: User = Relationship(back_populates="activities")


class QueueRefillStatus(SQLModel, table=True):
    __tablename__: str = "queue_refill_status"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    queue_type: ContentType = Field(index=True)
    is_refilling: bool = Field(default=False, index=True)
    started_at: Optional[datetime] = Field(default=None)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        # Constraint único: solo un refill activo por user_id y queue_type
    )


class GlobalConfiguration(SQLModel, table=True):
    __tablename__: str = "global_configurations"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True, nullable=False, max_length=100)
    value: str = Field(nullable=False)
    description: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
