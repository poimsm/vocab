from typing import List, Dict
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
        buffer_delivery_ids: List[int],
        delivery_items_map: Dict,
        user_id: int,
    ) -> list:
        """
        Convierte buffer de delivery items a respuesta de best options.

        Args:
            buffer_delivery_ids: Lista de IDs de delivery buffer
            delivery_items_map: Mapa de delivery items por ID
            user_id: ID del usuario

        Returns:
            Lista de best options formateados
        """
        logger.debug(f"[BestOptionsResponseBuilder] Building best options response for user {user_id}")
        logger.debug(f"[BestOptionsResponseBuilder] buffer_delivery_ids: {buffer_delivery_ids}")
        logger.debug(f"[BestOptionsResponseBuilder] delivery_items_map keys: {delivery_items_map.keys()}")

        if not buffer_delivery_ids:
            logger.debug(f"[BestOptionsResponseBuilder] No buffer_delivery_ids provided, returning empty list")
            return []

        # Obtener best options
        best_option_ids = [
            delivery_items_map[did].content_id
            for did in buffer_delivery_ids
            if did in delivery_items_map
        ]
        logger.debug(f"[BestOptionsResponseBuilder] best_option_ids extracted: {best_option_ids}")

        best_options = self.db.exec(
            select(BestOption)
            .where(BestOption.id.in_(best_option_ids))
            .options(joinedload(BestOption.word))
        ).all()

        logger.debug(f"[BestOptionsResponseBuilder] Retrieved {len(best_options) if best_options else 0} best option records from database")

        # Construir respuesta manteniendo orden del buffer
        items_response = []
        best_option_map = {bo.id: bo for bo in best_options}

        for delivery_id in buffer_delivery_ids:
            if delivery_id not in delivery_items_map:
                continue

            delivery_item = delivery_items_map[delivery_id]
            best_option = best_option_map.get(delivery_item.content_id)

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
                "delivery_id": delivery_id,
                "queue_item_id": delivery_item.learning_path_queue_id,
                "best_option_id": best_option.id,
                "word": word_data,
                "question": best_option.question,
                "options": best_option.options.split(";"),
                "correct_option": best_option.correct_option,
                "source_type": delivery_item.source_type.value,
            })

            logger.info(
                f"[BestOptionsResponseBuilder] Built best option for delivery_id={delivery_id}: "
                f"source_type={delivery_item.source_type.value}, "
                f"queue_item_id={delivery_item.learning_path_queue_id}, "
                f"word_id={delivery_item.word_id}, "
                f"content_id={delivery_item.content_id}"
            )

        logger.info(
            f"[BestOptionsResponseBuilder] Built {len(items_response)} best options for response. "
            f"Queue IDs: {[bo.get('queue_item_id') for bo in items_response]}"
        )
        return items_response
