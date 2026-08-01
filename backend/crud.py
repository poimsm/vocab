import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload
from sqlmodel import Session, func, or_, select

from logging_config import logger

import crud
from batch_manager import BatchManager

import ai
import models
from models import (
    Batch,
    BatchFeatured,
    BatchFeaturedType,
    BatchSource,
    BatchStatus,
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
    QueueRefillStatus,
    QueueType,
)

# ==========================================
# GLOBAL CONFIGURATION HELPERS
# ==========================================

def get_config_value(db: Session, key: str, default_value: Any = None) -> Any:
    """
    Get a global configuration value from the database.
    Returns the value as string, or default_value if not found.
    """
    try:
        config = db.exec(
            select(GlobalConfiguration).where(GlobalConfiguration.key == key)
        ).first()
        if config:
            logger.debug(f"[get_config_value] Retrieved config {key}: {config.value}")
            return config.value
        logger.debug(f"[get_config_value] Config {key} not found, using default: {default_value}")
        return default_value
    except Exception as e:
        logger.warning(f"[get_config_value] Error retrieving config {key}: {str(e)}, using default: {default_value}")
        return default_value


def get_config_int(db: Session, key: str, default_value: int) -> int:
    """Get a global configuration value as integer."""
    value = get_config_value(db, key, str(default_value))
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"[get_config_int] Could not convert config {key} to int: {value}, using default: {default_value}")
        return default_value


def get_target_cycle_seen(db: Session) -> int:
    """Get TARGET_CYCLE_SEEN configuration (how many times word must be seen to mark as learned)."""
    return get_config_int(db, "TARGET_CYCLE_SEEN", 1)


def get_threshold_for_transition(db: Session) -> int:
    """Get THRESHOLD_FOR_TRANSITION configuration (min unlearned words to trigger batch transition)."""
    return get_config_int(db, "THRESHOLD_FOR_TRANSITION", 4)


def get_chunk_size(db: Session) -> int:
    """Get CHUNK_SIZE configuration (size for bulk word import chunks)."""
    return get_config_int(db, "CHUNK_SIZE", 15)


def get_batch_default_capacity(db: Session) -> int:
    """Get BATCH_DEFAULT_CAPACITY configuration (max words per batch)."""
    return get_config_int(db, "BATCH_DEFAULT_CAPACITY", 15)


def get_default_priority_words_limit(db: Session) -> int:
    """Get DEFAULT_PRIORITY_WORDS_LIMIT configuration."""
    return get_config_int(db, "DEFAULT_PRIORITY_WORDS_LIMIT", 10)


def get_refill_queue_emergency_limit(db: Session) -> int:
    """Get REFILL_QUEUE_EMERGENCY_LIMIT configuration."""
    return get_config_int(db, "REFILL_QUEUE_EMERGENCY_LIMIT", 8)


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
        statement = statement.order_by(models.Word.times_seen.desc().nullslast())
    elif sort == "least_seen":
        statement = statement.order_by(models.Word.times_seen.asc().nullsfirst())

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
    db.commit()
    db.refresh(new_word)
    return new_word


def increment_words_seen(db: Session, words: List[Word]):
    for w in words:
        w.times_seen += 1
        w.last_seen_at = datetime.now(timezone.utc)
        db.add(w)
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

    word.is_learned = not word.is_learned
    db.add(word)
    db.commit()
    db.refresh(word)
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
        .filter(models.Word.user_id == user_id, models.Word.is_active == True)
        .order_by(models.Word.times_seen.asc().nullsfirst())
        .limit(limit)
    )
    return db.exec(statement).all()


def get_words_least_seen_ordered(db: Session, user_id: int, limit: int = 10) -> List[Word]:
    statement = (
        select(Word)
        .where(Word.user_id == user_id, Word.is_active == True)
        .order_by(Word.times_seen.asc())
        .limit(limit * 3)
    )
    results = db.exec(statement).all()
    if not results:
        return []
    return random.sample(results, min(len(results), limit))


# ==========================================
# EJEMPLOS (EXAMPLES)
# ==========================================

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
                assoc = ExampleWord(
                    example_id=example.id,
                    word_id=word_id,
                    text_form=word.get("text_form", "") if isinstance(word, dict) else ""
                )
                db.add(assoc)

        created.append(example)

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
    return db.exec(statement).unique().all()


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
    if source == BatchSource.ORGANIC:
        open_batch = db.exec(
            select(Batch)
            .where(
                Batch.user_id == user_id,
                Batch.status == BatchStatus.OPEN,
                Batch.source == BatchSource.ORGANIC
            )
            .order_by(Batch.created_at.desc())
        ).first()

        if open_batch and len(open_batch.words) < open_batch.capacity:
            return open_batch

        if open_batch:
            open_batch.status = BatchStatus.ACTIVE
            db.add(open_batch)

        count_batches = db.exec(
            select(func.count(Batch.id)).where(Batch.user_id == user_id)
        ).one() or 0
        
        new_batch = Batch(
            user_id=user_id,
            title=f"Lote {count_batches + 1}",
            source=BatchSource.ORGANIC,
            status=BatchStatus.OPEN
        )
        db.add(new_batch)
        db.commit()
        db.refresh(new_batch)
        return new_batch

    else:
        count_batches = db.exec(
            select(func.count(Batch.id)).where(Batch.user_id == user_id)
        ).one() or 0

        new_batch = Batch(
            user_id=user_id,
            title=title or f"Importación {count_batches + 1}",
            source=BatchSource.BULK_IMPORT,
            status=BatchStatus.ACTIVE
        )
        db.add(new_batch)
        db.commit()
        db.refresh(new_batch)
        return new_batch


def update_batch_metrics(db: Session, batch_id: int):
    """Actualiza métricas de todos los BatchFeatured de un batch."""
    manager = BatchManager(db)
    manager.update_featured_stats_for_batch(batch_id)


def get_priority_words_via_batches(db: Session, user_id: int, limit: int = 10) -> List[Word]:
    # 1. BOOST (Solo activas y NO aprendidas)
    boosted_words = db.exec(
        select(Word)
        .where(
            Word.user_id == user_id, 
            Word.is_active == True, 
            Word.is_boosted == True,
            Word.is_learned == False  # <--- Excluir aprendidas
        )
        .limit(3)
    ).all()

    # 2. LOTES (ACTIVE u OPEN) - Ordenar por antigüedad (más antiguos primero)
    active_batches = db.exec(
        select(Batch)
        .where(
            Batch.user_id == user_id,
            Batch.status.in_([BatchStatus.ACTIVE, BatchStatus.OPEN])
        )
        .order_by(
            Batch.created_at.asc(),  # Más antiguos primero (PRIORIDAD)
            Batch.status.asc(),       # ACTIVE antes que OPEN
            Batch.priority.desc()     # Luego por prioridad
        )
        .limit(3)  # Traer hasta 3 batches para tener más flexibilidad en transición
    ).all()

    primary_batch_words: List[Word] = []
    secondary_batch_words: List[Word] = []

    if active_batches:
        primary_batch = active_batches[0]

        # Solo tomamos palabras Pendientes de aprender
        unlearned_primary = db.exec(
            select(Word)
            .where(
                Word.batch_id == primary_batch.id,
                Word.is_active == True,
                Word.is_learned == False, # <--- Excluir aprendidas
                Word.is_boosted == False
            )
            .order_by(Word.current_cycle_seen.asc(), Word.last_seen_at.asc().nullsfirst())
        ).all()

        threshold_for_transition = get_threshold_for_transition(db)
        logger.debug(f"[get_priority_words_via_batches] Using THRESHOLD_FOR_TRANSITION={threshold_for_transition}")

        if len(unlearned_primary) <= threshold_for_transition and len(active_batches) > 1:
            # El batch primario está casi completo, comenzar a introducir el siguiente
            primary_batch_words = unlearned_primary
            needed_from_next = limit - len(boosted_words) - len(primary_batch_words)

            if needed_from_next > 0:
                next_batch = active_batches[1]
                secondary_batch_words = db.exec(
                    select(Word)
                    .where(
                        Word.batch_id == next_batch.id,
                        Word.is_active == True,
                        Word.is_learned == False,
                        Word.is_boosted == False
                    )
                    .order_by(Word.current_cycle_seen.asc(), Word.last_seen_at.asc().nullsfirst())
                    .limit(needed_from_next)
                ).all()
        else:
            # Batch primario aún tiene muchas palabras, enfocarse en él
            primary_batch_words = unlearned_primary[:6]

    # 3. OLEAJE ANTIGUO (Repaso de palabras de lotes completados que AÚN no estén aprendidas)
    batch_words_count = len(primary_batch_words) + len(secondary_batch_words)
    needed_old = max(limit - len(boosted_words) - batch_words_count, 0)

    old_words = []
    if needed_old > 0:
        old_words = db.exec(
            select(Word)
            .join(Batch)
            .where(
                Word.user_id == user_id,
                Word.is_active == True,
                Word.is_learned == False, # <--- Excluir aprendidas si no deseas repasarlas
                Word.is_boosted == False,
                Batch.status == BatchStatus.COMPLETED
            )
            .order_by(Word.last_seen_at.asc().nullsfirst())
            .limit(needed_old)
        ).all()

    # 4. CONSOLIDAR
    candidate_dict = {
        w.id: w for w in (boosted_words + primary_batch_words + secondary_batch_words + old_words)
    }

    return list(candidate_dict.values())

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

    # 🚨 CLAVE 2: Obtener solo palabras prioritarias NO APRENDIDAS (is_learned = False)
    total_words_needed = (recycle_amount * 2) + ai_simple_amount + ai_mixed_amount
    priority_words = crud.get_priority_words_via_batches(
        db, user_id=user_id, limit=max(total_words_needed, 8)
    )

    if not priority_words:
        return

    # 1. RECICLAR EJEMPLOS EXISTENTES (Que el usuario NUNCA haya visto)
    recycled_examples = []
    if recycle_amount > 0:
        for word in priority_words:
            if len(recycled_examples) >= recycle_amount:
                break
            
            statement = (
                select(Example)
                .join(Example.example_words)
                .join(ExampleWord.word)
                .where(
                    Example.is_active == True,
                    Example.type == ExampleType.EXPLORE,
                    ExampleWord.word_id == word.id,
                    Word.is_learned == False, # No incluir si ya se aprendió
                    Word.is_active == True
                )
            )
            
            # Garantiza no repetir ejemplos ya presentes en la cola del usuario
            if excluded_ids:
                statement = statement.where(Example.id.not_in(excluded_ids))
                
            statement = statement.order_by(
                Example.times_seen.asc(), Example.created_at.desc()
            ).limit(1)

            best_example = db.exec(statement).first()
            if best_example:
                recycled_examples.append(best_example)
                excluded_ids.append(best_example.id)

    # 2. GENERAR NUEVOS EJEMPLOS CON IA
    new_examples = []
    total_ai_required = ai_simple_amount + ai_mixed_amount
    
    if total_ai_required > 0:
        words_for_ai = priority_words[:total_ai_required * 2]
        current_index = 0

        # Simple
        if ai_simple_amount > 0 and len(words_for_ai) >= current_index:
            words_for_simple = words_for_ai[current_index : current_index + ai_simple_amount]
            if words_for_simple:
                raw_simple = ai.generate_examples_from_words(words_for_simple)
                new_examples.extend(create_examples(db, raw_simple[:ai_simple_amount]))
                current_index += len(words_for_simple)

        # Mixta
        if ai_mixed_amount > 0 and len(words_for_ai) >= current_index:
            words_for_mixed = words_for_ai[current_index : current_index + ai_mixed_amount]
            if words_for_mixed:
                raw_mixed = ai.generate_mixed_examples_from_words(words_for_mixed)
                new_examples.extend(create_examples(db, raw_mixed[:ai_mixed_amount]))

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
    target_cycle_seen = get_target_cycle_seen(db)

    # 2. Incrementar contadores en palabras y evaluar si están aprendidas
    seen_word_ids = set()
    affected_batch_ids = set()

    for ew in example.example_words:
        word = ew.word
        if word and word.id not in seen_word_ids:
            seen_word_ids.add(word.id)

            word.times_seen += 1
            word.current_cycle_seen += 1
            word.last_seen_at = now_utc

            # ✅ EVALUACIÓN AUTOMÁTICA DE IS_LEARNED
            if word.current_cycle_seen >= target_cycle_seen and not word.is_learned:
                word.is_learned = True
                logger.info(f"[resolve_and_increment_example] Word {word.id} ({word.main}) marked as LEARNED (current_cycle_seen={word.current_cycle_seen})")

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


def _check_and_update_batch_status(db: Session, batch_id: int):
    batch = db.get(Batch, batch_id)
    if not batch or batch.status == BatchStatus.COMPLETED:
        return

    # Contar total de palabras y palabras aprendidas en este lote
    total_words = db.exec(
        select(func.count(Word.id)).where(Word.batch_id == batch_id, Word.is_active == True)
    ).one() or 0

    if total_words == 0:
        return

    learned_words = db.exec(
        select(func.count(Word.id)).where(
            Word.batch_id == batch_id,
            Word.is_active == True,
            Word.is_learned == True
        )
    ).one() or 0

    # Calcular progreso (0.0 a 100.0)
    mastery_progress = round((learned_words / total_words) * 100, 2)

    # Si al menos el 80% están aprendidas, completamos el lote
    if mastery_progress >= 80.0:
        batch.status = BatchStatus.COMPLETED
        batch.completed_at = datetime.now(timezone.utc)

        # Activar el siguiente lote disponible si no hay ninguno activo
        _activate_next_open_batch(db, user_id=batch.user_id)

    db.add(batch)


def _activate_next_open_batch(db: Session, user_id: int):
    # Verificamos si ya hay un lote activo
    has_active = db.exec(
        select(Batch).where(Batch.user_id == user_id, Batch.status == BatchStatus.ACTIVE)
    ).first()

    if not has_active:
        # Promovemos el lote OPEN de mayor prioridad
        next_batch = db.exec(
            select(Batch)
            .where(Batch.user_id == user_id, Batch.status == BatchStatus.OPEN)
            .order_by(Batch.priority.desc(), Batch.created_at.asc())
        ).first()

        if next_batch:
            next_batch.status = BatchStatus.ACTIVE
            db.add(next_batch)


# ==========================================
# MEMORIA ESPACIADA (SPACED REPETITION)
# ==========================================

def reopen_batches_for_spaced_repetition(db: Session, user_id: int) -> dict:
    """
    Reabre gradualmente batches completados antiguos para memoria espaciada.

    Estrategia:
    - Cada día, reabre solo 1 batch completado (el más antiguo)
    - Marca todas sus palabras como is_learned=False (para revisión)
    - Cambia su estado a OPEN

    Esto permite que el usuario revise palabras "antiguas" de forma gradual.
    """
    from datetime import datetime, timedelta, timezone

    # Obtener batches COMPLETED del usuario, ordenados por antigüedad
    completed_batches = db.exec(
        select(Batch)
        .where(
            Batch.user_id == user_id,
            Batch.status == BatchStatus.COMPLETED
        )
        .order_by(Batch.completed_at.asc())  # Más antiguos primero
    ).all()

    if not completed_batches:
        logger.info(f"[reopen_batches_spaced_repetition] User {user_id}: No completed batches to reopen")
        return {"reopened": 0, "message": "No hay batches completados para reabrir"}

    # Reabre solo el batch más antiguo (1 por día)
    batch_to_reopen = completed_batches[0]

    try:
        # Marcar todas las palabras del batch como is_learned=False
        words = db.exec(
            select(Word).where(Word.batch_id == batch_to_reopen.id)
        ).all()

        for word in words:
            word.is_learned = False
            word.current_cycle_seen = 0  # Resetear el ciclo
            db.add(word)

        # Cambiar estado del batch a OPEN
        batch_to_reopen.status = BatchStatus.OPEN
        batch_to_reopen.completed_at = None
        db.add(batch_to_reopen)

        db.commit()

        logger.info(f"[reopen_batches_spaced_repetition] Batch #{batch_to_reopen.id} reopened for user {user_id}. Words: {len(words)}")

        return {
            "reopened": 1,
            "batch_id": batch_to_reopen.id,
            "batch_title": batch_to_reopen.title,
            "words_count": len(words),
            "message": f"Batch '{batch_to_reopen.title}' reabierto para revisión"
        }

    except Exception as e:
        logger.error(f"[reopen_batches_spaced_repetition] Error reopening batch: {str(e)}", exc_info=True)
        return {"reopened": 0, "error": str(e)}


def reopen_specific_batches(db: Session, user_id: int, batch_ids: List[int]) -> dict:
    """
    Reabre manualmente batches específicos (para el usuario).
    """
    reopened = []
    failed = []

    for batch_id in batch_ids:
        try:
            batch = db.exec(
                select(Batch).where(
                    Batch.id == batch_id,
                    Batch.user_id == user_id
                )
            ).first()

            if not batch:
                failed.append({"batch_id": batch_id, "reason": "No encontrado"})
                continue

            # Marcar palabras como is_learned=False
            words = db.exec(
                select(Word).where(Word.batch_id == batch.id)
            ).all()

            for word in words:
                word.is_learned = False
                word.current_cycle_seen = 0
                db.add(word)

            # Cambiar estado a ACTIVE (para revisión)
            batch.status = BatchStatus.ACTIVE
            batch.completed_at = None
            db.add(batch)

            reopened.append({
                "batch_id": batch.id,
                "title": batch.title,
                "words_count": len(words)
            })

            logger.info(f"[reopen_specific_batches] Batch #{batch_id} manually reopened")

        except Exception as e:
            failed.append({"batch_id": batch_id, "reason": str(e)})
            logger.error(f"[reopen_specific_batches] Error in batch {batch_id}: {str(e)}")

    db.commit()

    return {
        "reopened_count": len(reopened),
        "reopened": reopened,
        "failed": failed
    }


def get_batch_words(db: Session, batch_id: int, user_id: int) -> Optional[dict]:
    """
    Retorna todas las palabras asociadas a un batch.
    """
    batch = db.exec(
        select(Batch).where(
            Batch.id == batch_id,
            Batch.user_id == user_id
        )
    ).first()

    if not batch:
        return None

    words = db.exec(
        select(Word).where(Word.batch_id == batch_id)
    ).all()

    # Calcular progreso desde las palabras
    total_words = len(words)
    learned_words = sum(1 for w in words if w.is_learned)
    batch_progress = round((learned_words / total_words * 100), 2) if total_words > 0 else 0.0

    return {
        "batch_id": batch.id,
        "batch_title": batch.title,
        "batch_status": batch.status.value,
        "batch_progress": batch_progress,
        "total_words": total_words,
        "words": [
            {
                "id": w.id,
                "main": w.main,
                "meaning": w.meaning,
                "type": w.type,
                "level": w.level,
                "is_learned": w.is_learned,
                "is_active": w.is_active,
                "times_seen": w.times_seen,
                "last_seen_at": w.last_seen_at
            }
            for w in words
        ]
    }


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
    featured_type: BatchFeaturedType,
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
    featured_type: Optional[BatchFeaturedType] = None
) -> List[Dict[str, Any]]:
    """Obtiene todos los BatchFeatured de un usuario."""
    manager = BatchManager(db)
    return manager.get_all_batch_featured(user_id, featured_type)


def update_featured_stats_for_batch(db: Session, batch_id: int) -> None:
    """Actualiza estadísticas de BatchFeatured para un batch."""
    manager = BatchManager(db)
    manager.update_featured_stats_for_batch(batch_id)