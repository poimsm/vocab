from pydantic import BaseModel
from typing import List, Optional


class WordExample(BaseModel):
    """Schema para un ejemplo de una palabra"""
    id: int
    text: str
    is_favorite: bool


class WordInfo(BaseModel):
    """Schema para información de una palabra"""
    id: int
    main: str
    meaning: Optional[str] = None
    type: Optional[str] = None
    level: int
    synonyms: Optional[List[str]] = None
    frequency: Optional[str] = None
    examples: List[WordExample] = []


class BestOptionItem(BaseModel):
    """Schema para un best option individual en la respuesta"""
    id: int
    queue_item_id: int
    word: WordInfo
    question: str
    options: List[str]
    correct_option: int


class BestOptionResponse(BaseModel):
    """Schema de respuesta para el endpoint /explore de best options"""
    items: List[BestOptionItem]
    total: int
    status: str = "ok"


class BestOptionResolutionResponse(BaseModel):
    """Schema de respuesta para resolver un best option"""
    status: str
