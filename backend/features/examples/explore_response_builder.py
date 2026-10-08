from typing import List
from sqlmodel import Session, select
from features.examples.models import Example
from logging_client import logger
from features.examples.repository import ExampleRepository
from features.examples.helpers import extract_words_from_example


class ExploreResponseBuilder:
    """Construye respuestas de ejemplos para el endpoint explore"""

    def __init__(self, db: Session):
        self.db = db
        self.example_repo = ExampleRepository(db)
        self.common_words = self._load_common_words()

    def build_examples_response(
        self,
        buffer_delivery_ids: List[int],
        delivery_items_map: dict,
        user_id: int,
    ) -> list:
        """
        Convierte buffer de delivery items a respuesta de ejemplos.

        Args:
            buffer_delivery_ids: Lista de IDs de delivery buffer
            delivery_items_map: Mapa de delivery items por ID
            user_id: ID del usuario

        Returns:
            Lista de ejemplos formateados con segmentación de texto
        """
        logger.debug(f"[ExploreResponseBuilder] Building examples response for user {user_id}")
        logger.debug(f"[ExploreResponseBuilder] buffer_delivery_ids: {buffer_delivery_ids}")
        logger.debug(f"[ExploreResponseBuilder] delivery_items_map keys: {delivery_items_map.keys()}")

        if not buffer_delivery_ids:
            logger.debug(f"[ExploreResponseBuilder] No buffer_delivery_ids provided, returning empty list")
            return []

        # Obtener ejemplos
        example_ids = [
            delivery_items_map[did].content_id
            for did in buffer_delivery_ids
            if did in delivery_items_map
        ]
        logger.debug(f"[ExploreResponseBuilder] example_ids extracted: {example_ids}")

        examples = self.db.exec(
            select(Example).where(Example.id.in_(example_ids))
        ).all()

        logger.debug(f"[ExploreResponseBuilder] Retrieved {len(examples) if examples else 0} examples from database")

        examples_response = []

        # Mantener orden del buffer
        for delivery_id in buffer_delivery_ids:
            if delivery_id not in delivery_items_map:
                continue

            delivery_item = delivery_items_map[delivery_id]
            ex = next((e for e in examples if e.id == delivery_item.content_id), None)

            if not ex:
                continue

            text_segments = self.example_repo.segment_example_text(ex)
            target_word_ids = {
                seg["target_word"]["id"]
                for seg in text_segments
                if seg.get("target_word")
            }
            target_word_strings = {
                seg["target_word"]["main"].lower()
                for seg in text_segments
                if seg.get("target_word")
            }

            extracted_words = extract_words_from_example(
                text_segments, target_word_ids, self.common_words
            )
            extracted_words = [w for w in extracted_words if w not in target_word_strings]

            example_response = {
                "delivery_id": delivery_id,
                "queue_item_id": delivery_item.learning_path_queue_id,
                "example_id": ex.id,
                "text": text_segments,
                "extracted_words": extracted_words,
                "is_favorite": ex.is_favorite,
                "is_marked": ex.is_marked,
                "source_type": delivery_item.source_type.value,
                "word_id": delivery_item.word_id,
            }

            logger.info(
                f"[ExploreResponseBuilder] Built example for delivery_id={delivery_id}: "
                f"source_type={delivery_item.source_type.value}, "
                f"queue_item_id={delivery_item.learning_path_queue_id}, "
                f"word_id={delivery_item.word_id}, "
                f"content_id={delivery_item.content_id}"
            )

            examples_response.append(example_response)

        logger.info(
            f"[ExploreResponseBuilder] Built {len(examples_response)} examples for response. "
            f"Queue IDs: {[ex.get('queue_item_id') for ex in examples_response]}"
        )
        return examples_response

    def _load_common_words(self):
        """Carga el set de palabras comunes desde most_common.txt."""
        from pathlib import Path

        possible_paths = [
            Path(__file__).parent.parent.parent / "data" / "most_common.txt",
            Path("/app/data") / "most_common.txt",
        ]

        common_words_path = None
        for path in possible_paths:
            if path.exists():
                common_words_path = path
                break

        if not common_words_path:
            logger.warning(f"[ExploreResponseBuilder] Common words file not found")
            return set()

        common_words = set()
        with open(common_words_path, "r", encoding="utf-8") as f:
            import re
            for word in f.readlines():
                word = word.strip().lower()
                if word:
                    normalized = re.sub(r"'s$", "", word).replace("'", "")
                    common_words.add(normalized)

        return common_words
