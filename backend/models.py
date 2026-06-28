from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import JSON

# Mantenemos tu clase WordLevel intacta ya que es lógica pura
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


# 1. TABLA INTERMEDIA (Muchos a Muchos con datos extra)
class ExampleWord(SQLModel, table=True):
    __tablename__: str = "example_words"

    example_id: int = Field(foreign_key="examples.id", primary_key=True)
    word_id: int = Field(foreign_key="words.id", primary_key=True)
    text_form: str = Field(max_length=255, nullable=False)

    # Relaciones inversas en SQLModel usando Relationship
    example: "Example" = Relationship(back_populates="example_words")
    word: "Word" = Relationship(back_populates="example_words")


# 2. MODELO WORD
class Word(SQLModel, table=True):
    __tablename__: str = "words"

    id: Optional[int] = Field(default=None, primary_key=True)
    main: str = Field(max_length=255, nullable=False, index=True)
    meaning: Optional[str] = Field(default=None) # Text en Postgres se maneja con str normal
    type: Optional[str] = Field(default=None, max_length=50) # word | phrase | idiom | phrasal verb
    frequency: Optional[str] = Field(default=None, max_length=50)
    level: int = Field(default=WordLevel.INTERMEDIATE)
    context: Optional[str] = Field(default=None, max_length=50)
    source_text: Optional[str] = Field(default=None)
    
    normalized: Optional[str] = Field(default=None, max_length=255, unique=True, index=True)
    is_favorite: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_learned: bool = Field(default=False)

    # Relaciones
    # sa_relationship_kwargs={"uselist": False} define la relación 1 a 1
    stats: Optional["WordStats"] = Relationship(back_populates="word", sa_relationship_kwargs={"uselist": False})
    example_words: List[ExampleWord] = Relationship(back_populates="word")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# 3. MODELO WORD STATS (Relación 1:1 con Word)
class WordStats(SQLModel, table=True):
    __tablename__: str = "word_stats"

    word_id: int = Field(foreign_key="words.id", primary_key=True)
    last_seen_at: Optional[datetime] = Field(default=None)
    times_seen: int = Field(default=0)
    times_favorited: int = Field(default=0)

    word: Word = Relationship(back_populates="stats")


# 4. MODELO EXAMPLE
class Example(SQLModel, table=True):
    __tablename__: str = "examples"

    id: Optional[int] = Field(default=None, primary_key=True)
    text: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: Optional[str] = Field(default=None, max_length=50)
    is_active: bool = Field(default=True)
    is_favorite: bool = Field(default=False)
    times_seen: int = Field(default=0)

    example_words: List[ExampleWord] = Relationship(back_populates="example")


# 5. MODELO ACTIVITY (Manejo de JSON nativo de Postgres)
class Activity(SQLModel, table=True):
    __tablename__: str = "activities"

    id: Optional[int] = Field(default=None, primary_key=True)
    action: str = Field(max_length=100, nullable=False)
    
    # 🔥 CORRECCIÓN: Le decimos explícitamente a SQLModel que use el tipo JSON de SQLAlchemy
    payload: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON) 
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))