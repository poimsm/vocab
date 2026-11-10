# src/core/delivery/repository.py
from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import Session, select, col
from core.delivery.enums import DeliveryStatus
from core.enums import ContentSourceType, ContentType
from core.delivery.models import DeliveryBuffer
from logging_client import logger


class DeliveryRepository:
    def __init__(self, session: Session):
        self.session = session

    def push_to_buffer(
        self,
        user_id: int,
        content_id: int,
        source_type: ContentSourceType,
        content_type: ContentType = ContentType.EXAMPLE,
        word_id: Optional[int] = None,
        learning_path_queue_id: Optional[int] = None,
    ) -> DeliveryBuffer:
        """
        Agrega nuevo contenido generado al búfer en estado PENDING.

        IMPORTANTE: word_id debe siempre proporcionarse. En futuros cambios será obligatorio (no Optional).
        Ahora es Optional solo mientras se actualiza la BD.
        """
        item = DeliveryBuffer(
            user_id=user_id,
            content_id=content_id,
            word_id=word_id,
            content_type=content_type,
            source_type=source_type,
            learning_path_queue_id=learning_path_queue_id,
            status=DeliveryStatus.PENDING,
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)

        logger.debug(
            f"[DeliveryRepository] Pushed to buffer: id={item.id}, user_id={user_id}, "
            f"content_id={content_id}, word_id={word_id}, source_type={source_type.value}, "
            f"status={item.status.value}"
        )
        return item

    def get_pending_items(self, user_id: int, limit: int = 10) -> List[DeliveryBuffer]:
        """Obtiene los elementos pendientes del búfer ordenados por posición."""
        statement = (
            select(DeliveryBuffer)
            .where(
                DeliveryBuffer.user_id == user_id,
                DeliveryBuffer.status == DeliveryStatus.PENDING,
            )
            .order_by(DeliveryBuffer.order_position.asc())
            .limit(limit)
        )
        return list(self.session.exec(statement).all())

    def mark_multiple_as_dispatched(self, buffer_ids: list, user_id: int = None) -> int:
        """Marca múltiples contenidos como despachados.

        Args:
            buffer_ids: Lista de IDs de DeliveryBuffer a marcar
            user_id: ID del usuario propietario (recomendado para validación de seguridad)
        """
        if not buffer_ids:
            return 0

        statement = (
            select(DeliveryBuffer)
            .where(
                DeliveryBuffer.id.in_(buffer_ids),
                DeliveryBuffer.status == DeliveryStatus.PENDING,
            )
        )

        # Agregar filtro de user_id si se proporciona (validación de seguridad)
        if user_id is not None:
            statement = statement.where(DeliveryBuffer.user_id == user_id)

        items = self.session.exec(statement).all()

        for item in items:
            item.status = DeliveryStatus.DISPATCHED
            self.session.add(item)

        self.session.commit()
        return len(items)

    def get_non_dispatched_items(self, user_id: int) -> List[DeliveryBuffer]:
        """Obtiene todos los items no-despachados (PENDING, DISPATCHED) para un usuario."""
        statement = (
            select(DeliveryBuffer)
            .where(
                DeliveryBuffer.user_id == user_id,
                col(DeliveryBuffer.status).in_([DeliveryStatus.PENDING, DeliveryStatus.DISPATCHED]),
            )
            .order_by(DeliveryBuffer.created_at.desc())
        )
        return list(self.session.exec(statement).all())

    def get_pending_content(
        self,
        user_id: int,
        limit: int = 10,
        word_id: Optional[int] = None,
        content_type: Optional[ContentType] = None,
        source_type: Optional[ContentSourceType] = None,
    ) -> List[DeliveryBuffer]:
        """
        Obtiene contenido PENDING para un usuario.
        Si word_id es None, obtiene contenido sin restricción, distribuyendo entre diferentes queue_items.
        Si word_id es especificado, obtiene solo contenido de esa palabra.
        Si content_type es especificado, filtra por tipo de contenido.
        Si source_type es especificado, filtra por fuente (BOOST o LEARNING_PATH).
        Retorna en orden LIFO (último en llegar primero).
        """
        statement = (
            select(DeliveryBuffer)
            .where(
                DeliveryBuffer.user_id == user_id,
                DeliveryBuffer.status == DeliveryStatus.PENDING,
            )
        )

        if word_id is not None:
            statement = statement.where(DeliveryBuffer.word_id == word_id)

        if content_type is not None:
            statement = statement.where(DeliveryBuffer.content_type == content_type)

        if source_type is not None:
            statement = statement.where(DeliveryBuffer.source_type == source_type)

        # Get all pending items for distribution
        statement = statement.order_by(DeliveryBuffer.created_at.desc())
        all_items = list(self.session.exec(statement).all())

        # If word_id is NOT specified (learning path), distribute across different queue_items for diversity
        if word_id is None and all_items:
            items_by_queue = {}
            for item in all_items:
                q_id = item.learning_path_queue_id or 0
                if q_id not in items_by_queue:
                    items_by_queue[q_id] = []
                items_by_queue[q_id].append(item)

            # Round-robin through queue items to get diverse content
            result = []
            queue_ids = list(items_by_queue.keys())
            idx = {q_id: 0 for q_id in queue_ids}

            while len(result) < limit and any(idx[q_id] < len(items_by_queue[q_id]) for q_id in queue_ids):
                for q_id in queue_ids:
                    if len(result) >= limit:
                        break
                    if idx[q_id] < len(items_by_queue[q_id]):
                        result.append(items_by_queue[q_id][idx[q_id]])
                        idx[q_id] += 1

            logger.debug(
                f"[DeliveryRepository] get_pending_content: user_id={user_id}, word_id={word_id}, "
                f"content_type={content_type.value if content_type else None}, found {len(result)} items (distributed)"
            )
            return result[:limit]

        results = all_items[:limit]

        logger.debug(
            f"[DeliveryRepository] get_pending_content: user_id={user_id}, word_id={word_id}, "
            f"content_type={content_type.value if content_type else None}, found {len(results)} items"
        )

        return results

    def discard_boost_word_items(self, user_id: int, word_id: int) -> int:
        """Descarta todo el contenido no consumido de una palabra des-boosteada."""
        statement = (
            select(DeliveryBuffer)
            .where(
                DeliveryBuffer.user_id == user_id,
                DeliveryBuffer.word_id == word_id,
                DeliveryBuffer.source_type == ContentSourceType.BOOST,
                col(DeliveryBuffer.status).in_([DeliveryStatus.PENDING, DeliveryStatus.DISPATCHED]),
            )
        )
        items = self.session.exec(statement).all()
        for item in items:
            item.status = DeliveryStatus.DISCARDED
            self.session.add(item)

        self.session.commit()
        return len(items)

    def get_pending_learning_path_content(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> List[DeliveryBuffer]:
        """
        Obtiene contenido PENDING de learning path para un usuario.
        Verifica si hay contenido disponible después de la generación.
        """
        statement = (
            select(DeliveryBuffer)
            .where(
                DeliveryBuffer.user_id == user_id,
                DeliveryBuffer.content_type == content_type,
                DeliveryBuffer.source_type == ContentSourceType.LEARNING_PATH,
                DeliveryBuffer.status == DeliveryStatus.PENDING,
            )
        )
        return list(self.session.exec(statement).all())

