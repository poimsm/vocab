from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from core.generation_ai.enums import GenerationAIStatus


class GenerationAIRegistry(SQLModel, table=True):
    __tablename__: str = "generation_ai_queue"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    central_queue_id: Optional[int] = Field(
        foreign_key="central_queue.id", nullable=True)
    status: GenerationAIStatus = Field(
        default=GenerationAIStatus.PENDING, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    word_id: int = Field(index=True, nullable=False)
    source_type: str = Field(index=True, nullable=False)
