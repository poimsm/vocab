from pydantic import BaseModel
from typing import List, Optional


class TextSegment(BaseModel):
    """Segmento de texto con información de destacado"""
    text: str
    is_highlighted: bool


class CollocationItem(BaseModel):
    """Schema para una colocación individual"""
    id: int
    phrase: str
    word_id: Optional[int] = None
    text: List[TextSegment]
    is_marked: bool = False


class CollocationListResponse(BaseModel):
    """Schema de respuesta para el endpoint de lista de colocaciones"""
    items: List[CollocationItem]
    total: int


class CollocationCreateRequest(BaseModel):
    """Schema para crear una colocación"""
    phrase: str
    word_id: Optional[int] = None


class CollocationToggleRequest(BaseModel):
    """Schema para actualizar el estado de marcado de una colocación"""
    is_marked: bool
