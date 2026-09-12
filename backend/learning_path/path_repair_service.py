"""
Auto-repair service for Learning Path anomalies.
Automatically fixes detected problems to prevent infinite loops and other issues.
"""

import json
from typing import Dict, Any
from datetime import datetime, timezone
from sqlmodel import Session, select
from logging_client import logger

from models import (
    LearningPath,
    LearningPathCursor,
    Word,
    WordStatistics,
    ContentType,
    LearningState,
    LearningPathAnomaly,
    PathAnomalyType,
    PathRepairLog,
)


class PathRepairService:
    """
    Auto-reparación para anomalías detectadas en el learning path.
    """

    def __init__(self, session: Session):
        self.session = session

    def repair_anomaly(self, anomaly: LearningPathAnomaly) -> bool:
        """
        Intenta reparar una anomalía detectada.
        Retorna True si la reparación fue exitosa.
        """
        try:
            success = False
            repair_desc = ""

            if anomaly.anomaly_type == PathAnomalyType.OVERSIZED_PATH:
                success, repair_desc = self._repair_oversized_path(
                    anomaly.user_id, anomaly.type
                )

            elif anomaly.anomaly_type == PathAnomalyType.INACTIVE_WORDS_IN_PATH:
                success, repair_desc = self._repair_inactive_words(
                    anomaly.user_id, anomaly.type
                )

            elif anomaly.anomaly_type == PathAnomalyType.LEARNED_WORDS_IN_PATH:
                success, repair_desc = self._repair_learned_words(
                    anomaly.user_id, anomaly.type
                )

            elif anomaly.anomaly_type == PathAnomalyType.INFINITE_GENERATION_LOOP:
                success, repair_desc = self._repair_infinite_generation_loop(
                    anomaly.user_id, anomaly.type
                )

            elif anomaly.anomaly_type == PathAnomalyType.EMPTY_QUEUE_WITH_NEW_WORDS:
                success, repair_desc = self._repair_empty_queue_with_new_words(
                    anomaly.user_id, anomaly.type
                )

            elif anomaly.anomaly_type == PathAnomalyType.CURSOR_MISALIGNMENT:
                success, repair_desc = self._repair_cursor_misalignment(
                    anomaly.user_id, anomaly.type
                )

            # Actualizar anomalía
            anomaly.auto_repair_attempted = True
            anomaly.auto_repair_successful = success
            anomaly.repair_description = repair_desc
            if success:
                anomaly.is_resolved = True
                anomaly.resolved_at = datetime.now(timezone.utc)

            self.session.add(anomaly)
            self.session.commit()

            logger.info(
                f"[PathRepairService] Repair attempted for {anomaly.anomaly_type}: "
                f"success={success}, desc={repair_desc}"
            )

            return success

        except Exception as e:
            logger.error(
                f"[PathRepairService] Error repairing {anomaly.anomaly_type}: {str(e)}"
            )
            anomaly.auto_repair_attempted = True
            anomaly.auto_repair_successful = False
            anomaly.repair_description = f"Error: {str(e)}"
            self.session.add(anomaly)
            self.session.commit()
            return False

    def _repair_oversized_path(
        self, user_id: int, content_type: ContentType
    ) -> tuple[bool, str]:
        """
        Repara path demasiado grande.
        Estrategia: Borrar todo el path y resetear cursor.
        """
        try:
            # Contar items antes
            before_count = self.session.exec(
                select(LearningPath).where(
                    LearningPath.user_id == user_id,
                    LearningPath.type == content_type,
                )
            ).all()

            # Borrar path
            items_to_delete = self.session.exec(
                select(LearningPath).where(
                    LearningPath.user_id == user_id,
                    LearningPath.type == content_type,
                )
            ).all()
            for item in items_to_delete:
                self.session.delete(item)

            # Resetear cursor
            cursor = self.session.exec(
                select(LearningPathCursor).where(
                    LearningPathCursor.user_id == user_id,
                    LearningPathCursor.type == content_type,
                )
            ).first()

            if cursor:
                cursor.current_segment = 0
                cursor.current_position = 0
                self.session.add(cursor)

            self.session.commit()

            self._log_repair(
                user_id,
                content_type,
                "delete_oversized_path",
                before_state=f'{{"path_items": {len(before_count)}}}',
                after_state='{"path_items": 0}',
                items_affected=len(before_count),
                success=True,
            )

            return True, f"Deleted {len(before_count)} corrupted path items and reset cursor"

        except Exception as e:
            return False, f"Failed to delete path: {str(e)}"

    def _repair_inactive_words(
        self, user_id: int, content_type: ContentType
    ) -> tuple[bool, str]:
        """
        Repara palabras inactivas en el path.
        Estrategia: Borrar path items de palabras inactivas.
        """
        try:
            # Encontrar items con palabras inactivas
            inactive_items = self.session.exec(
                select(LearningPath)
                .join(Word, LearningPath.word_id == Word.id)
                .where(
                    LearningPath.user_id == user_id,
                    LearningPath.type == content_type,
                    Word.is_active == False,
                )
            ).all()

            # Borrar
            for item in inactive_items:
                self.session.delete(item)

            self.session.commit()

            self._log_repair(
                user_id,
                content_type,
                "remove_inactive_words",
                before_state=f'{{"inactive_items": {len(inactive_items)}}}',
                after_state='{"inactive_items": 0}',
                items_affected=len(inactive_items),
                success=True,
            )

            return (
                True,
                f"Removed {len(inactive_items)} path items with inactive words",
            )

        except Exception as e:
            return False, f"Failed to remove inactive words: {str(e)}"

    def _repair_learned_words(
        self, user_id: int, content_type: ContentType
    ) -> tuple[bool, str]:
        """
        Repara palabras LEARNED en el path.
        Estrategia: Borrar path items de palabras LEARNED.
        """
        try:
            # Encontrar items con palabras LEARNED
            learned_items = self.session.exec(
                select(LearningPath)
                .join(Word, LearningPath.word_id == Word.id)
                .join(WordStatistics, Word.id == WordStatistics.word_id)
                .where(
                    LearningPath.user_id == user_id,
                    LearningPath.type == content_type,
                    WordStatistics.type == content_type,
                    WordStatistics.learning_state == LearningState.LEARNED,
                )
            ).all()

            # Borrar
            for item in learned_items:
                self.session.delete(item)

            self.session.commit()

            self._log_repair(
                user_id,
                content_type,
                "remove_learned_words",
                before_state=f'{{"learned_items": {len(learned_items)}}}',
                after_state='{"learned_items": 0}',
                items_affected=len(learned_items),
                success=True,
            )

            return True, f"Removed {len(learned_items)} path items with LEARNED words"

        except Exception as e:
            return False, f"Failed to remove learned words: {str(e)}"

    def _repair_infinite_generation_loop(
        self, user_id: int, content_type: ContentType
    ) -> tuple[bool, str]:
        """
        Repara loop infinito de generación.
        Estrategia: Limpiar path y resetear cursor para forzar rebuild.
        """
        try:
            # Contar items antes
            before_count = self.session.exec(
                select(LearningPath).where(
                    LearningPath.user_id == user_id,
                    LearningPath.type == content_type,
                )
            ).all()

            # Borrar path
            items_to_delete = self.session.exec(
                select(LearningPath).where(
                    LearningPath.user_id == user_id,
                    LearningPath.type == content_type,
                )
            ).all()
            for item in items_to_delete:
                self.session.delete(item)

            # Resetear cursor
            cursor = self.session.exec(
                select(LearningPathCursor).where(
                    LearningPathCursor.user_id == user_id,
                    LearningPathCursor.type == content_type,
                )
            ).first()

            if cursor:
                cursor.current_segment = 0
                cursor.current_position = 0
                self.session.add(cursor)

            self.session.commit()

            self._log_repair(
                user_id,
                content_type,
                "break_infinite_generation_loop",
                before_state=f'{{"path_items": {len(before_count)}}}',
                after_state='{"path_items": 0}',
                items_affected=len(before_count),
                success=True,
            )

            return (
                True,
                f"Cleared {len(before_count)} path items to break infinite generation loop",
            )

        except Exception as e:
            return False, f"Failed to break loop: {str(e)}"

    def _repair_empty_queue_with_new_words(
        self, user_id: int, content_type: ContentType
    ) -> tuple[bool, str]:
        """
        Repara queue vacía con palabras NEW.
        Estrategia: Forzar rebuild del path para que NEW palabras se añadan.
        """
        try:
            # Contar items antes
            before_count = self.session.exec(
                select(LearningPath).where(
                    LearningPath.user_id == user_id,
                    LearningPath.type == content_type,
                )
            ).all()

            # Borrar path existente (va a ser rebuildo)
            items_to_delete = self.session.exec(
                select(LearningPath).where(
                    LearningPath.user_id == user_id,
                    LearningPath.type == content_type,
                )
            ).all()
            for item in items_to_delete:
                self.session.delete(item)

            self.session.commit()

            self._log_repair(
                user_id,
                content_type,
                "rebuild_path_for_new_words",
                before_state=f'{{"path_items": {len(before_count)}}}',
                after_state='{"path_items": 0, "will_rebuild": true}',
                items_affected=len(before_count),
                success=True,
            )

            return True, "Cleared path to trigger rebuild for NEW words"

        except Exception as e:
            return False, f"Failed to clear path: {str(e)}"

    def _repair_cursor_misalignment(
        self, user_id: int, content_type: ContentType
    ) -> tuple[bool, str]:
        """
        Repara cursor fuera de rango.
        Estrategia: Resetear a valores seguros (0, 0).
        """
        try:
            cursor = self.session.exec(
                select(LearningPathCursor).where(
                    LearningPathCursor.user_id == user_id,
                    LearningPathCursor.type == content_type,
                )
            ).first()

            if not cursor:
                return False, "Cursor not found"

            before_state = (
                f'{{"segment": {cursor.current_segment}, "position": {cursor.current_position}}}'
            )

            cursor.current_segment = 0
            cursor.current_position = 0
            self.session.add(cursor)
            self.session.commit()

            self._log_repair(
                user_id,
                content_type,
                "reset_cursor",
                before_state=before_state,
                after_state='{"segment": 0, "position": 0}',
                items_affected=1,
                success=True,
            )

            return True, "Reset cursor to safe values (0, 0)"

        except Exception as e:
            return False, f"Failed to reset cursor: {str(e)}"

    def _log_repair(
        self,
        user_id: int,
        content_type: ContentType,
        repair_type: str,
        before_state: str,
        after_state: str,
        items_affected: int,
        success: bool,
    ) -> None:
        """Registra una reparación en la BD."""
        log = PathRepairLog(
            user_id=user_id,
            type=content_type,
            repair_type=repair_type,
            before_state=before_state,
            after_state=after_state,
            items_affected=items_affected,
            success=success,
            triggered_by="auto_repair",
        )
        self.session.add(log)
        self.session.commit()
        logger.info(
            f"[PathRepairService] Logged repair: {repair_type} for user {user_id}"
        )
