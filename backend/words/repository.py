import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload
from sqlmodel import Session, func, or_, select

from logging_client import logger

from utils.paginator import paginate_query

import models
from models import (
    ContentType,
    ExampleType,
    Word,
    WordStatistics,
)


def available(db: Session, content_type: ContentType, user_id: int) -> List[Word]:
    """Obtiene palabras disponibles (no aprendidas) para un usuario específico."""
    statement = (
        select(Word)
        .outerjoin(WordStatistics, (WordStatistics.word_id == Word.id) & (WordStatistics.type == content_type))
        .where(
            Word.user_id == user_id,
            Word.is_active == True,
            (WordStatistics.is_learned == False) | (WordStatistics.id.is_(None))
        )
        .limit(100)
    )
    return db.exec(statement).all()


def learned():
    pass


def not_learned():
    pass


def is_learned(word_id):
    pass


def mark_learned(word_id):
    pass


def mark_unlearned(word_id):
    pass


def are_learned(db: Session, words: List[Word], content_type: ContentType = ContentType.EXAMPLE) -> bool:
    """Verifica si todas las palabras en una lista están marcadas como aprendidas para un tipo específico."""
    if not words:
        return True

    word_ids = [w.id for w in words]

    # Obtener todas las estadísticas para estas palabras y el tipo específico
    stats = db.exec(
        select(WordStatistics).where(
            WordStatistics.word_id.in_(word_ids),
            WordStatistics.type == content_type
        )
    ).all()

    # Si no hay estadísticas, no están aprendidas
    if not stats:
        return False

    # Verificar que todas las palabras tienen is_learned = True
    learned_word_ids = {s.word_id for s in stats if s.is_learned}
    return learned_word_ids == set(word_ids)


def get(word_id):
    pass


def get_many(ids):
    pass


def exists(word_id):
    pass


def exists_many(ids):
    pass

# increment_views(word_id)


def get_words(db: Session, user_id: int, sort: str = "newest", page: int = 1, limit: int = 15):
    statement = (
        select(
            models.Word,
            func.count(models.Example.id).label("total_examples")
        )
        .where(models.Word.is_active == True, models.Word.user_id == user_id)
        .outerjoin(models.ExampleWord, models.ExampleWord.word_id == models.Word.id)
        .outerjoin(
            models.Example,
            (models.Example.id == models.ExampleWord.example_id) &
            (models.Example.type == ExampleType.EXPLORE) &
            (models.Example.is_active == True)
        )
        .outerjoin(WordStatistics, WordStatistics.word_id == models.Word.id)
        .group_by(models.Word.id)
    )

    if sort == "newest":
        statement = statement.order_by(models.Word.id.desc())
    elif sort == "oldest":
        statement = statement.order_by(models.Word.id.asc())
    elif sort == "hardest":
        statement = statement.order_by(models.Word.level.desc())
    elif sort == "easiest":
        statement = statement.order_by(models.Word.level.asc())
    elif sort == "alphabetical":
        statement = statement.order_by(models.Word.main.asc())
    elif sort == "most_seen":
        statement = statement.order_by(
            WordStatistics.times_seen.desc().nullslast())
    elif sort == "least_seen":
        statement = statement.order_by(
            WordStatistics.times_seen.asc().nullsfirst())

    return paginate_query(db, statement, page, limit)


def get(db: Session, word_id: int):
    return db.exec(select(models.Word).filter(models.Word.id == word_id)).first()


def create(db: Session, word_data: dict, user_id: int):
    main_raw = word_data.get("main", "").strip()
    normalized = main_raw.lower()
    source_text = word_data.get("source_text", "").strip(
    ) if word_data.get("source_text") else None

    conditions = [models.Word.normalized == normalized]

    if main_raw:
        conditions.append(models.Word.main == main_raw)
    if source_text:
        conditions.append(models.Word.source_text == source_text)

    existing = db.exec(
        select(models.Word).where(
            models.Word.user_id == user_id,
            models.Word.is_active == True,
            or_(*conditions)
        )
    ).first()

    if existing:
        return None

    new_word = models.Word(
        **word_data,
        user_id=user_id,
        normalized=normalized
    )

    db.add(new_word)
    db.flush()

    # Crear estadísticas para la palabra por cada tipo
    for featured_type in models.ContentType:
        stats = WordStatistics(
            word_id=new_word.id,
            type=featured_type
        )
        db.add(stats)
    db.commit()
    db.refresh(new_word)
    return new_word


def increment_words_seen(db: Session, words: List[Word]):
    for w in words:
        # Incrementar contador para todos los tipos de estadísticas
        all_stats = db.exec(
            select(WordStatistics).where(WordStatistics.word_id == w.id)
        ).all()

        now = datetime.now(timezone.utc)
        for stats in all_stats:
            stats.times_seen += 1
            stats.last_seen_at = now
            db.add(stats)
    db.commit()


def toggle_active(db: Session, word_id: int):
    word = get(db, word_id)
    if not word:
        return None

    word.is_active = not word.is_active
    db.add(word)
    db.commit()
    db.refresh(word)
    return word


def toggle_learned(db: Session, word_id: int):
    word = get(db, word_id)
    if not word:
        return None

    # Toggle learned status in all WordStatistics for this word
    word_stats_list = db.exec(
        select(WordStatistics).where(WordStatistics.word_id == word_id)
    ).all()

    if word_stats_list:
        for stats in word_stats_list:
            stats.is_learned = not stats.is_learned
            db.add(stats)
    else:
        # If no statistics exist, create one with is_learned=True
        new_stats = WordStatistics(
            word_id=word_id, type=ContentType.EXAMPLE, is_learned=True)
        db.add(new_stats)

    db.commit()
    return word


def toggle_favorite(db: Session, word_id: int):
    word = get(db, word_id)
    if not word:
        return None

    word.is_favorite = not word.is_favorite
    db.add(word)
    db.commit()
    db.refresh(word)
    return word


def get_words_least_seen(db: Session, user_id: int, limit: int = 15):
    statement = (
        select(models.Word)
        .outerjoin(WordStatistics, WordStatistics.word_id == models.Word.id)
        .filter(models.Word.user_id == user_id, models.Word.is_active == True)
        .order_by(WordStatistics.times_seen.asc().nullsfirst())
        .limit(limit)
    )
    return db.exec(statement).all()


def get_words_least_seen_ordered(db: Session, user_id: int, limit: int = 10) -> List[Word]:
    statement = (
        select(Word)
        .outerjoin(WordStatistics, WordStatistics.word_id == Word.id)
        .where(Word.user_id == user_id, Word.is_active == True)
        .order_by(WordStatistics.times_seen.asc())
        .limit(limit * 3)
    )
    results = db.exec(statement).unique().all()
    if not results:
        return []
    return random.sample(results, min(len(results), limit))
