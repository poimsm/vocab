from pydantic import BaseModel
from typing import List, Optional


class BestOptionItem(BaseModel):
    """Schema para un best option individual en la respuesta"""
    queue_item_id: int
    best_option_id: int
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
