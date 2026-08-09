# backend/schemas/explore.py

from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from logging_client import logger


class ExploreWordSchema(BaseModel):
    id: int
    main: str
    type: str
    meaning: Optional[str] = None
    level: Optional[int] = None
    is_boosted: bool = False
    batch_id: Optional[int] = None


class TextSegmentSchema(BaseModel):
    text: str
    is_highlighted: bool = False
    target_word: Optional[ExploreWordSchema] = None


class ExploreExampleSchema(BaseModel):
    id: int
    text: List[TextSegmentSchema]


class ExploreResponse(BaseModel):
    examples: List[ExploreExampleSchema]
    status: str = "ok"