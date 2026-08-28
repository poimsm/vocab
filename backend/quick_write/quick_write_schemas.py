from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class QuickWriteCreate(BaseModel):
    prompt: str
    emoji: str = "✍️"
    words: Optional[list[str]] = None
    original_content: Optional[str] = None


class QuickWriteUpdate(BaseModel):
    original_content: Optional[str] = None
    is_favorite: Optional[bool] = None


class QuickWriteResponse(BaseModel):
    id: int
    prompt: str
    emoji: str
    words: Optional[list[str]] = None
    original_content: Optional[str] = None
    corrected_content: Optional[str] = None
    has_corrections: bool
    is_favorite: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QuickWriteListResponse(BaseModel):
    items: list[QuickWriteResponse]
    total: int


class GenerateQuickWriteRequest(BaseModel):
    word_ids: Optional[list[int]] = None
    user_id: Optional[int] = None
