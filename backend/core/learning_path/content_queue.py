from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import Session, select
from logging_client import logger
from core.learning_path.models import LearningPathQueue
from core.learning_path.enums import LearningPathQueueStatus
from core.enums import ContentType


class ContentQueue:
    """
    Administra el contenido que ya está preparado y listo
    para ser consumido por el usuario.

    Esta clase NO decide qué palabras deberían estudiarse.
    NO calcula prioridades de aprendizaje.
    NO genera contenido.

    Su responsabilidad es exclusivamente administrar
    LearningPathQueue items (enqueue, consume, count, etc).

    Usa ContentRepository para obtener información sobre
    el contenido de manera agnóstica.
    """

    def __init__(self, session: Session, content_repo=None):
        self.session = session
        self.content_repo = content_repo

    def enqueue(
        self,
        user_id: int,
        content_type: ContentType,
        content_id: int,
        priority: float = 0.0,
    ) -> LearningPathQueue:
        """
        Agrega un contenido a la cola.

        Si el mismo contenido ya está PENDING, no lo duplica.
        """

        existing = self.session.exec(
            select(LearningPathQueue)
            .where(
                LearningPathQueue.user_id == user_id,
                LearningPathQueue.type == content_type,
                LearningPathQueue.content_id == content_id,
                LearningPathQueue.status == LearningPathQueueStatus.PENDING,
            )
        ).first()

        if existing:
            return existing

        now = datetime.now(timezone.utc)
        item = LearningPathQueue(
            user_id=user_id,
            type=content_type,
            content_id=content_id,
            priority=priority,
            status=LearningPathQueueStatus.PENDING,
            created_at=now,
            updated_at=now,
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
    ) -> List[LearningPathQueue]:
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
    ) -> Optional[LearningPathQueue]:
        """
        Obtiene y reserva el siguiente contenido PENDING.

        Primero utiliza prioridad y después antigüedad.

        Importante:
        esta operación no debería generar contenido.
        """

        statement = (
            select(LearningPathQueue)
            .where(
                LearningPathQueue.user_id == user_id,
                LearningPathQueue.status == LearningPathQueueStatus.PENDING,
            )
            .order_by(
                LearningPathQueue.priority.desc(),
                LearningPathQueue.created_at.asc(),
            )
        )

        if content_type is not None:
            statement = statement.where(
                LearningPathQueue.type == content_type
            )

        return self.session.exec(statement).first()


    def next_many(
        self,
        user_id: int,
        content_type: ContentType,
        amount: int,
    ) -> List[LearningPathQueue]:
        """
        Obtiene los próximos contenidos pendientes para el usuario,
        usando PriorityEngine para recalcular prioridades en tiempo real.

        Filtra items donde TODAS las palabras están en estado LEARNED.
        """
        from features.words.models import WordStatistics, Word
        from core.learning_path.models import LearningState
        from core.learning_path.priority_engine import PriorityEngine

        statement = (
            select(LearningPathQueue)
            .where(
                LearningPathQueue.user_id == user_id,
                LearningPathQueue.type == content_type,
                LearningPathQueue.status == LearningPathQueueStatus.PENDING,
            )
            .limit(amount * 3)  # Obtener más para compensar filtrados
        )

        all_items = self.session.exec(statement).all()
        priority_engine = PriorityEngine()
        items_with_priority = []

        for item in all_items:
            # Obtener las palabras asociadas al contenido (agnóstico de tipo)
            word_ids = []
            if self.content_repo:
                word_ids = self.content_repo.get_target_word_ids(item.content_id, content_type)

            # Contar palabras en estado LEARNED
            learned_count = 0
            max_priority = 0.0

            for word_id in word_ids:
                stats = self.session.exec(
                    select(WordStatistics)
                    .where(
                        WordStatistics.word_id == word_id,
                        WordStatistics.type == content_type
                    )
                ).first()

                if stats and stats.learning_state == LearningState.LEARNED:
                    learned_count += 1

                # Calcular prioridad usando PriorityEngine
                if stats:
                    word = self.session.get(Word, word_id)
                    priority = priority_engine.calculate_priority(word, stats)
                    max_priority = max(max_priority, priority)

            # Incluir solo si NO todas las palabras son LEARNED
            if learned_count < len(word_ids):
                items_with_priority.append((item, max_priority))
            else:
                logger.debug(
                    f"[ContentQueue] Filtering out {content_type} item {item.content_id}: "
                    f"all {len(word_ids)} words are LEARNED"
                )

        # Ordenar por prioridad y retornar
        items_with_priority.sort(key=lambda x: x[1], reverse=True)
        result = [item for item, priority in items_with_priority[:amount]]

        return result

    def peek(
        self,
        user_id: int,
        content_type: Optional[ContentType] = None,
    ) -> Optional[LearningPathQueue]:
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
    ) -> Optional[LearningPathQueue]:
        """
        Marca un elemento como CONSUMED.

        Actualiza:
        - ContentQueue.status = CONSUMED
        - Example/BestOption.is_consumed = True (para nunca volver a encolar)

        El LearningTracker se encarga de registrar
        las exposiciones de las palabras.
        """
        item = self.session.get(
            LearningPathQueue,
            queue_id,
        )

        if item is None:
            return None

        now = datetime.now(timezone.utc)
        item.status = LearningPathQueueStatus.CONSUMED
        item.updated_at = now

        # Marcar el contenido como consumido para evitar que vuelva a aparecer
        if self.content_repo:
            self.content_repo.mark_as_consumed(item.content_id, item.type)
            logger.info(
                f"[ContentQueue] CONSUMED: queue_item_id={queue_id}, "
                f"content_id={item.content_id}, content_type={item.type}"
            )

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
        Cuenta cuántos contenidos VÁLIDOS (no LEARNED) existen actualmente.

        Usa el mismo filtro que next_many() para asegurar que count_pending
        solo cuenta items que pueden ser devueltos. Evita que items con
        palabras LEARNED se cuenten en el gap.
        """
        from features.words.models import WordStatistics
        from core.learning_path.models import LearningState

        statement = (
            select(LearningPathQueue)
            .where(
                LearningPathQueue.user_id == user_id,
                LearningPathQueue.status == LearningPathQueueStatus.PENDING,
            )
        )

        if content_type is not None:
            statement = statement.where(
                LearningPathQueue.type == content_type
            )

        all_items = self.session.exec(statement).all()
        valid_count = 0

        for item in all_items:
            # Obtener las palabras asociadas al contenido
            word_ids = []
            if self.content_repo:
                word_ids = self.content_repo.get_target_word_ids(item.content_id, item.type)

            # Contar palabras en estado LEARNED
            learned_count = 0
            for word_id in word_ids:
                stats = self.session.exec(
                    select(WordStatistics)
                    .where(
                        WordStatistics.word_id == word_id,
                        WordStatistics.type == item.type
                    )
                ).first()
                if stats and stats.learning_state == LearningState.LEARNED:
                    learned_count += 1

            # Contar solo si NO todas las palabras son LEARNED
            if learned_count < len(word_ids):
                valid_count += 1

        return valid_count

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
            select(LearningPathQueue)
            .where(
                LearningPathQueue.user_id == user_id,
                LearningPathQueue.type == content_type,
                LearningPathQueue.content_id == content_id,
                LearningPathQueue.status == LearningPathQueueStatus.PENDING,
            )
        ).first()

        return item is not None