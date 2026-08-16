from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CreateWordFromTextRequest(BaseModel):
    """Schema para crear palabra desde texto libre"""
    text: str = Field(..., description="Texto libre para extraer la palabra")


class CreateWordRequest(BaseModel):
    """Schema para crear/actualizar una palabra con datos completos"""
    main: str = Field(..., description="Palabra principal")
    meaning: Optional[str] = Field(None, description="Significado")
    synonyms: Optional[List[str]] = Field(None, description="Sinónimos")
    type: Optional[str] = Field(None, description="Tipo de palabra (noun, verb, etc)")
    frequency: Optional[str] = Field(None, description="Frecuencia")
    level: Optional[int] = Field(None, description="Nivel de dificultad")
    context: Optional[str] = Field(None, description="Contexto")


class WordListItem(BaseModel):
    """Schema para palabra en lista"""
    id: int
    main: str
    meaning: Optional[str]
    synonyms: Optional[List[str]]
    type: Optional[str]
    frequency: Optional[str]
    level: str
    context: Optional[str]
    is_favorite: bool
    is_learned: bool
    total_examples: int


class WordDetail(BaseModel):
    """Schema para detalles completos de palabra"""
    id: int
    main: str
    meaning: Optional[str]
    synonyms: Optional[List[str]]
    type: Optional[str]
    frequency: Optional[str]
    level: str
    context: Optional[str]
    source_text: Optional[str]
    is_favorite: bool
    is_learned: bool
    created_at: datetime
    total_examples: int
    examples: List[str]


class WordResponse(BaseModel):
    """Schema para respuesta genérica de palabra"""
    id: int
    main: str
    meaning: Optional[str] = None


class CreateWordResponse(BaseModel):
    """Schema para respuesta de creación de palabra"""
    id: int
    main: str
    meaning: Optional[str]
    message: str


class FavoriteToggleResponse(BaseModel):
    """Schema para respuesta de toggle favorito"""
    id: int
    is_favorite: bool
