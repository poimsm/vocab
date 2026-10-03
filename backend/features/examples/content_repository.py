"""
Adapter que implementa ContentRepository para Examples.
Wrappea ExampleRepository para cumplir el contrato de LearningPathService.
"""
from typing import Optional
from sqlmodel import Session, func, select
from logging_client import logger
from features.examples.models import Example
from features.words.models import WordStatistics
from core.enums import ContentType
from core.learning_path.models import LearningState
from features.examples.repository import ExampleRepository


class ExampleContentRepository:
    """
    Implementa ContentRepository Protocol para Examples.
    Adapta ExampleRepository al contrato esperado por LearningPathService.
    """

    def __init__(self, db: Session):
        self.db = db
        self.example_repo = ExampleRepository(db)

    def count_available_for_word(self, word_id: int) -> int:
        """Cuenta examples disponibles para una palabra"""
        # Examples están disponibles si tienen la palabra y no están consumidos
        count = self.db.exec(
            select(func.count(Example.id))
            .join(
                WordStatistics,
                (WordStatistics.word_id == word_id)
                & (WordStatistics.type == ContentType.EXAMPLE),
            )
            .where(
                Example.is_consumed == False,
                WordStatistics.learning_state != LearningState.LEARNED,
            )
        ).first() or 0

        return count

    def get_available_content_for_word(self, word_id: int) -> Optional[int]:
        """Obtiene el próximo example disponible para una palabra"""
        # Buscar un example que contenga la palabra y no esté consumido
        example_id = self.db.exec(
            select(Example.id)
            .join(
                WordStatistics,
                (WordStatistics.word_id == word_id)
                & (WordStatistics.type == ContentType.EXAMPLE),
            )
            .where(
                Example.is_consumed == False,
                WordStatistics.learning_state != LearningState.LEARNED,
            )
            .order_by(Example.created_at.asc())
            .limit(1)
        ).first()

        return example_id

    def get_word_id(self, content_id: int) -> Optional[int]:
        """Obtiene el word_id de un example (primera palabra target)"""
        return self.example_repo.get_first_target_word_id(content_id)
