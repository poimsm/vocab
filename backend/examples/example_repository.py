from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import joinedload
from sqlmodel import Session, func, or_, select
from logging_client import logger
from models import ContentQueue, ContentQueueStatus

import random
from models import (
    Example,
    ExampleWord,
    WordStatistics,
    ContentType,
    ExampleType,
    Word,
)


class ExampleRepository:
    """
    Repository para la gestión de Examples.
    """

    def __init__(self, session: Session):
        self.session = session

    def get_available_content_for_path(self, user_id: int) -> List[int]:
        """
        Obtiene IDs de examples pristine que no están en ContentQueue.

        Estos examples pueden ser reutilizados en lugar de generar nuevos.
        """

        # Obtener IDs de examples ya encolados
        enqueued_ids = self.session.exec(
            select(ContentQueue.content_id)
            .where(
                ContentQueue.user_id == user_id,
                ContentQueue.type == ContentType.EXAMPLE,
                ContentQueue.status == ContentQueueStatus.PENDING,
            )
        ).all()

        enqueued_ids = set(enqueued_ids)

        # Obtener examples pristine que no estén encolados
        examples = self.session.exec(
            select(Example.id)
            .where(
                Example.id.notin_(enqueued_ids) if enqueued_ids else True,
            )
        ).all()

        return examples

    def get_word_ids(self, example_id: int) -> List[int]:
        """
        Obtiene los IDs de las palabras asociadas a un example.
        """
        word_ids = self.session.exec(
            select(ExampleWord.word_id)
            .where(ExampleWord.example_id == example_id)
        ).all()

        return word_ids

    def save(self, example: Example) -> Example:
        """
        Guarda un example en la base de datos.
        """
        self.session.add(example)
        self.session.commit()
        self.session.refresh(example)
        return example

