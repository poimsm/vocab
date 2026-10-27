"""Schemas for Vocabulary Images feature"""
from pydantic import BaseModel
from typing import Optional


class AddVocabImageWordRequest(BaseModel):
    """Request to add a word from vocabulary image"""
    vocab_image_word_id: str
    word: str
    definition: Optional[str] = None


class AddVocabImageWordResponse(BaseModel):
    """Response when adding a word from vocabulary image"""
    status: str  # "success", "existing", "error"
    message: str
    word_id: Optional[int] = None
