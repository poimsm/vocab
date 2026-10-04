# src/core/delivery/repository.py
from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import Session, select, col
from core.delivery.enums import DeliveryStatus
from core.enums import ContentSourceType, ContentType
from core.delivery.models import DeliveryBuffer


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
        """Agrega nuevo contenido generado al búfer en estado PENDING."""
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

    def mark_as_dispatched(self, buffer_id: int) -> Optional[DeliveryBuffer]:
        """Marca un contenido como despachado al usuario (enviado al explore buffer)."""
        item = self.session.get(DeliveryBuffer, buffer_id)
        if item and item.status == DeliveryStatus.PENDING:
            item.status = DeliveryStatus.DISPATCHED
            self.session.add(item)
            self.session.commit()
            self.session.refresh(item)
        return item

    def mark_multiple_as_dispatched(self, buffer_ids: list) -> int:
        """Marca múltiples contenidos como despachados."""
        if not buffer_ids:
            return 0

        statement = (
            select(DeliveryBuffer)
            .where(
                DeliveryBuffer.id.in_(buffer_ids),
                DeliveryBuffer.status == DeliveryStatus.PENDING,
            )
        )
        items = self.session.exec(statement).all()

        for item in items:
            item.status = DeliveryStatus.DISPATCHED
            self.session.add(item)

        self.session.commit()
        return len(items)

    def mark_as_served(self, buffer_id: int) -> Optional[DeliveryBuffer]:
        """Marca un contenido como entregado/mostrado en la pantalla del usuario."""
        item = self.session.get(DeliveryBuffer, buffer_id)
        if item and item.status == DeliveryStatus.PENDING:
            item.status = DeliveryStatus.DISPATCHED
            self.session.add(item)
            self.session.commit()
            self.session.refresh(item)
        return item

    def mark_as_consumed(self, buffer_id: int) -> Optional[DeliveryBuffer]:
        """Marca el contenido como completado/superado por el usuario."""
        item = self.session.get(DeliveryBuffer, buffer_id)
        if item and item.status == DeliveryStatus.DISPATCHED:
            item.status = DeliveryStatus.DISPATCHED
            item.consumed_at = datetime.now(timezone.utc)
            self.session.add(item)
            self.session.commit()
            self.session.refresh(item)
        return item

    def get_non_dispatched_items(self, user_id: int) -> List[DeliveryBuffer]:
        """Obtiene todos los items no-despachados (PENDING, SERVED) para un usuario."""
        statement = (
            select(DeliveryBuffer)
            .where(
                DeliveryBuffer.user_id == user_id,
                col(DeliveryBuffer.status).in_([DeliveryStatus.PENDING, DeliveryStatus.SERVED]),
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
    ) -> List[DeliveryBuffer]:
        """
        Obtiene contenido PENDING para un usuario.
        Si word_id es None, obtiene contenido sin restricción.
        Si word_id es especificado, obtiene solo contenido de esa palabra.
        Si content_type es especificado, filtra por tipo de contenido.
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

        statement = statement.order_by(DeliveryBuffer.created_at.desc()).limit(limit)

        return list(self.session.exec(statement).all())

    def discard_boost_word_items(self, user_id: int, word_id: int) -> int:
        """Descarta todo el contenido no consumido de una palabra des-boosteada."""
        statement = (
            select(DeliveryBuffer)
            .where(
                DeliveryBuffer.user_id == user_id,
                DeliveryBuffer.word_id == word_id,
                DeliveryBuffer.source_type == ContentSourceType.BOOST,
                col(DeliveryBuffer.status).in_([DeliveryStatus.PENDING, DeliveryStatus.SERVED]),
            )
        )
        items = self.session.exec(statement).all()
        for item in items:
            item.status = DeliveryStatus.DISCARDED
            self.session.add(item)

        self.session.commit()
        return len(items)