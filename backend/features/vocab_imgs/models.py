import uuid
from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Relationship


class VocabImage(SQLModel, table=True):
    """Modelo para almacenar temas de vocabulario con metadata"""
    __tablename__: str = "vocab_images"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    name: str = Field(max_length=100, nullable=False, index=True)
    description: Optional[str] = Field(default=None, max_length=500)
    cover_image: Optional[str] = Field(default=None, max_length=255)
    main_image: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = Field(default=True, index=True)

    # Relationships
    words: List["VocabImageWord"] = Relationship(back_populates="vocab_image")

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VocabImageWord(SQLModel, table=True):
    """Modelo para asociar palabras con temas de vocabulario"""
    __tablename__: str = "vocab_image_words"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    vocab_image_id: str = Field(foreign_key="vocab_images.id", index=True)
    word: str = Field(max_length=100, nullable=False, index=True)
    definition: Optional[str] = Field(default=None, max_length=500)
    category: Optional[str] = Field(default=None, max_length=50, index=True)
    word_order: Optional[int] = Field(default=None, index=True)  # Para mantener orden

    # Relationships
    vocab_image: VocabImage = Relationship(back_populates="words")

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
