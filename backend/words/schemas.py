from sqlmodel import SQLModel
from datetime import datetime
from logging_client import logger


class WordCreate(SQLModel):
    text: str


class WordResponse(SQLModel):
    id: int
    text: str
    created_at: datetime


class FavoriteResponse(SQLModel):
    id: int
    example_id: int
    created_at: datetime
