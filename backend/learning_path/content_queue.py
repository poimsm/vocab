from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import Session, select
from models import ContentQueue as ContentQueueModel, ContentQueueStatus, ContentType


class ContentQueue:
    """
    Administra el contenido que ya está preparado y listo
    para ser consumido por el usuario.

    Esta clase NO decide qué palabras deberían estudiarse.
    NO calcula prioridades de aprendizaje.
    NO genera contenido.

    Su responsabilidad es exclusivamente administrar
    ContentQueue.
    """

    def __init__(self, session: Session):
        self.session = session

    def enqueue(
        self,
        user_id: int,
        content_type: ContentType,
        content_id: int,
        priority: float = 0.0,
    ) -> ContentQueueModel:
        """
        Agrega un contenido a la cola.

        Si el mismo contenido ya está PENDING, no lo duplica.
        """

        existing = self.session.exec(
            select(ContentQueueModel)
            .where(
                ContentQueueModel.user_id == user_id,
                ContentQueueModel.type == content_type,
                ContentQueueModel.content_id == content_id,
                ContentQueueModel.status == ContentQueueStatus.PENDING,
            )
        ).first()

        if existing:
            return existing

        item = ContentQueueModel(
            user_id=user_id,
            type=content_type,
            content_id=content_id,
            priority=priority,
            status=ContentQueueStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)

        return item

    def enqueue_many(
        self,
        user_id: int,
        content_type: ContentType,
        content_ids: List[int],
        priority: float = 0.0,
    ) -> List[ContentQueueModel]:
        """
        Agrega múltiples contenidos.

        Útil cuando la AI genera varios examples
        en una sola operación.
        """

        result = []

        for content_id in content_ids:
            item = self.enqueue(
                user_id=user_id,
                content_type=content_type,
                content_id=content_id,
                priority=priority,
            )

            result.append(item)

        return result

    def next(
        self,
        user_id: int,
        content_type: Optional[ContentType] = None,
    ) -> Optional[ContentQueueModel]:
        """
        Obtiene y reserva el siguiente contenido PENDING.

        Primero utiliza prioridad y después antigüedad.

        Importante:
        esta operación no debería generar contenido.
        """

        statement = (
            select(ContentQueueModel)
            .where(
                ContentQueueModel.user_id == user_id,
                ContentQueueModel.status == ContentQueueStatus.PENDING,
            )
            .order_by(
                ContentQueueModel.priority.desc(),
                ContentQueueModel.created_at.asc(),
            )
        )

        if content_type is not None:
            statement = statement.where(
                ContentQueueModel.type == content_type
            )

        return self.session.exec(statement).first()


    def next_many(
        self,
        user_id: int,
        content_type: ContentType,
        amount: int,
    ) -> List[ContentQueueModel]:
        """
        Obtiene los próximos contenidos pendientes para el usuario,
        respetando el orden en que fueron planificados.
        """
        statement = (
            select(ContentQueueModel)
            .where(
                ContentQueueModel.user_id == user_id,
                ContentQueueModel.type == content_type,
                ContentQueueModel.status == ContentQueueStatus.PENDING,
            )
            .order_by(
                ContentQueueModel.priority.desc(),
                ContentQueueModel.created_at.asc(),
            )
            .limit(amount)
        )

        return self.session.exec(statement).all()

    def peek(
        self,
        user_id: int,
        content_type: Optional[ContentType] = None,
    ) -> Optional[ContentQueueModel]:
        """
        Obtiene el siguiente elemento sin modificar su estado.

        Útil para inspección o planificación.
        """

        return self.next(
            user_id=user_id,
            content_type=content_type,
        )

    def consume(
        self,
        queue_id: int,
    ) -> Optional[ContentQueueModel]:
        """
        Marca un elemento como CONSUMED.

        No actualiza WordStatistics.

        El LearningTracker se encarga de registrar
        las exposiciones de las palabras.
        """

        item = self.session.get(
            ContentQueueModel,
            queue_id,
        )

        if item is None:
            return None

        item.status = ContentQueueStatus.CONSUMED

        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)

        return item

    def count_pending(
        self,
        user_id: int,
        content_type: Optional[ContentType] = None,
    ) -> int:
        """
        Cuenta cuántos contenidos preparados existen actualmente.
        """

        statement = (
            select(ContentQueueModel)
            .where(
                ContentQueueModel.user_id == user_id,
                ContentQueueModel.status == ContentQueueStatus.PENDING,
            )
        )

        if content_type is not None:
            statement = statement.where(
                ContentQueueModel.type == content_type
            )

        return len(self.session.exec(statement).all())

    def is_pending(
        self,
        user_id: int,
        content_type: ContentType,
        content_id: int,
    ) -> bool:
        """
        Determina si un contenido ya está esperando en la cola.
        """

        item = self.session.exec(
            select(ContentQueueModel)
            .where(
                ContentQueueModel.user_id == user_id,
                ContentQueueModel.type == content_type,
                ContentQueueModel.content_id == content_id,
                ContentQueueModel.status == ContentQueueStatus.PENDING,
            )
        ).first()

        return item is not None