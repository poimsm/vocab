from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload
from sqlmodel import Session, func, or_, select

from logging_client import logger

from models import (
    BestOption,
    WordStatistics,
    ContentType,
    Word,
    LearningState,
)

import random


class BestOptionRepository:
    """
    Repository para la gestión de BestOptions.
    """

    def __init__(self, session: Session):
        self.session = session

    def get_available_content_for_path(self, user_id: int) -> List[int]:
        """
        Obtiene IDs de best_options pristine que no están en ContentQueue.

        Estos best_options pueden ser reutilizados en lugar de generar nuevos.
        """
        from models import ContentQueue, ContentQueueStatus

        # Obtener IDs de best_options ya encolados
        enqueued_ids = self.session.exec(
            select(ContentQueue.content_id)
            .where(
                ContentQueue.user_id == user_id,
                ContentQueue.type == ContentType.BEST_OPTIONS,
                ContentQueue.status == ContentQueueStatus.PENDING,
            )
        ).all()

        enqueued_ids = set(enqueued_ids)

        # Obtener best_options pristine que no estén encolados
        best_options = self.session.exec(
            select(BestOption.id)
            .where(
                BestOption.is_active == True,
                BestOption.id.notin_(enqueued_ids) if enqueued_ids else True,
            )
        ).all()

        return best_options

    def count_available_best_options_for_word(self, word_id: int) -> int:
        """
        Cuenta cuántos best_options disponibles hay para una palabra.

        Un best_option está disponible si:
        - Pertenece a la palabra
        - Está activo (is_active=True)
        - No ha sido encolado aún (enqueued=False)
        """
        count = self.session.exec(
            select(func.count(BestOption.id))
            .where(
                BestOption.word_id == word_id,
                BestOption.is_active == True,
                BestOption.enqueued == False,
                BestOption.is_consumed == False
            )
        ).first() or 0

        return count

    def get_available_content_for_word(self, word_id: int) -> Optional[int]:
        """
        Obtiene el próximo best_option disponible para una palabra específica.

        Un best_option está disponible si:
        - Pertenece a la palabra
        - No ha sido encolado aún (enqueued=False)
        - La palabra NO está en estado LEARNED

        Retorna el best_option con la secuencia más baja (el más antiguo).
        """
        # Verificar si la palabra está en estado LEARNED
        word_stats = self.session.exec(
            select(WordStatistics)
            .where(
                WordStatistics.word_id == word_id,
                WordStatistics.type == ContentType.BEST_OPTIONS
            )
        ).first()

        if word_stats and word_stats.learning_state == LearningState.LEARNED:
            logger.debug(
                f"[BestOptionRepository] Word {word_id} is LEARNED, skipping best_option"
            )
            return None

        best_option_id = self.session.exec(
            select(BestOption.id)
            .where(
                BestOption.word_id == word_id,
                BestOption.is_active == True,
                BestOption.enqueued == False,
                BestOption.is_consumed == False
            )
            .order_by(BestOption.sequence.asc())
        ).first()

        return best_option_id

    def get_word_id(self, best_option_id: int) -> Optional[int]:
        """
        Obtiene el ID de la palabra asociada a un best_option.
        """
        best_option = self.session.exec(
            select(BestOption).where(BestOption.id == best_option_id)
        ).first()

        return best_option.word_id if best_option else None

    def save(self, best_option: BestOption) -> BestOption:
        """
        Guarda un best_option en la base de datos.
        """
        self.session.add(best_option)
        self.session.commit()
        self.session.refresh(best_option)
        return best_option


def get_words(db: Session, best_option_id: int) -> List:
    """Obtiene la palabra asociada a un best option."""
    best_option = db.exec(
        select(BestOption).where(BestOption.id == best_option_id)
    ).first()
    return [best_option.word] if best_option and best_option.word else []