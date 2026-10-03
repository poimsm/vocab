"""
Adapter que implementa ContentRepository para BestOptions.
Wrappea BestOptionRepository para cumplir el contrato de LearningPathService.
"""
from typing import Optional
from sqlmodel import Session
from logging_client import logger
from features.best_options.repository import BestOptionRepository


class BestOptionsContentRepository:
    """
    Implementa ContentRepository Protocol para BestOptions.
    Adapta BestOptionRepository al contrato esperado por LearningPathService.
    """

    def __init__(self, db: Session):
        self.db = db
        self.best_option_repo = BestOptionRepository(db)

    def count_available_for_word(self, word_id: int) -> int:
        """Cuenta best_options disponibles para una palabra"""
        return self.best_option_repo.count_available_best_options_for_word(word_id)

    def get_available_content_for_word(self, word_id: int) -> Optional[int]:
        """Obtiene el próximo best_option disponible para una palabra"""
        return self.best_option_repo.get_available_content_for_word(word_id)

    def get_word_id(self, content_id: int) -> Optional[int]:
        """Obtiene el word_id asociado a un best_option"""
        return self.best_option_repo.get_word_id(content_id)
