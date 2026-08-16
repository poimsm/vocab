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