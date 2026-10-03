# src/core/boost/repository.py
from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import Session, select
from features.words.models import Word
from core.boost.models import BoostGenerationMonitor
from core.enums import ContentType


class BoostRepository:
    """Repository for boost domain operations on Word model."""

    def __init__(self, session: Session):
        self.session = session

    def activate(self, user_id: int, word_id: int) -> Word:
        """Activate boost for a word."""
        word = self.session.get(Word, word_id)
        if not word:
            raise ValueError(f"Word {word_id} not found")

        if word.user_id != user_id:
            raise PermissionError(f"Word {word_id} does not belong to user {user_id}")

        word.is_boosted = True
        word.boosted_at = datetime.now(timezone.utc)
        self.session.add(word)
        self.session.commit()
        return word

    def deactivate(self, user_id: int, word_id: int) -> Word:
        """Deactivate boost for a word."""
        word = self.session.get(Word, word_id)
        if not word:
            raise ValueError(f"Word {word_id} not found")

        if word.user_id != user_id:
            raise PermissionError(f"Word {word_id} does not belong to user {user_id}")

        word.is_boosted = False
        self.session.add(word)
        self.session.commit()
        return word

    def get_boost_by_word(self, user_id: int, word_id: int) -> Optional[Word]:
        """Get boost info for a specific word."""
        statement = select(Word).where(
            Word.id == word_id,
            Word.user_id == user_id,
        )
        return self.session.exec(statement).first()

    def get_active_boosts(self, user_id: int) -> List[Word]:
        """Get all active boosted words for a user."""
        statement = select(Word).where(
            Word.user_id == user_id,
            Word.is_boosted == True,
        )
        return self.session.exec(statement).all()

    def is_word_boosted(self, user_id: int, word_id: int) -> bool:
        """Check if a word is currently boosted."""
        word = self.get_boost_by_word(user_id, word_id)
        return word is not None and word.is_boosted

    def get_total_boosted(self, user_id: int) -> int:
        """Count total active boosted words for a user."""
        return len(self.get_active_boosts(user_id))

    # Generation Monitoring Methods
    def start_generation_monitor(
        self,
        user_id: int,
        word_id: int,
        content_type: ContentType
    ) -> BoostGenerationMonitor:
        """Registra que se comenzó a generar contenido para una palabra boosteada."""
        now = datetime.now(timezone.utc)

        # Buscar si ya existe un monitor para esta palabra y content_type
        statement = select(BoostGenerationMonitor).where(
            BoostGenerationMonitor.user_id == user_id,
            BoostGenerationMonitor.word_id == word_id,
            BoostGenerationMonitor.content_type == content_type,
        )
        existing = self.session.exec(statement).first()

        if existing:
            # Actualizar el existente
            existing.status = "generating"
            existing.started_at = now
            existing.updated_at = now
            existing.error_message = None
            self.session.add(existing)
        else:
            # Crear uno nuevo
            monitor = BoostGenerationMonitor(
                user_id=user_id,
                word_id=word_id,
                content_type=content_type,
                status="generating",
                started_at=now,
            )
            self.session.add(monitor)

        self.session.commit()
        return existing or monitor

    def complete_generation_monitor(
        self,
        user_id: int,
        word_id: int,
        content_type: ContentType
    ) -> Optional[BoostGenerationMonitor]:
        """Marca que la generación de contenido fue completada."""
        now = datetime.now(timezone.utc)

        statement = select(BoostGenerationMonitor).where(
            BoostGenerationMonitor.user_id == user_id,
            BoostGenerationMonitor.word_id == word_id,
            BoostGenerationMonitor.content_type == content_type,
        )
        monitor = self.session.exec(statement).first()

        if monitor:
            monitor.status = "completed"
            monitor.completed_at = now
            monitor.updated_at = now
            self.session.add(monitor)
            self.session.commit()

        return monitor

    def fail_generation_monitor(
        self,
        user_id: int,
        word_id: int,
        content_type: ContentType,
        error_message: str
    ) -> Optional[BoostGenerationMonitor]:
        """Marca que la generación de contenido falló."""
        now = datetime.now(timezone.utc)

        statement = select(BoostGenerationMonitor).where(
            BoostGenerationMonitor.user_id == user_id,
            BoostGenerationMonitor.word_id == word_id,
            BoostGenerationMonitor.content_type == content_type,
        )
        monitor = self.session.exec(statement).first()

        if monitor:
            monitor.status = "failed"
            monitor.error_message = error_message
            monitor.updated_at = now
            self.session.add(monitor)
            self.session.commit()

        return monitor

    def clear_generation_monitor(
        self,
        user_id: int,
        word_id: int,
        content_type: Optional[ContentType] = None
    ) -> int:
        """Limpia los registros de monitoreo para una palabra (todos o un content_type específico)."""
        statement = select(BoostGenerationMonitor).where(
            BoostGenerationMonitor.user_id == user_id,
            BoostGenerationMonitor.word_id == word_id,
        )

        if content_type:
            statement = statement.where(
                BoostGenerationMonitor.content_type == content_type
            )

        monitors = self.session.exec(statement).all()

        for monitor in monitors:
            self.session.delete(monitor)

        self.session.commit()
        return len(monitors)

    def is_word_generating(
        self,
        user_id: int,
        word_id: int,
        content_type: Optional[ContentType] = None
    ) -> bool:
        """Chequea si una palabra está actualmente en estado generando."""
        statement = select(BoostGenerationMonitor).where(
            BoostGenerationMonitor.user_id == user_id,
            BoostGenerationMonitor.word_id == word_id,
            BoostGenerationMonitor.status == "generating",
        )

        if content_type:
            statement = statement.where(
                BoostGenerationMonitor.content_type == content_type
            )

        return self.session.exec(statement).first() is not None
