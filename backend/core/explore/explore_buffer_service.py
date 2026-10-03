from typing import List
from sqlmodel import Session, select
from logging_client import logger

from core.enums import ContentType
from core.explore.protocols import ContentValidator


class ExploreBufferService:
    """
    Servicio agnóstico para gestionar el buffer de explore del usuario (mostrado en frontend).

    Responsabilidades:
    - Validar items del buffer (removiendo aquellos con palabras LEARNED)
    - Refill del buffer desde DeliveryBuffer
    - Ajuste de posición después de remociones
    - Cargar nuevos batches desde DeliveryBuffer

    Las dependencias se inyectan para mantener desacoplamiento de features.
    """

    def __init__(self, db: Session, content_validator: ContentValidator):
        self.db = db
        self.content_validator = content_validator
        from core.delivery.service import DeliveryService
        self.delivery_service = DeliveryService(db)

    def is_delivery_item_learned(self, content_id, user_id: int) -> bool:
        """Chequea si el contenido de un delivery item está aprendido"""
        return self.content_validator.is_content_learned(content_id, user_id)

    def validate_buffer_items(
        self,
        buffer_delivery_ids: List[int],
        user_id: int,
    ) -> List[int]:
        """
        Valida items del buffer, removiendo aquellos con palabras LEARNED y duplicados.

        Returns:
            Lista de IDs válidos sin duplicados
        """
        if not buffer_delivery_ids:
            return []

        # Obtener delivery items para validar a través del servicio
        delivery_items = self.delivery_service.get_delivery_items_by_ids(buffer_delivery_ids, user_id)

        item_map = {item.id: item for item in delivery_items}
        valid_ids = []
        seen_ids = set()

        for delivery_id in buffer_delivery_ids:
            if delivery_id in seen_ids:
                logger.debug(f"[validate_buffer_items] Item {delivery_id} is duplicate, skipping")
                continue

            if delivery_id not in item_map:
                logger.debug(f"[validate_buffer_items] Item {delivery_id} not found, skipping")
                continue

            delivery_item = item_map[delivery_id]
            if self.is_delivery_item_learned(delivery_item.content_id, user_id):
                logger.debug(f"[validate_buffer_items] Item {delivery_id} (content_id={delivery_item.content_id}) has LEARNED word, removing")
                continue

            valid_ids.append(delivery_id)
            seen_ids.add(delivery_id)

        return valid_ids

    def adjust_position_after_removals(
        self,
        buffer_delivery_ids: List[int],
        valid_ids: List[int],
        buffer_position: int,
    ) -> int:
        """
        Calcula la nueva posición después de remover items del buffer.

        Returns:
            Nueva posición ajustada
        """
        removed_before_position = 0
        for i, delivery_id in enumerate(buffer_delivery_ids):
            if i < buffer_position and delivery_id not in valid_ids:
                removed_before_position += 1

        new_position = max(0, buffer_position - removed_before_position)

        if valid_ids:
            new_position = min(new_position, len(valid_ids) - 1)
        else:
            new_position = 0

        return new_position

    def refill_buffer(
        self,
        buffer_ids: List[int],
        content_type: ContentType,
        limit: int,
        user_id: int,
    ) -> List[int]:
        """
        Refill buffer hasta alcanzar limit, obteniendo items desde DeliveryBuffer.

        Returns:
            Lista de IDs del delivery buffer rellenado
        """
        if len(buffer_ids) >= limit:
            return buffer_ids

        logger.debug(
            f"[refill_buffer] Buffer has {len(buffer_ids)}, filling to {limit}"
        )

        final_ids = list(buffer_ids)
        buffer_ids_set = set(buffer_ids)
        amount_needed = limit - len(final_ids)

        # Obtener items desde delivery service (mixed content)
        result = self.delivery_service.get_mixed_content(user_id, content_type, amount_needed)
        status = result["status"]
        delivery_items = result["content"]

        logger.debug(
            f"[refill_buffer] DeliveryService status={status}, found {len(delivery_items)} items"
        )

        if not delivery_items:
            logger.info(f"[refill_buffer] No content available from delivery service")
            return final_ids

        # Agregar items únicos al buffer
        items_added = 0
        for item in delivery_items:
            delivery_id = item.get("id")
            if not delivery_id:
                continue

            if delivery_id in buffer_ids_set:
                logger.debug(f"[refill_buffer] Item {delivery_id} already in buffer, skipping")
                continue

            # Validar que no esté aprendido (double-check)
            content_id = item.get("content_id")
            if content_id and self.content_validator.is_content_learned(content_id, user_id):
                logger.debug(f"[refill_buffer] Content {content_id} is LEARNED, skipping")
                continue

            final_ids.append(delivery_id)
            buffer_ids_set.add(delivery_id)
            items_added += 1

            if len(final_ids) >= limit:
                break

        logger.debug(
            f"[refill_buffer] Added {items_added} items, buffer now has {len(final_ids)}"
        )

        return final_ids

    def load_next_batch(
        self,
        user_id: int,
        content_type: ContentType,
        limit: int,
    ) -> List[int]:
        """
        Carga un nuevo batch de items desde DeliveryBuffer.

        Returns:
            Lista de IDs de delivery buffer items cargados
        """
        logger.debug(f"[load_next_batch] Loading {limit} items for user {user_id}")

        # Obtener items desde delivery service (mixed content)
        result = self.delivery_service.get_mixed_content(user_id, content_type, limit)
        status = result["status"]
        delivery_items = result["content"]

        logger.debug(
            f"[load_next_batch] DeliveryService status={status}, found {len(delivery_items)} items"
        )

        # Extraer delivery buffer IDs
        batch_ids = []
        for item in delivery_items:
            delivery_id = item.get("id")
            if delivery_id:
                batch_ids.append(delivery_id)

        return batch_ids
