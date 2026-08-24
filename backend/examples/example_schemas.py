from pydantic import BaseModel
from typing import List, Optional


class TargetWord(BaseModel):
    """Schema para una palabra target dentro de un segmento de texto"""
    id: int
    main: str
    type: str
    meaning: str
    level: int
    is_boosted: bool


class TextSegment(BaseModel):
    """Schema para un segmento de texto (con o sin palabra target)"""
    text: str
    is_highlighted: bool
    target_word: Optional[TargetWord] = None


class ExploreExample(BaseModel):
    """Schema para un ejemplo con texto segmentado"""
    queue_item_id: int
    example_id: int
    text: List[TextSegment]
    extracted_words: List[str]


class ExploreResponse(BaseModel):
    """Schema de respuesta para el endpoint /explore de ejemplos"""
    examples: List[ExploreExample]
    status: str = "ok"


class ExampleResolutionResponse(BaseModel):
    """Schema de respuesta para resolver un ejemplo"""
    status: str
