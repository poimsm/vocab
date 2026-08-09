from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import joinedload
from sqlmodel import Session, func, or_, select
from logging_client import logger
from config_manager import ConfigManager
from utils.paginator import paginate_query
from examples.helpers import approximate_text_form

import random
from typing import List
from sqlmodel import Session, select
from datetime import datetime, timezone

from models import (
    Example,
    ExampleWord,
    WordStatistics,
    ContentType,
    ExampleType,
)


def toggle_active(db: Session, example_id: int):
    example = db.exec(select(Example).filter(
        Example.id == example_id)).first()
    if not example:
        return None

    example.is_active = not example.is_active
    db.add(example)
    db.commit()
    db.refresh(example)
    return example


def toggle_favorite(db: Session, example_id: int):
    example = db.exec(select(Example).filter(
        Example.id == example_id)).first()
    if not example:
        return None

    example.is_favorite = not example.is_favorite
    db.add(example)
    db.commit()
    db.refresh(example)
    return example


def increment_statistics(db: Session, example_id: int, user_id: int) -> Optional[Example]:
    statement = (
        select(Example)
        .where(Example.id == example_id)
        .options(joinedload(Example.example_words).joinedload(ExampleWord.word))
    )
    example = db.exec(statement).first()
    if not example:
        return None

    now_utc = datetime.now(timezone.utc)

    # 1. Incrementar contador del ejemplo
    example.times_seen += 1
    db.add(example)

    # Get TARGET_CYCLE_SEEN from database configuration
    config = ConfigManager(db)
    target_cycle_seen = config.get_target_cycle_seen()

    # 2. Incrementar contadores en palabras y evaluar si están aprendidas
    seen_word_ids = set()
    affected_batch_ids = set()

    for ew in example.example_words:
        word = ew.word
        if word and word.id not in seen_word_ids:
            seen_word_ids.add(word.id)

            # Obtener o crear estadísticas para esta palabra solo para EXAMPLE (ejemplos)
            featured_type = ContentType.EXAMPLE
            stats = db.exec(
                select(WordStatistics).where(
                    WordStatistics.word_id == word.id,
                    WordStatistics.type == featured_type
                )
            ).first()

            if not stats:
                stats = WordStatistics(word_id=word.id, type=featured_type)
                db.add(stats)
                db.flush()

            stats.times_seen += 1
            stats.current_cycle_seen += 1
            stats.last_seen_at = now_utc
            db.add(stats)

            # ✅ EVALUACIÓN AUTOMÁTICA DE IS_LEARNED
            if stats.current_cycle_seen >= target_cycle_seen and not stats.is_learned:
                stats.is_learned = True
                logger.info(
                    f"[resolve_and_increment_example] Word {word.id} ({word.main}) marked as LEARNED for type {featured_type.value} (current_cycle_seen={stats.current_cycle_seen})")

            db.add(word)

            if word.batch_id:
                affected_batch_ids.add(word.batch_id)  

    db.commit()
    db.refresh(example)
    return example


def get_examples(db: Session, sort: str = "newest", word_id: int = None, page: int = 1, limit: int = 15):
    statement = select(Example).filter(Example.is_active == True)

    if word_id is not None:
        statement = statement.join(Example.example_words).filter(
            ExampleWord.word_id == word_id
        )

    if sort == "newest":
        statement = statement.order_by(Example.id.desc())
    elif sort == "oldest":
        statement = statement.order_by(Example.id.asc())
    elif sort == "alphabetical":
        statement = statement.order_by(Example.text.asc())
    elif sort == "favorites":
        statement = statement.order_by(
            Example.is_favorite.desc(), Example.id.desc()
        )

    statement = statement.options(joinedload(
        Example.example_words).joinedload(ExampleWord.word)
    )

    return paginate_query(db, statement, page, limit)


def create(db: Session, raw_examples: List[dict], example_type: ExampleType = ExampleType.EXPLORE) -> List[Example]:
    created = []
    for item in raw_examples:
        example = Example(
            text=item["text"],
            type=example_type
        )
        db.add(example)
        db.flush()

        # Crear la relación N:M en ExampleWord
        # Buscar "words" (retorno de IA) o "target_words" (alternativa)
        words_list = item.get("words", item.get("target_words", []))
        for word in words_list:
            word_id = word.get("word_id") if isinstance(word, dict) else (
                word.id if hasattr(word, "id") else word)
            if word_id:
                suggested_text_form = word.get(
                    "text_form", "") if isinstance(word, dict) else ""
                corrected_text_form = approximate_text_form(example.text, suggested_text_form)
                logger.info(f'[example] {example.text}')
                logger.info(f'[suggested_text_form] word_id={word_id}, {suggested_text_form}')
                logger.info(f'[corrected_text_form] word_id={word_id}, {corrected_text_form}')

                assoc = ExampleWord(
                    example_id=example.id,
                    word_id=word_id,
                    text_form=corrected_text_form
                )
                db.add(assoc)

        created.append(example)

    db.commit()
    return created




THRESHOLD_FOR_TRANSITION = 10

def available_for_queue(db: Session) -> List["Example"]:
    # Step 1: Get pristine items
    statement = select(Example).where(Example.is_pristine == True)
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

def get_words(db: Session, example_id: int) -> List:
    """Obtiene todas las palabras asociadas a un ejemplo."""
    from models import Word
    statement = (
        select(Word)
        .join(ExampleWord, ExampleWord.word_id == Word.id)
        .where(ExampleWord.example_id == example_id)
    )
    return db.exec(statement).all()


def segment_example_text(example_text: str, example_words: List[Any]) -> List[dict]:
    """
    Segmenta el texto del ejemplo en partes resaltadas y no resaltadas basado en text_form.

    Args:
        example_text: El texto completo del ejemplo
        example_words: Lista de diccionarios o ExampleWord con text_form e información de la palabra

    Returns:
        Lista de diccionarios con estructura {text, is_highlighted, target_word}
    """
    if not example_words:
        return [{"text": example_text, "is_highlighted": False}]

    # Crear lista de (start_pos, end_pos, word_data) para cada occurrence de text_form
    highlights = []

    for ew in example_words:
        # Manejar tanto diccionarios como objetos ORM
        text_form = ew.get('text_form') if isinstance(ew, dict) else (ew.text_form or "")
        if not text_form:
            continue

        # Buscar el text_form en el texto (case-insensitive)
        text_lower = example_text.lower()
        form_lower = text_form.lower()

        # Buscar todas las ocurrencias (aunque típicamente hay una)
        start = 0
        while True:
            pos = text_lower.find(form_lower, start)
            if pos == -1:
                break

            # Extraer datos de palabra de forma segura
            if isinstance(ew, dict):
                word_data = ew.get('word', {})
            else:
                word_data = {
                    "id": ew.word_id,
                    "main": ew.word.main if ew.word else "",
                    "type": ew.word.type if ew.word else "",
                    "meaning": ew.word.meaning if ew.word else "",
                    "level": ew.word.level if ew.word else None,
                    "is_boosted": ew.word.is_boosted if ew.word else False,
                    "batch_id": ew.word.batch_id if ew.word else None,
                }

            highlights.append({
                "start": pos,
                "end": pos + len(text_form),
                "text": example_text[pos:pos + len(text_form)],
                "word": word_data
            })

            start = pos + 1

    if not highlights:
        return [{"text": example_text, "is_highlighted": False}]

    # Ordenar por posición y eliminar overlaps
    highlights.sort(key=lambda x: x["start"])

    # Construir segmentos
    segments = []
    current_pos = 0

    for highlight in highlights:
        # Texto antes del highlight
        if current_pos < highlight["start"]:
            segments.append({
                "text": example_text[current_pos:highlight["start"]],
                "is_highlighted": False
            })

        # Texto del highlight
        segments.append({
            "text": highlight["text"],
            "is_highlighted": True,
            "target_word": highlight["word"]
        })

        current_pos = highlight["end"]

    # Texto al final
    if current_pos < len(example_text):
        segments.append({
            "text": example_text[current_pos:],
            "is_highlighted": False
        })

    return segments