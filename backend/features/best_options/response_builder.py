from typing import List
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload

from features.best_options.models import BestOption
from logging_client import logger


class BestOptionsResponseBuilder:
    """Construye respuestas de best options para el endpoint explore"""

    def __init__(self, db: Session):
        self.db = db

    def build_best_options_response(
        self,
        queue_items: List,
        user_id: int,
    ) -> list:
        """
        Convierte queue items a respuesta de best options.

        Args:
            queue_items: Lista de ContentQueue items con content_id
            user_id: ID del usuario

        Returns:
            Lista de best options formateados
        """
        if not queue_items:
            return []

        # Obtener best options
        best_option_ids = [item.content_id for item in queue_items]
        best_options = self.db.exec(
            select(BestOption)
            .where(BestOption.id.in_(best_option_ids))
            .options(joinedload(BestOption.word))
        ).all()

        logger.debug(f"[build_best_options_response] Retrieved {len(best_options)} best option records")

        # Construir respuesta manteniendo orden
        items_response = []
        best_option_map = {bo.id: bo for bo in best_options}

        for queue_item in queue_items:
            best_option = best_option_map.get(queue_item.content_id)
            if not best_option:
                continue

            word_data = {
                "id": best_option.word.id,
                "main": best_option.word.main,
                "meaning": best_option.word.meaning,
                "type": best_option.word.type,
                "level": best_option.word.level,
                "synonyms": best_option.word.synonyms or [],
                "frequency": best_option.word.frequency,
                "examples": [],
            }

            items_response.append({
                "queue_item_id": queue_item.id,
                "best_option_id": best_option.id,
                "word": word_data,
                "question": best_option.question,
                "options": best_option.options.split(";"),
                "correct_option": best_option.correct_option,
            })

        return items_response
