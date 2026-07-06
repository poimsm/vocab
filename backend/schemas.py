from sqlmodel import SQLModel
from datetime import datetime
from typing import List, Optional


class WordCreate(SQLModel):
    text: str


class WordResponse(SQLModel):
    id: int
    text: str
    created_at: datetime


class ExampleResponse(SQLModel):
    id: int
    content: str
    created_at: datetime


class FavoriteResponse(SQLModel):
    id: int
    example_id: int
    created_at: datetime


class DailyResponse(SQLModel):
    words: List[str]
    examples: List[str]


class ListResponse(SQLModel):
    id: int
    name: str


class ListItemResponse(SQLModel):
    id: int
    content: str


class ListDetailResponse(SQLModel):
    id: int
    name: str
    items: List[ListItemResponse]
