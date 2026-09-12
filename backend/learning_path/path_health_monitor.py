"""
Health monitoring for Learning Path.
Detects anomalies and logs them for potential auto-repair.
"""

from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select, func
from logging_client import logger

from models import (
    LearningPath,
    LearningPathCursor,
    Word,
    WordStatistics,
    ContentQueue,
    ContentQueueStatus,
    ContentType,
    LearningState,
    LearningPathAnomaly,
    PathAnomalyType,
)


class PathHealthMonitor:
    """
    Monitorea la salud del learning path.
    Detecta anomalías que podrían causar comportamiento indeseado.
    """

    MAX_PATH_SIZE = 20
    MIN_QUEUE_SIZE = 5
    GENERATION_TIMEOUT_MINUTES = 5

    def __init__(self, session: Session):
        self.session = session

    def check_path_health(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> List[LearningPathAnomaly]:
        """
        Chequea la salud del path del usuario.
        Retorna lista de anomalías detectadas.
        """
        anomalies = []

        # Check 1: Path oversized
        oversized = self._check_oversized_path(user_id, content_type)
        if oversized:
            anomalies.append(oversized)

        # Check 2: Inactive words in path
        inactive = self._check_inactive_words_in_path(user_id, content_type)
        if inactive:
            anomalies.append(inactive)

        # Check 3: LEARNED words in path
        learned = self._check_learned_words_in_path(user_id, content_type)
        if learned:
            anomalies.append(learned)

        # Check 4: Infinite generation loop
        infinite_gen = self._check_infinite_generation_loop(user_id, content_type)
        if infinite_gen:
            anomalies.append(infinite_gen)

        # Check 5: Empty queue with NEW words
        empty_queue = self._check_empty_queue_with_new_words(user_id, content_type)
        if empty_queue:
            anomalies.append(empty_queue)

        # Check 6: Cursor misalignment
        cursor_issue = self._check_cursor_misalignment(user_id, content_type)
        if cursor_issue:
            anomalies.append(cursor_issue)

        # Log summary if any anomalies found
        if anomalies:
            logger.warning(
                f"[PathHealthMonitor] Detected {len(anomalies)} anomalies for user {user_id} ({content_type})"
            )
            for anomaly in anomalies:
                logger.warning(f"  - {anomaly.anomaly_type}: {anomaly.description}")

        return anomalies

    def _check_oversized_path(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> LearningPathAnomaly | None:
        """Detecta si el path es demasiado grande."""
        path_size = self.session.exec(
            select(func.count(LearningPath.id)).where(
                LearningPath.user_id == user_id,
                LearningPath.type == content_type,
            )
        ).first() or 0

        if path_size > self.MAX_PATH_SIZE:
            return LearningPathAnomaly(
                user_id=user_id,
                type=content_type,
                anomaly_type=PathAnomalyType.OVERSIZED_PATH,
                description=f"Path size is {path_size}, exceeds max of {self.MAX_PATH_SIZE}",
                details=f'{{"path_size": {path_size}, "max_size": {self.MAX_PATH_SIZE}}}',
            )

        return None

    def _check_inactive_words_in_path(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> LearningPathAnomaly | None:
        """Detecta si hay palabras inactivas en el path."""
        inactive_count = self.session.exec(
            select(func.count(LearningPath.id))
            .join(Word, LearningPath.word_id == Word.id)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.type == content_type,
                Word.is_active == False,
            )
        ).first() or 0

        if inactive_count > 0:
            # Get list of inactive word IDs
            inactive_words = self.session.exec(
                select(LearningPath.word_id)
                .join(Word, LearningPath.word_id == Word.id)
                .where(
                    LearningPath.user_id == user_id,
                    LearningPath.type == content_type,
                    Word.is_active == False,
                )
                .distinct()
            ).all()

            return LearningPathAnomaly(
                user_id=user_id,
                type=content_type,
                anomaly_type=PathAnomalyType.INACTIVE_WORDS_IN_PATH,
                description=f"Found {inactive_count} path items with inactive words: {inactive_words}",
                details=f'{{"inactive_count": {inactive_count}, "inactive_word_ids": {inactive_words}}}',
            )

        return None

    def _check_learned_words_in_path(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> LearningPathAnomaly | None:
        """Detecta si hay palabras LEARNED en el path."""
        learned_count = self.session.exec(
            select(func.count(LearningPath.id))
            .join(Word, LearningPath.word_id == Word.id)
            .join(WordStatistics, Word.id == WordStatistics.word_id)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.type == content_type,
                WordStatistics.type == content_type,
                WordStatistics.learning_state == LearningState.LEARNED,
            )
        ).first() or 0

        if learned_count > 0:
            learned_words = self.session.exec(
                select(LearningPath.word_id)
                .join(Word, LearningPath.word_id == Word.id)
                .join(WordStatistics, Word.id == WordStatistics.word_id)
                .where(
                    LearningPath.user_id == user_id,
                    LearningPath.type == content_type,
                    WordStatistics.type == content_type,
                    WordStatistics.learning_state == LearningState.LEARNED,
                )
                .distinct()
            ).all()

            return LearningPathAnomaly(
                user_id=user_id,
                type=content_type,
                anomaly_type=PathAnomalyType.LEARNED_WORDS_IN_PATH,
                description=f"Found {learned_count} path items with LEARNED words: {learned_words}",
                details=f'{{"learned_count": {learned_count}, "learned_word_ids": {learned_words}}}',
            )

        return None

    def _check_infinite_generation_loop(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> LearningPathAnomaly | None:
        """
        Detecta si el usuario está en un loop infinito de "generating".
        Criterios:
        - ContentQueue vacía
        - Hay palabras NO LEARNED
        - No se han generado ejemplos recientemente
        """
        # Contar queue pendiente
        pending_count = self.session.exec(
            select(func.count(ContentQueue.id)).where(
                ContentQueue.user_id == user_id,
                ContentQueue.type == content_type,
                ContentQueue.status == ContentQueueStatus.PENDING,
            )
        ).first() or 0

        # Contar palabras no LEARNED activas
        non_learned_count = self.session.exec(
            select(func.count(WordStatistics.id))
            .join(Word, WordStatistics.word_id == Word.id)
            .where(
                Word.user_id == user_id,
                Word.is_active == True,
                WordStatistics.type == content_type,
                WordStatistics.learning_state != LearningState.LEARNED,
            )
        ).first() or 0

        # Contar ejemplos generados en últimos N minutos
        recent_cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=self.GENERATION_TIMEOUT_MINUTES
        )

        if pending_count == 0 and non_learned_count > 0:
            return LearningPathAnomaly(
                user_id=user_id,
                type=content_type,
                anomaly_type=PathAnomalyType.INFINITE_GENERATION_LOOP,
                description=f"Empty queue ({pending_count}) but {non_learned_count} non-learned words exist. May be infinite generation loop.",
                details=f'{{"pending_count": {pending_count}, "non_learned_count": {non_learned_count}}}',
            )

        return None

    def _check_empty_queue_with_new_words(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> LearningPathAnomaly | None:
        """Detecta queue vacía cuando hay palabras NEW."""
        pending_count = self.session.exec(
            select(func.count(ContentQueue.id)).where(
                ContentQueue.user_id == user_id,
                ContentQueue.type == content_type,
                ContentQueue.status == ContentQueueStatus.PENDING,
            )
        ).first() or 0

        new_words_count = self.session.exec(
            select(func.count(WordStatistics.id))
            .join(Word, WordStatistics.word_id == Word.id)
            .where(
                Word.user_id == user_id,
                Word.is_active == True,
                WordStatistics.type == content_type,
                WordStatistics.learning_state == LearningState.NEW,
            )
        ).first() or 0

        if pending_count == 0 and new_words_count > 0:
            return LearningPathAnomaly(
                user_id=user_id,
                type=content_type,
                anomaly_type=PathAnomalyType.EMPTY_QUEUE_WITH_NEW_WORDS,
                description=f"ContentQueue empty but {new_words_count} NEW words exist (should have pre-generated examples)",
                details=f'{{"pending_count": {pending_count}, "new_words_count": {new_words_count}}}',
            )

        return None

    def _check_cursor_misalignment(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> LearningPathAnomaly | None:
        """Detecta si el cursor está fuera de rango."""
        cursor = self.session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == user_id,
                LearningPathCursor.type == content_type,
            )
        ).first()

        if not cursor:
            return None

        # Verificar que el segmento no sea negativo
        if cursor.current_segment < 0 or cursor.current_position < 0:
            return LearningPathAnomaly(
                user_id=user_id,
                type=content_type,
                anomaly_type=PathAnomalyType.CURSOR_MISALIGNMENT,
                description=f"Cursor has negative values: segment={cursor.current_segment}, position={cursor.current_position}",
                details=f'{{"segment": {cursor.current_segment}, "position": {cursor.current_position}}}',
            )

        # Verificar que exista contenido en esa posición o después
        max_segment = self.session.exec(
            select(func.max(LearningPath.segment)).where(
                LearningPath.user_id == user_id,
                LearningPath.type == content_type,
            )
        ).first() or 0

        if cursor.current_segment > max_segment + 1:
            return LearningPathAnomaly(
                user_id=user_id,
                type=content_type,
                anomaly_type=PathAnomalyType.CURSOR_MISALIGNMENT,
                description=f"Cursor segment {cursor.current_segment} exceeds max segment {max_segment}",
                details=f'{{"cursor_segment": {cursor.current_segment}, "max_segment": {max_segment}}}',
            )

        return None

    def log_anomaly(self, anomaly: LearningPathAnomaly) -> None:
        """Registra una anomalía en la BD."""
        self.session.add(anomaly)
        self.session.commit()
        logger.info(
            f"[PathHealthMonitor] Logged anomaly: {anomaly.anomaly_type} for user {anomaly.user_id}"
        )
