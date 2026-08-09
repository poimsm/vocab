from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload
from sqlmodel import Session, func, or_, select

from logging_client import logger

from config_manager import ConfigManager

from models import (
    BestOption,
    WordStatistics,
    ContentType,
)

import random


def increment_statistics(db: Session, content_id: int, user_id: int) -> Optional[BestOption]:
    best_option = db.exec(
        select(BestOption).where(BestOption.id == content_id)
    ).first()

    if not best_option:
        return None

    word = best_option.word

    if not word:
        return None

    now_utc = datetime.now(timezone.utc)

    config = ConfigManager(db)
    target_cycle_seen = config.get_target_cycle_seen()

    stats = db.exec(
        select(WordStatistics).where(
            WordStatistics.word_id == word.id,
            WordStatistics.type == ContentType.BEST_OPTIONS
        )
    ).first()

    if not stats:
        stats = WordStatistics(word_id=word.id, type=ContentType.BEST_OPTIONS)
        db.add(stats)
        db.flush()

    stats.times_seen += 1
    stats.current_cycle_seen += 1
    stats.last_seen_at = now_utc
    db.add(stats)

    if stats.current_cycle_seen >= target_cycle_seen and not stats.is_learned:
        stats.is_learned = True
        logger.info(f"[increment_statistics] Word {word.id} ({word.main}) marked as LEARNED (current_cycle_seen={stats.current_cycle_seen})")

    db.add(word)

    db.commit()
    return best_option



THRESHOLD_FOR_TRANSITION = 10

def available_for_queue(db: Session) -> List["BestOption"]:
    # Step 1: Get pristine items
    statement = select(BestOption).where(BestOption.is_pristine == True)
    pristine_items = db.exec(statement).all()

    if not pristine_items:
        return []

    # Step 2: Shuffle items
    random.shuffle(pristine_items)

    # Step 3: Select up to threshold
    selected_items = pristine_items[:THRESHOLD_FOR_TRANSITION]

    # Step 4: Mark them as not pristine
    for item in selected_items:
        item.is_pristine = False
        db.add(item)

    db.commit()

    # Step 5: Return updated items
    return selected_items


def get_words(db: Session, best_option_id: int) -> List:
    """Obtiene la palabra asociada a un best option."""
    best_option = db.exec(
        select(BestOption).where(BestOption.id == best_option_id)
    ).first()
    return [best_option.word] if best_option and best_option.word else []