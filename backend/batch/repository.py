from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload
from sqlmodel import Session, func, or_, select

from logging_client import logger

from batch_manager import BatchManager

import models
from models import (
    ContentType,
    Word,
)



# ==========================================
# BATCH MANAGER CONVENIENCE FUNCTIONS
# ==========================================

def create_batch_manager(db: Session) -> BatchManager:
    """Crea una instancia del BatchManager."""
    return BatchManager(db)


def save_words_to_batches(
    db: Session,
    user_id: int,
    words_data: List[dict],
    source: models.BatchSource = models.BatchSource.ORGANIC,
    batch_title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Guarda palabras en batches usando BatchManager.
    Interfaz de conveniencia para uso en rutas y tareas.
    """
    manager = BatchManager(db)
    return manager.save_words_to_batches(user_id, words_data, source, batch_title)


def get_words_by_batch_featured_type(
    db: Session,
    user_id: int,
    content_type: ContentType,
    limit: int = 50
) -> List[Word]:
    """Obtiene palabras por tipo de contenido."""
    manager = BatchManager(db)
    return manager.get_words_by_batch_featured_type(user_id, content_type, limit)


def get_dormant_batches(
    db: Session,
    user_id: int,
    days_threshold: int = 7
) -> List[Dict[str, Any]]:
    """Obtiene batches dormidos."""
    manager = BatchManager(db)
    return manager.get_dormant_batches(user_id, days_threshold)


def get_all_batch_featured(
    db: Session,
    user_id: int,
    content_type: Optional[ContentType] = None
) -> List[Dict[str, Any]]:
    """Obtiene todos los BatchFeatured de un usuario."""
    manager = BatchManager(db)
    return manager.get_all_batch_featured(user_id, content_type)


def update_featured_stats_for_batch(db: Session, batch_id: int) -> None:
    """Actualiza estadísticas de BatchFeatured para un batch."""
    manager = BatchManager(db)
    manager.update_featured_stats_for_batch(batch_id)