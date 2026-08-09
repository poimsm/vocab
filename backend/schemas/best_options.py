# backend/schemas/best_options.py

from pydantic import BaseModel
from typing import List, Optional


class BestOptionWordSchema(BaseModel):
    id: int
    main: str
    type: str
    meaning: Optional[str] = None
    level: Optional[int] = None
    is_boosted: bool = False
    batch_id: Optional[int] = None


class BestOptionItemSchema(BaseModel):
    id: int
    queue_item_id: int
    content_id: int
    question: str
    options: List[str]
    correct_option: int
    word: BestOptionWordSchema


class BestOptionResponse(BaseModel):
    items: List[BestOptionItemSchema]
    status: str = "ok"
