import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload
from sqlmodel import Session, func, or_, select

from logging_client import logger

import crud
from batch_manager import BatchManager
from config_manager import ConfigManager

import ai
import models
from models import (
    Batch,
    BatchFeatured,
    FeaturedType,
    BatchSource,
    BatchStatus,
    BatchFeaturedStatus,
    BestOption,
    BestOptionQueue,
    Example,
    ExampleQueue,
    ExampleType,
    ExampleWord,
    ExploreConfiguration,
    GlobalConfiguration,
    QueueStatus,
    Word,
    WordStatistics,
    QueueRefillStatus,
    QueueType,
)

# ==========================================
# QUEUE REFILL STATUS MANAGEMENT
# ==========================================

def is_queue_refilling(db: Session, user_id: int, queue_type: QueueType) -> bool:
    """
    Verifica si una cola está siendo reflenada en este momento.
    Retorna True si está refilling, False si no.
    """
    status = db.exec(
        select(QueueRefillStatus).where(
            QueueRefillStatus.user_id == user_id,
            QueueRefillStatus.queue_type == queue_type
        )
    ).first()

    if not status:
        return False

    return status.is_refilling


def start_queue_refill(db: Session, user_id: int, queue_type: QueueType) -> QueueRefillStatus:
    """
    Marca una cola como refilling (inicio de tarea de refill).
    Crea un registro si no existe, o actualiza el existente.
    """
    status = db.exec(
        select(QueueRefillStatus).where(
            QueueRefillStatus.user_id == user_id,
            QueueRefillStatus.queue_type == queue_type
        )
    ).first()

    now = datetime.now(timezone.utc)

    if status:
        status.is_refilling = True
        status.started_at = now
        status.updated_at = now
    else:
        status = QueueRefillStatus(
            user_id=user_id,
            queue_type=queue_type,
            is_refilling=True,
            started_at=now,
            updated_at=now
        )
        db.add(status)

    db.add(status)
    db.commit()
    db.refresh(status)

    logger.info(f"[start_queue_refill] User {user_id}, queue_type {queue_type.value}: refill started")
    return status


def end_queue_refill(db: Session, user_id: int, queue_type: QueueType) -> Optional[QueueRefillStatus]:
    """
    Marca una cola como terminada (fin de tarea de refill).
    """
    status = db.exec(
        select(QueueRefillStatus).where(
            QueueRefillStatus.user_id == user_id,
            QueueRefillStatus.queue_type == queue_type
        )
    ).first()

    if not status:
        logger.warning(f"[end_queue_refill] No refill status found for user {user_id}, queue_type {queue_type.value}")
        return None

    status.is_refilling = False
    status.updated_at = datetime.now(timezone.utc)
    db.add(status)
    db.commit()
    db.refresh(status)

    logger.info(f"[end_queue_refill] User {user_id}, queue_type {queue_type.value}: refill completed")
    return status


# ==========================================
# PAGINACIÓN
# ==========================================

def paginate_query(db: Session, statement, page: int, limit: int) -> dict:
    """Toma un statement de SQLModel, aplica paginación y devuelve
    la estructura estándar con metadatos.
    """
    if page < 1:
        page = 1
    if limit < 1:
        limit = 15

    count_statement = select(func.count()).select_from(statement.subquery())
    total_items = db.exec(count_statement).one()

    offset = (page - 1) * limit
    paginated_statement = statement.offset(offset).limit(limit)
    items = db.exec(paginated_statement).unique().all()

    total_pages = (total_items + limit - 1) // limit if total_items > 0 else 0

    return {
        "items": items,
        "meta": {
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }



# ==========================================
# PALABRAS (WORDS)
# ==========================================

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
        statement = statement.order_by(WordStatistics.times_seen.desc().nullslast())
    elif sort == "least_seen":
        statement = statement.order_by(WordStatistics.times_seen.asc().nullsfirst())

    return paginate_query(db, statement, page, limit)


def get_word_by_id(db: Session, word_id: int):
    return db.exec(select(models.Word).filter(models.Word.id == word_id)).first()


def create_word(db: Session, word_data: dict, user_id: int):
    main_raw = word_data.get("main", "").strip()
    normalized = main_raw.lower()
    source_text = word_data.get("source_text", "").strip() if word_data.get("source_text") else None

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
    for featured_type in models.FeaturedType:
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


def toggle_word_active(db: Session, word_id: int):
    word = get_word_by_id(db, word_id)
    if not word:
        return None

    word.is_active = not word.is_active
    db.add(word)
    db.commit()
    db.refresh(word)
    return word


def toggle_word_learned(db: Session, word_id: int):
    word = get_word_by_id(db, word_id)
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
        new_stats = WordStatistics(word_id=word_id, type=FeaturedType.EXAMPLE, is_learned=True)
        db.add(new_stats)

    db.commit()
    return word


def toggle_word_favorite(db: Session, word_id: int):
    word = get_word_by_id(db, word_id)
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


# ==========================================
# EJEMPLOS (EXAMPLES)
# ==========================================

def _segment_example_text(example_text: str, example_words: List[Any]) -> List[dict]:
    """
    Segmenta el texto del ejemplo en partes resaltadas y no resaltadas basado en text_form.

    Args:
        example_text: El texto completo del ejemplo
        example_words: Lista de ExampleWord con text_form e información de la palabra

    Returns:
        Lista de diccionarios con estructura {text, is_highlighted, target_word}
    """
    if not example_words:
        return [{"text": example_text, "is_highlighted": False}]

    # Crear lista de (start_pos, end_pos, word_data) para cada occurrence de text_form
    highlights = []

    for ew in example_words:
        text_form = ew.text_form or ""
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


# Caché global para diccionario de verbos irregulares
_IRREGULAR_VERBS_CACHE = None

def _load_irregular_verbs() -> dict:
    """Carga el diccionario de verbos irregulares desde el archivo."""
    global _IRREGULAR_VERBS_CACHE

    if _IRREGULAR_VERBS_CACHE is not None:
        return _IRREGULAR_VERBS_CACHE

    import os
    irregular_verbs_path = os.path.join(os.path.dirname(__file__), 'irregular_verbs.txt')

    irregular_verbs = {}
    try:
        with open(irregular_verbs_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                forms = [form.strip().lower() for form in line.split(';')]
                if forms:
                    # La primera forma es la base
                    base_form = forms[0]
                    # Todas las formas se mapean a todas las otras
                    for form in forms:
                        if form not in irregular_verbs:
                            irregular_verbs[form] = set(forms)
    except Exception:
        pass

    _IRREGULAR_VERBS_CACHE = irregular_verbs
    return irregular_verbs


def _approximate_text_form(example_text: str, suggested_text_form: str) -> str:
    """
    Aproxima la forma correcta del text_form basada en cómo aparece en el texto del ejemplo.
    Usa LemmInflect y diccionario de verbos irregulares para generar todas las inflexiones.

    Args:
        example_text: El texto completo del ejemplo
        suggested_text_form: La forma sugerida por IA (puede ser incorrecta)

    Returns:
        La forma más aproximada encontrada en el texto, o la sugerida si no se puede mejorar
    """
    if not suggested_text_form or not suggested_text_form.strip():
        return ""

    import re

    text_lower = example_text.lower()
    suggested_lower = suggested_text_form.lower()

    # 1. Buscar match exacto con límites de palabra (case-insensitive)
    exact_pattern = r'\b' + re.escape(suggested_lower) + r'\b'
    match = re.search(exact_pattern, text_lower)
    if match:
        return example_text[match.start():match.end()]

    # 2. Si no hay match exacto, intentar aproximar
    words = suggested_lower.split()

    # Filtrar artículos comunes (a, an, the) que pueden no estar en el texto
    # pero dejar las otras palabras
    articles = {'a', 'an', 'the'}
    words_without_articles = [w for w in words if w not in articles]

    # Si después de filtrar artículos quedan palabras, usar esas
    # Si no, usar las palabras originales
    if words_without_articles:
        words = words_without_articles

    if len(words) == 1:
        # Palabra única: generar todas las inflexiones posibles
        word = words[0]
        possible_forms = {word}  # Incluir la forma original

        # Obtener formas del diccionario de verbos irregulares
        irregular_verbs = _load_irregular_verbs()
        if word in irregular_verbs:
            possible_forms.update(irregular_verbs[word])

        try:
            # Obtener todas las inflexiones con LemmInflect
            from lemminflect.lemminflect import getInflections
            inflections = getInflections(word)
            if inflections:
                for form_list in inflections.values():
                    possible_forms.update(form_list)
        except Exception:
            pass

        # Buscar las inflexiones en el texto
        # Preferir exacto primero
        for form in possible_forms:
            if form and form.lower() == word:
                pattern = r'\b' + re.escape(form) + r'\b'
                match = re.search(pattern, text_lower)
                if match:
                    return example_text[match.start():match.end()]

        # Si no hay exacto, buscar todas las inflexiones y retornar la más larga encontrada
        # Esto asegura que "dreams" se retorne antes que "dream", y "dreaming" antes que "dream"
        found_matches = []
        sorted_forms = sorted(possible_forms, key=len, reverse=True)
        for form in sorted_forms:
            if form:
                pattern = r'\b' + re.escape(form) + r'\b'
                match = re.search(pattern, text_lower)
                if match:
                    found_matches.append((len(form), match.start(), match.end(), example_text[match.start():match.end()]))

        if found_matches:
            # Retornar el match más largo encontrado
            found_matches.sort(reverse=True)
            return found_matches[0][3]

        # Fallback: patrón regex si nada encontrado
        pattern = r'\b' + re.escape(word) + r'[a-z]*\b'
        match = re.search(pattern, text_lower)
        if match:
            return example_text[match.start():match.end()]
    else:
        # Frase múltiple: intentar encontrar los componentes en orden
        found_positions = []
        irregular_verbs = _load_irregular_verbs()

        for word in words:
            possible_forms = {word}

            # Obtener formas del diccionario de verbos irregulares
            if word in irregular_verbs:
                possible_forms.update(irregular_verbs[word])

            try:
                from lemminflect.lemminflect import getInflections
                inflections = getInflections(word)
                if inflections:
                    for form_list in inflections.values():
                        possible_forms.update(form_list)
            except Exception:
                pass

            # Buscar todas las formas y retornar la más larga encontrada
            sorted_forms = sorted(possible_forms, key=len, reverse=True)
            best_match = None
            best_length = 0
            for form in sorted_forms:
                if form:
                    pattern = r'\b' + re.escape(form) + r'\b'
                    match = re.search(pattern, text_lower)
                    if match and len(form) > best_length:
                        best_match = (match.start(), match.end(), example_text[match.start():match.end()])
                        best_length = len(form)

            if best_match:
                found_positions.append(best_match)

        # Si encontramos al menos una palabra
        if found_positions:
            # Si encontramos todas o la mayoría, reconstruir la frase
            if len(found_positions) >= max(1, len(words) - 1):
                # Ordenar por posición en el texto
                found_positions.sort(key=lambda x: x[0])

                # Si los matches están consecutivos (sin grandes gaps), recuperar todo
                first_start = found_positions[0][0]
                last_end = found_positions[-1][1]

                # Verificar que no hay demasiado espacio entre ellos
                gap = last_end - first_start
                expected_length = sum(len(form) for _, _, form in found_positions) + (len(found_positions) - 1) * 2

                if gap <= expected_length * 1.5:  # Permitir espacios y palabras pequeñas entre ellas
                    reconstructed = example_text[first_start:last_end].strip()
                    return reconstructed

            # Si solo encontramos una palabra, devolver esa
            if len(found_positions) == 1:
                return found_positions[0][2]

    # 3. Si no se puede aproximar, devolver la sugerencia original
    return suggested_text_form


def create_examples(db: Session, raw_examples: List[dict], example_type: ExampleType = ExampleType.EXPLORE) -> List[Example]:
    created = []
    for item in raw_examples:
        example = Example(
            text=item["text"],
            type=example_type
        )
        db.add(example)
        db.flush()  # 🚨 Importante: genera el ID del Example antes de asociar relaciones

        # Crear la relación N:M en ExampleWord
        # Buscar "words" (retorno de IA) o "target_words" (alternativa)
        words_list = item.get("words", item.get("target_words", []))
        for word in words_list:
            word_id = word.get("word_id") if isinstance(word, dict) else (word.id if hasattr(word, "id") else word)
            if word_id:
                suggested_text_form = word.get("text_form", "") if isinstance(word, dict) else ""
                # Aproximar la forma correcta del text_form basada en cómo aparece en el texto
                corrected_text_form = _approximate_text_form(example.text, suggested_text_form)
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


def get_examples(db: Session, sort: str = "newest", word_id: int = None, page: int = 1, limit: int = 15):
    statement = select(models.Example).filter(models.Example.is_active == True)

    if word_id is not None:
        statement = statement.join(models.Example.example_words).filter(
            models.ExampleWord.word_id == word_id
        )

    if sort == "newest":
        statement = statement.order_by(models.Example.id.desc())
    elif sort == "oldest":
        statement = statement.order_by(models.Example.id.asc())
    elif sort == "alphabetical":
        statement = statement.order_by(models.Example.text.asc())
    elif sort == "favorites":
        statement = statement.order_by(
            models.Example.is_favorite.desc(), models.Example.id.desc()
        )

    statement = statement.options(joinedload(
        models.Example.example_words).joinedload(models.ExampleWord.word)
    )

    return paginate_query(db, statement, page, limit)


def get_random_examples_by_words(db: Session, word_ids: List[int], limit: int = 5):
    if not word_ids:
        return []

    statement = (
        select(models.Example)
        .join(models.Example.example_words)
        .filter(models.Example.is_active == True, models.ExampleWord.word_id.in_(word_ids))
        .options(joinedload(models.Example.example_words).joinedload(models.ExampleWord.word))
        .order_by(func.random())
        .limit(limit)
    )
    return db.exec(statement).all()


def toggle_example_active(db: Session, example_id: int):
    example = db.exec(select(models.Example).filter(
        models.Example.id == example_id)).first()
    if not example:
        return None

    example.is_active = not example.is_active
    db.add(example)
    db.commit()
    db.refresh(example)
    return example


def toggle_example_favorite(db: Session, example_id: int):
    example = db.exec(select(models.Example).filter(
        models.Example.id == example_id)).first()
    if not example:
        return None

    example.is_favorite = not example.is_favorite
    db.add(example)
    db.commit()
    db.refresh(example)
    return example


def get_examples_balanced_by_least_seen(db: Session, limit: int = 5) -> List[Example]:
    statement = (
        select(Example)
        .where(Example.is_active == True)
        .order_by(Example.times_seen.asc(), Example.created_at.desc())
        .limit(limit)
    )
    return db.exec(statement).all()


def increment_examples_seen(db: Session, examples: List[Example]):
    for example in examples:
        example.times_seen += 1
        db.add(example)
    db.commit()


# ==========================================
# BATCHES (LOTES) Y PRIORIZACIÓN
# ==========================================

def get_or_create_propitious_batch(
    db: Session,
    user_id: int,
    source: BatchSource = BatchSource.ORGANIC,
    title: Optional[str] = None
) -> Batch:
    """
    Wrapper para BatchManager.get_or_create_propitious_batch().
    Mantenido para compatibilidad con código existente.
    """
    manager = BatchManager(db)
    return manager.get_or_create_propitious_batch(user_id, source, title)


# ==========================================
# COLA DE EXPLORACIÓN (EXAMPLE QUEUE MULTI-USER)
# ==========================================

def get_explore_configuration(db: Session, user_id: int) -> dict:
    total_examples = db.exec(
        select(func.count())
        .select_from(Example)
        .join(Example.example_words)
        .join(ExampleWord.word)
        .where(
            Word.user_id == user_id,
            Example.is_active == True, 
            Example.type == ExampleType.EXPLORE
        )
    ).one() or 0

    config = db.exec(
        select(ExploreConfiguration)
        .where(ExploreConfiguration.max_examples >= total_examples)
        .order_by(ExploreConfiguration.max_examples.asc())
    ).first()

    if not config:
        return {"ai_mixed_generation_amount": 6, "ai_simple_generation_amount": 6, "recycled_words_amount": 2}

    return {
        "ai_mixed_generation_amount": config.ai_mixed_generation_amount,
        "ai_simple_generation_amount": config.ai_simple_generation_amount,
        "recycled_words_amount": config.recycled_words_amount
    }


def refill_example_queue(db: Session, user_id: int):
    config = get_explore_configuration(db, user_id)
    ai_mixed_amount = config.get("ai_mixed_generation_amount", 0)
    ai_simple_amount = config.get("ai_simple_generation_amount", 0)
    recycle_amount = config.get("recycled_words_amount", 0)

    # 🚨 CLAVE 1: Excluir TODO el historial de ExampleQueue del usuario
    # (PENDING, SENT y RESOLVED). Esto evita re-encolar lo mismo o borrar historial.
    queue_statement = select(ExampleQueue.example_id).where(
        ExampleQueue.user_id == user_id
    )
    excluded_ids = list(db.exec(queue_statement).all())
    logger.info(f"[refill_example_queue] User {user_id}: excluded_ids count = {len(excluded_ids)}, ids = {excluded_ids[:10]}")

    # 🚨 CLAVE 2: Obtener solo palabras prioritarias NO APRENDIDAS usando BatchManager
    total_words_needed = (recycle_amount * 2) + ai_simple_amount + ai_mixed_amount
    manager = BatchManager(db)
    priority_words = manager.get_words_with_transition(
        user_id=user_id,
        featured_type=models.FeaturedType.EXAMPLE,
        limit=max(total_words_needed, 8)
    )

    if not priority_words:
        return

    # 1. PRIMERA PRIORIDAD: RECOLECTAR TODOS LOS EJEMPLOS PRISTINOS DISPONIBLES
    # Sin límite de cantidad, simplemente obtén TODOS los que estén disponibles
    all_pristine_examples = []

    statement = (
        select(Example)
        .join(Example.example_words)
        .join(ExampleWord.word)
        .outerjoin(WordStatistics, WordStatistics.word_id == ExampleWord.word_id)
        .where(
            Example.is_active == True,
            Example.type == ExampleType.EXPLORE,
            Example.is_pristine == True,
            ExampleWord.word_id.in_([w.id for w in priority_words]),
            or_(WordStatistics.is_learned == False, WordStatistics.id == None),
            Word.is_active == True
        )
    )

    if excluded_ids:
        statement = statement.where(Example.id.not_in(excluded_ids))

    statement = statement.order_by(
        Example.times_seen.asc(), Example.created_at.desc()
    )

    all_pristine_examples = db.exec(statement).all()
    logger.info(f"[refill_example_queue] User {user_id}: Found {len(all_pristine_examples)} pristine examples")

    # Actualizar excluded_ids con los ejemplos encontrados
    for example in all_pristine_examples:
        excluded_ids.append(example.id)
        example.is_pristine = False  # Marcar como usado
        db.add(example)

    # 2. RECICLAR EJEMPLOS EXISTENTES (Que el usuario NUNCA haya visto)
    recycled_examples = all_pristine_examples[:recycle_amount] if recycle_amount > 0 else []

    # 3. GENERAR NUEVOS EJEMPLOS CON IA (SOLO si no hay suficientes pristinos)
    new_examples = []
    total_needed = recycle_amount + ai_simple_amount + ai_mixed_amount
    pristine_count = len(all_pristine_examples)

    # Si ya tenemos suficientes ejemplos pristinos, no generar IA
    if pristine_count >= total_needed:
        logger.info(f"[refill_example_queue] User {user_id}: Enough pristine examples ({pristine_count}). Skipping AI generation")
        new_examples = all_pristine_examples[recycle_amount:]  # El resto van a new_examples
    else:
        # Faltan ejemplos, generar con IA
        total_ai_required = ai_simple_amount + ai_mixed_amount

        if total_ai_required > 0:
            words_for_ai = priority_words[:total_ai_required * 2]

            # Simple - Generar si faltan
            if ai_simple_amount > 0:
                needed_simple = ai_simple_amount
                if pristine_count > recycle_amount:
                    # Algunos pristinos se pueden usar para simple
                    needed_simple = max(0, ai_simple_amount - (pristine_count - recycle_amount))

                if needed_simple > 0:
                    simple_words = words_for_ai[:ai_simple_amount]
                    raw_simple = ai.generate_examples_from_words(simple_words)
                    if raw_simple:
                        generated_simple = create_examples(db, raw_simple[:needed_simple])
                        new_examples.extend(generated_simple)

            # Mixed - Generar si faltan
            if ai_mixed_amount > 0:
                # Calcular cuántos mixed aún se necesitan
                already_collected = len(recycled_examples) + len(new_examples)
                needed_mixed = max(0, total_ai_required - already_collected)

                if needed_mixed > 0:
                    mixed_words = words_for_ai[ai_simple_amount:ai_simple_amount + ai_mixed_amount]
                    raw_mixed = ai.generate_mixed_examples_from_words(mixed_words)
                    if raw_mixed:
                        generated_mixed = create_examples(db, raw_mixed[:needed_mixed])
                        new_examples.extend(generated_mixed)

        # Agregar pristinos restantes a new_examples
        new_examples = all_pristine_examples[recycle_amount:] + new_examples

    # 3. ENCOLAR EN ESTADO PENDING SIN BORRAR REGISTROS PREVIOS
    all_candidates = recycled_examples + new_examples
    newly_queued = 0
    for example in all_candidates:
        already_in_queue = db.exec(
            select(ExampleQueue).where(
                ExampleQueue.user_id == user_id,
                ExampleQueue.example_id == example.id
            )
        ).first()

        if not already_in_queue:
            # Marcar el ejemplo como usado (no pristine)
            example.is_pristine = False
            db.add(example)

            queue_item = ExampleQueue(
                user_id=user_id,
                example_id=example.id,
                status=QueueStatus.PENDING
            )
            db.add(queue_item)
            newly_queued += 1

    db.commit()
    logger.info(f"[refill_example_queue] User {user_id}: newly queued {newly_queued} examples (recycled={len(recycled_examples)}, new_ai={len(new_examples)})")

def get_examples_from_queue(db: Session, user_id: int, limit: int) -> List[Example]:
    # 1. Recuperar ítems huérfanos/no resueltos en SENT del usuario
    reusable_statement = (
        select(ExampleQueue)
        .where(
            ExampleQueue.user_id == user_id,
            ExampleQueue.is_active == True,
            ExampleQueue.status == QueueStatus.SENT
        )
        .order_by(ExampleQueue.created_at.asc())
        .limit(limit)
    )
    reusable_items = db.exec(reusable_statement).all()

    needed = limit - len(reusable_items)
    queue_items = list(reusable_items)

    # 2. Extraer el resto de PENDING del usuario
    if needed > 0:
        pending_statement = (
            select(ExampleQueue)
            .where(
                ExampleQueue.user_id == user_id,
                ExampleQueue.is_active == True,
                ExampleQueue.status == QueueStatus.PENDING
            )
            .order_by(ExampleQueue.created_at.asc())
            .limit(needed)
        )
        pending_items = db.exec(pending_statement).all()

        for item in pending_items:
            item.status = QueueStatus.SENT
            db.add(item)

        queue_items.extend(pending_items)
        db.commit()

    if not queue_items:
        return []

    # 3. Retornar objetos Example
    example_ids = [item.example_id for item in queue_items]
    examples = db.exec(
        select(Example)
        .where(Example.id.in_(example_ids))
        .options(joinedload(Example.example_words).joinedload(ExampleWord.word))
    )
    examples_dict = {e.id: e for e in examples.unique().all()}
    return [examples_dict[eid] for eid in example_ids if eid in examples_dict]



def resolve_and_increment_example(db: Session, example_id: int, user_id: int) -> Optional[Example]:
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
            featured_type = models.FeaturedType.EXAMPLE
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
                logger.info(f"[resolve_and_increment_example] Word {word.id} ({word.main}) marked as LEARNED for type {featured_type.value} (current_cycle_seen={stats.current_cycle_seen})")

            db.add(word)

            if word.batch_id:
                affected_batch_ids.add(word.batch_id)

    # 3. Marcar en la cola del usuario como RESOLVED
    queue_item = db.exec(
        select(ExampleQueue).where(
            ExampleQueue.user_id == user_id,
            ExampleQueue.example_id == example_id,
            ExampleQueue.status == QueueStatus.SENT,
            ExampleQueue.is_active == True,
        )
    ).first()

    if queue_item:
        queue_item.status = QueueStatus.RESOLVED
        db.add(queue_item)

    # 4. OPCIONAL: Evaluar si el Lote (Batch) se completó
    for batch_id in affected_batch_ids:
        _check_and_update_batch_status(db, batch_id)

    db.commit()
    db.refresh(example)
    return example


def resolve_and_increment_best_option(db: Session, queue_item_id: int, user_id: int) -> Optional[BestOptionQueue]:
    """
    Resolve a best_option exercise and increment word statistics.
    - Updates WordStatistics.times_seen for type BEST_OPTIONS
    - Evaluates if word is learned based on cycle count
    - Marks queue_item as RESOLVED
    """
    queue_item = db.exec(
        select(BestOptionQueue)
        .where(
            BestOptionQueue.id == queue_item_id,
            BestOptionQueue.user_id == user_id,
            BestOptionQueue.status == QueueStatus.SENT,
            BestOptionQueue.is_active == True
        )
        .options(joinedload(BestOptionQueue.best_option).joinedload(BestOption.word))
    ).first()

    if not queue_item:
        return None

    best_option = queue_item.best_option
    word = best_option.word

    if not word:
        return None

    now_utc = datetime.now(timezone.utc)

    # Get TARGET_CYCLE_SEEN from database configuration
    config = ConfigManager(db)
    target_cycle_seen = config.get_target_cycle_seen()

    # Update WordStatistics for BEST_OPTIONS type
    featured_type = models.FeaturedType.BEST_OPTIONS
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

    # Evaluate if word is learned
    if stats.current_cycle_seen >= target_cycle_seen and not stats.is_learned:
        stats.is_learned = True
        logger.info(f"[resolve_and_increment_best_option] Word {word.id} ({word.main}) marked as LEARNED for type {featured_type.value} (current_cycle_seen={stats.current_cycle_seen})")

    db.add(word)

    # Mark queue_item as RESOLVED
    queue_item.status = QueueStatus.RESOLVED
    db.add(queue_item)

    # Update batch status if needed
    if word.batch_id:
        _check_and_update_batch_status(db, word.batch_id)

    db.commit()
    db.refresh(queue_item)
    return queue_item


def _check_and_update_batch_status(db: Session, batch_id: int):
    """
    DEPRECATED: El estado ahora se maneja en BatchFeatured, no en Batch.
    Esta función se mantiene para compatibilidad pero no realiza cambios.
    """
    # Esta lógica ahora se maneja en BatchManager.get_words_with_transition()
    # donde se actualiza BatchFeatured.status según el tipo
    pass


def _activate_next_open_batch(db: Session, user_id: int):
    """
    DEPRECATED: El estado ahora se maneja en BatchFeatured, no en Batch.
    Esta función se mantiene para compatibilidad pero no realiza cambios.
    """
    # Esta lógica ahora se maneja en BatchManager.get_words_with_transition()
    pass


# ==========================================
# MEMORIA ESPACIADA (SPACED REPETITION)
# ==========================================

def reopen_batches_for_spaced_repetition(db: Session, user_id: int) -> dict:
    """
    Wrapper para BatchManager.reopen_batch_for_spaced_repetition().
    Mantenido para compatibilidad con código existente.
    """
    manager = BatchManager(db)
    return manager.reopen_batch_for_spaced_repetition(user_id)


def reopen_specific_batches(db: Session, user_id: int, batch_ids: List[int]) -> dict:
    """
    Wrapper para BatchManager.reopen_batches_by_ids().
    Mantenido para compatibilidad con código existente.
    """
    manager = BatchManager(db)
    return manager.reopen_batches_by_ids(user_id, batch_ids)


def get_batch_words(db: Session, batch_id: int, user_id: int) -> Optional[dict]:
    """
    Wrapper para BatchManager.get_batch_words().
    Mantenido para compatibilidad con código existente.
    """
    manager = BatchManager(db)
    return manager.get_batch_words(batch_id, user_id)


# ==========================================
# BEST OPTIONS QUEUE MANAGEMENT
# ==========================================

def enqueue_next_best_option_for_word(db: Session, user_id: int, word_id: int, current_sequence_order: int) -> Optional[BestOptionQueue]:
    """
    Auto-encola el siguiente ejercicio de best_option para una palabra cuando se resuelve uno.

    Busca el siguiente ejercicio (sequence_order + 1) de la misma palabra que:
    - Aún no esté encolado
    - Esté activo

    Si encuentra uno, lo agrega a la cola con estado PENDING.
    """

    next_sequence_order = current_sequence_order + 1

    # Buscar el siguiente ejercicio de esta palabra (máximo 4)
    if next_sequence_order > 4:
        logger.debug(f"[enqueue_next_best_option_for_word] No more exercises for word {word_id} (already at sequence 4)")
        return None

    next_best_option = db.exec(
        select(BestOption).where(
            BestOption.word_id == word_id,
            BestOption.sequence_order == next_sequence_order,
            BestOption.is_active == True
        )
    ).first()

    if not next_best_option:
        logger.debug(f"[enqueue_next_best_option_for_word] No exercise found for word {word_id} with sequence {next_sequence_order}")
        return None

    # Verificar que no esté ya en la cola
    existing_queue = db.exec(
        select(BestOptionQueue).where(
            BestOptionQueue.user_id == user_id,
            BestOptionQueue.best_option_id == next_best_option.id
        )
    ).first()

    if existing_queue:
        logger.debug(f"[enqueue_next_best_option_for_word] Exercise {next_best_option.id} already in queue for user {user_id}")
        return None

    # Agregar a la cola
    queue_item = BestOptionQueue(
        user_id=user_id,
        best_option_id=next_best_option.id,
        status=QueueStatus.PENDING
    )
    db.add(queue_item)
    db.commit()
    db.refresh(queue_item)

    logger.info(f"[enqueue_next_best_option_for_word] User {user_id}: Enqueued exercise {next_best_option.id} (sequence {next_sequence_order}) for word {word_id}")
    return queue_item


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
    featured_type: FeaturedType,
    limit: int = 50
) -> List[Word]:
    """Obtiene palabras por tipo de BatchFeatured."""
    manager = BatchManager(db)
    return manager.get_words_by_batch_featured_type(user_id, featured_type, limit)


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
    featured_type: Optional[FeaturedType] = None
) -> List[Dict[str, Any]]:
    """Obtiene todos los BatchFeatured de un usuario."""
    manager = BatchManager(db)
    return manager.get_all_batch_featured(user_id, featured_type)


def update_featured_stats_for_batch(db: Session, batch_id: int) -> None:
    """Actualiza estadísticas de BatchFeatured para un batch."""
    manager = BatchManager(db)
    manager.update_featured_stats_for_batch(batch_id)