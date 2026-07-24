# backend/schemas/explore.py

from pydantic import BaseModel
from typing import List, Optional


class ExploreWordSchema(BaseModel):
    id: int
    main: str
    type: str
    meaning: Optional[str] = None
    level: Optional[int] = None
    is_boosted: bool = False
    batch_id: Optional[int] = None


class ExploreExampleSchema(BaseModel):
    id: int
    text: str
    target_words: List[ExploreWordSchema]


class ExploreResponse(BaseModel):
    examples: List[ExploreExampleSchema]
    active_batch_id: Optional[int] = None
    active_batch_title: Optional[str] = None
    total_queue_remaining: int