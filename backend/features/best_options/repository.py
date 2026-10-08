from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload
from sqlmodel import Session, func, or_, select

from logging_client import logger

from features.best_options.models import BestOption
from features.words.models import WordStatistics, Word
from core.enums import ContentType
from core.learning_path.models import LearningState

import random


class BestOptionRepository:
    """
    Repository para la gestión de BestOptions.
    """

    def __init__(self, session: Session):
        self.session = session

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
                BestOption.enqueued == False
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
                BestOption.enqueued == False
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

    def is_best_option_learned(self, best_option_id: int, user_id: int) -> bool:
        """
        Verifica si una best_option ha sido aprendida por un usuario.

        Una best_option se considera aprendida si su palabra asociada está en estado LEARNED.
        """
        from features.words.models import WordStatistics

        # Obtener la palabra asociada al best_option
        best_option = self.session.exec(
            select(BestOption).where(BestOption.id == best_option_id)
        ).first()

        if not best_option:
            return False

        # Verificar si la palabra está en estado LEARNED
        word_stats = self.session.exec(
            select(WordStatistics)
            .where(
                WordStatistics.word_id == best_option.word_id,
                WordStatistics.type == ContentType.BEST_OPTIONS,
                WordStatistics.user_id == user_id
            )
        ).first()

        if word_stats and word_stats.learning_state == LearningState.LEARNED:
            return True

        return False


def get_words(db: Session, best_option_id: int) -> List:
    """Obtiene la palabra asociada a un best option."""
    best_option = db.exec(
        select(BestOption).where(BestOption.id == best_option_id)
    ).first()
    return [best_option.word] if best_option and best_option.word else []