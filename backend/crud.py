import re, random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload
from sqlmodel import Session, func, select

import ai
import models
from models import Example, ExampleQueue, ExampleWord, QueueStatus, Word


def paginate_query(db: Session, statement, page: int, limit: int) -> dict:
    """Toma un statement de SQLModel, aplica paginación y devuelve

    la estructura estándar con metadatos.
    """
    if page < 1:
        page = 1
    if limit < 1:
        limit = 15

    # 1. Contar el total usando una subconsulta limpia
    count_statement = select(func.count()).select_from(statement.subquery())
    total_items = db.exec(count_statement).one()

    # 2. Calcular el desplazamiento (offset)
    offset = (page - 1) * limit

    # 3. Obtener los registros de la página actual
    paginated_statement = statement.offset(offset).limit(limit)
    items = db.exec(paginated_statement).unique().all()

    # 4. Calcular el total de páginas
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


def paginate_query2(db: Session, statement, page: int, limit: int) -> dict:
    if page < 1:
        page = 1
    if limit < 1:
        limit = 15

    count_statement = select(func.count()).select_from(statement.subquery())
    total_items = db.exec(count_statement).one()

    offset = (page - 1) * limit
    paginated_statement = statement.offset(offset).limit(limit)

    # Agregamos .unique() aquí para limpiar los resultados con joinedload
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


def get_words(db: Session, sort: str = "newest", page: int = 1, limit: int = 15):
    # SQLModel prefiere agrupar tuplas o selecciones explícitas usando select()
    statement = (
        select(models.Word, func.count(
            models.ExampleWord.example_id).label("total_examples"))
        .filter(models.Word.is_active == True)
        .outerjoin(models.ExampleWord)
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
        # Corregido: Usa el campo directo de Word
        statement = statement.order_by(
            models.Word.times_seen.desc().nullslast())
    elif sort == "least_seen":
        # Corregido: Usa el campo directo de Word
        statement = statement.order_by(
            models.Word.times_seen.asc().nullsfirst())

    return paginate_query(db, statement, page, limit)


def get_word_by_id(db: Session, word_id: int):
    return db.exec(select(models.Word).filter(models.Word.id == word_id)).first()


def create_word(db: Session, word_data: dict):
    normalized = word_data["main"].lower().strip()

    existing = db.exec(
        select(models.Word).filter(models.Word.normalized ==
                                   normalized, models.Word.is_active == True)
    ).first()

    if existing:
        return None

    new_word = models.Word(**word_data, normalized=normalized)

    db.add(new_word)
    db.commit()
    db.refresh(new_word)
    return new_word


def increment_words_seen(db: Session, words: List[Word]):
    """Incrementa las visualizaciones directamente en el modelo Word."""
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


def get_words_least_seen(db: Session, limit: int = 15):
    # Corregido: Removido outerjoin obsoleto, usa Word.times_seen
    statement = (
        select(models.Word)
        .filter(models.Word.is_active == True)
        .order_by(models.Word.times_seen.asc().nullsfirst())
        .limit(limit)
    )
    return db.exec(statement).all()


def create_examples(db: Session, data: list[dict]):
    examples = []

    for item in data:
        # 1. Normalizar el texto del ejemplo
        text_raw = item["text"]
        normalized_text = text_raw.lower().strip()
        normalized_text = re.sub(r"[.,;:!?¿¡]$", "", normalized_text).strip()

        # 2. Buscar si ya existe
        existing_example = db.exec(
            select(models.Example).where(
                models.Example.normalized == normalized_text, models.Example.is_active == True
            )
        ).first()

        if existing_example:
            examples.append(existing_example)
            continue

        # 3. Si no existe, lo creamos
        example = models.Example(text=text_raw, normalized=normalized_text)
        db.add(example)
        db.flush()

        # 4. Crear las relaciones
        for word_data in item["words"]:
            example_word = models.ExampleWord(
                example_id=example.id, word_id=word_data["word_id"], text_form=word_data["word"]
            )
            db.add(example_word)

        examples.append(example)

    db.commit()

    for example in examples:
        db.refresh(example)

    return examples


def get_examples(db: Session, sort: str = "newest", word_id: int = None, page: int = 1, limit: int = 15):
    statement = select(models.Example).filter(models.Example.is_active == True)

    if word_id is not None:
        statement = statement.join(models.Example.example_words).filter(
            models.ExampleWord.word_id == word_id)

    if sort == "newest":
        statement = statement.order_by(models.Example.id.desc())
    elif sort == "oldest":
        statement = statement.order_by(models.Example.id.asc())
    elif sort == "alphabetical":
        statement = statement.order_by(models.Example.text.asc())
    elif sort == "favorites":
        statement = statement.order_by(
            models.Example.is_favorite.desc(), models.Example.id.desc())

    statement = statement.options(joinedload(
        models.Example.example_words).joinedload(models.ExampleWord.word))

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
    """Incrementa en 1 el contador times_seen de una lista de ejemplos."""
    for example in examples:
        example.times_seen += 1
        db.add(example)
    db.commit()


def get_words_least_seen_ordered(db: Session, limit: int = 10) -> List[Word]:
    # Pedimos el triple de lo necesario para tener un "pool" de variedad
    statement = (
        select(Word)
        .where(Word.is_active == True)
        .order_by(Word.times_seen.asc())
        .limit(limit * 3) 
    )
    results = db.exec(statement).all()
    # Mezclamos el resultado para no darle siempre prioridad a los mismos IDs bajos
    return random.sample(results, min(len(results), limit))


def get_pending_examples(db: Session, limit: int = 15) -> List[Example]:
    statement = (
        select(Example)
        .where(Example.is_active == True, Example.is_pending == True)
        .options(joinedload(Example.example_words).joinedload(ExampleWord.word))
        .order_by(Example.times_seen.asc(), Example.created_at.desc())
        .limit(limit)
    )
    return db.exec(statement).unique().all()


def resolve_and_increment_example(db: Session, example_id: int) -> Optional[Example]:
    statement = (
        select(Example)
        .where(Example.id == example_id)
        .options(joinedload(Example.example_words).joinedload(ExampleWord.word))
    )
    example = db.exec(statement).first()
    if not example:
        return None

    # 1. Cambiar estado del ejemplo base
    example.times_seen += 1
    db.add(example)

    # 2. Incrementar visualizaciones de palabras asociadas directamente en Word
    seen_word_ids = set()
    for ew in example.example_words:
        word = ew.word
        if word and word.id not in seen_word_ids:
            word.times_seen += 1
            word.last_seen_at = datetime.now(timezone.utc)
            db.add(word)
            seen_word_ids.add(word.id)

    # 3. Buscar registro en la cola y pasarlo a RESOLVED
    queue_item = db.exec(
        select(ExampleQueue).where(
            ExampleQueue.example_id == example_id,
            ExampleQueue.status == QueueStatus.SENT,
            ExampleQueue.is_active == True,
        )
    ).first()

    if queue_item:
        queue_item.status = QueueStatus.RESOLVED
        db.add(queue_item)

    db.commit()
    db.refresh(example)
    return example


def get_explore_configuration(db: Session) -> dict:
    total_examples = db.exec(select(func.count()).select_from(
        Example).where(Example.is_active == True)).one()

    if total_examples <= 15:
        return {"ai_mixed_generation_amount": 3, "ai_simple_generation_amount": 6, "recycled_words_amount": 0}
    elif total_examples <= 30:
        return {"ai_mixed_generation_amount": 6, "ai_simple_generation_amount": 6, "recycled_words_amount": 0}
    elif total_examples <= 60:
        return {"ai_mixed_generation_amount": 6, "ai_simple_generation_amount": 6, "recycled_words_amount": 3}
    else:
        return {"ai_mixed_generation_amount": 6, "ai_simple_generation_amount": 6, "recycled_words_amount": 8}


def refill_example_queue(db: Session):
    config = get_explore_configuration(db)
    ai_mixed_amount = config.get("ai_mixed_generation_amount", 0)
    ai_simple_amount = config.get("ai_simple_generation_amount", 0)
    recycle_amount = config.get("recycled_words_amount", 0)

    queue_statement = select(ExampleQueue.example_id).where(
        ExampleQueue.is_active == True, ExampleQueue.status.in_(
            [QueueStatus.PENDING, QueueStatus.SENT])
    )
    excluded_ids = list(db.exec(queue_statement).all())

    # 1. RECICLAR EJEMPLOS
    recycled_examples = []
    if recycle_amount > 0:
        words = get_words_least_seen_ordered(db, limit=recycle_amount * 3)
        for word in words:
            if len(recycled_examples) >= recycle_amount:
                break
            statement = select(Example).join(Example.example_words).where(
                Example.is_active == True, ExampleWord.word_id == word.id
            )
            if excluded_ids:
                statement = statement.where(Example.id.not_in(excluded_ids))
            statement = statement.order_by(
                Example.times_seen.asc(), Example.created_at.desc()).limit(1)

            best_example = db.exec(statement).first()
            if best_example:
                recycled_examples.append(best_example)
                excluded_ids.append(best_example.id)

    # 2. GENERAR EJEMPLOS CON IA
    new_examples = []
    total_ai_required = ai_simple_amount + ai_mixed_amount
    if total_ai_required > 0:
        words_for_ai = get_words_least_seen_ordered(
            db, limit=total_ai_required * 2)
        current_index = 0

        if ai_simple_amount > 0:
            words_for_simple = words_for_ai[current_index:
                                            current_index + ai_simple_amount]
            if words_for_simple:
                raw_simple = ai.generate_examples_from_words(words_for_simple)
                new_examples.extend(create_examples(
                    db, raw_simple[:ai_simple_amount]))
                current_index += ai_simple_amount

        if ai_mixed_amount > 0:
            words_for_mixed = words_for_ai[current_index:
                                           current_index + ai_mixed_amount]
            if words_for_mixed:
                raw_mixed = ai.generate_mixed_examples_from_words(
                    words_for_mixed)
                new_examples.extend(create_examples(
                    db, raw_mixed[:ai_mixed_amount]))

    # 3. ENCOLAR EN ESTADO PENDING
    all_candidates = recycled_examples + new_examples
    for example in all_candidates:
        already_waiting = db.exec(
            select(ExampleQueue).where(
                ExampleQueue.example_id == example.id,
                ExampleQueue.is_active == True,
                ExampleQueue.status.in_(
                    [QueueStatus.PENDING, QueueStatus.SENT]),
            )
        ).first()

        if not already_waiting:
            queue_item = ExampleQueue(
                example_id=example.id, status=QueueStatus.PENDING)
            db.add(queue_item)

    db.commit()


def get_examples_from_queue(db: Session, limit: int) -> List[Example]:
    """
    Busca ejemplos que ya fueron enviados (SENT) pero no resueltos para reutilizarlos.
    Si no completan el límite, extrae el resto de los que están en PENDING.
    """
    # 1. Intentar recuperar primero los que se quedaron huérfanos en SENT
    reusable_statement = (
        select(ExampleQueue)
        .where(ExampleQueue.is_active == True, ExampleQueue.status == QueueStatus.SENT)
        .order_by(ExampleQueue.created_at.asc())
        .limit(limit)
    )
    reusable_items = db.exec(reusable_statement).all()

    needed = limit - len(reusable_items)
    queue_items = list(reusable_items)

    # 2. Si faltan para cumplir el lote, jalamos de los PENDING
    if needed > 0:
        pending_statement = (
            select(ExampleQueue)
            .where(ExampleQueue.is_active == True, ExampleQueue.status == QueueStatus.PENDING)
            .order_by(ExampleQueue.created_at.asc())
            .limit(needed)
        )
        pending_items = db.exec(pending_statement).all()

        # A los nuevos que extraemos de PENDING, los pasamos a SENT
        for item in pending_items:
            item.status = QueueStatus.SENT
            db.add(item)

        queue_items.extend(pending_items)
        db.commit()

    if not queue_items:
        return []

    # 3. Construir y retornar los objetos Example ordenados como venían
    example_ids = [item.example_id for item in queue_items]
    examples = db.exec(
        select(Example)
        .where(Example.id.in_(example_ids))
        .options(joinedload(Example.example_words).joinedload(ExampleWord.word))
    )
    examples_dict = {e.id: e for e in examples.unique().all()}
    return [examples_dict[eid] for eid in example_ids if eid in examples_dict]
