from pydantic import BaseModel
from typing import List, Optional


class ExampleItem(BaseModel):
    """Schema para un ejemplo individual en la respuesta"""
    queue_item_id: int
    example_id: int
    text: str
    type: str


class ExploreResponse(BaseModel):
    """Schema de respuesta para el endpoint /explore de ejemplos"""
    items: List[ExampleItem]
    total: int
    status: Optional[str] = "ok"


class ExampleResolutionResponse(BaseModel):
    """Schema de respuesta para resolver un ejemplo"""
    status: str
