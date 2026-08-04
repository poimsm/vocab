from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from logging_client import logger


class WordCreate(BaseModel):
    main: str
    meaning: Optional[str] = None
    type: Optional[str] = None
    level: Optional[int] = None
    frequency: Optional[str] = None
    context: Optional[str] = None
    source_text: Optional[str] = None
    synonyms: Optional[List[str]] = None


class WordResponse(BaseModel):
    id: int
    main: str
    created_at: datetime


class ReopenBatchesRequest(BaseModel):
    batch_ids: List[int]
