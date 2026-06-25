from sqlmodel import Session, select, func
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone
from typing import List

# CORRECCIÓN: Ajustamos la importación al mismo nivel
import models


def paginate_query(db: Session, statement, page: int, limit: int) -> dict:
    """
    Toma un statement de SQLModel, aplica paginación y devuelve
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
            "has_prev": page > 1
        }
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

    # 🔥 LA CORRECCIÓN: Agregamos .unique() aquí para limpiar los resultados con joinedload
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
            "has_prev": page > 1
        }
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
        statement = (
            statement.outerjoin(models.WordStats)
            .order_by(models.WordStats.times_seen.desc().nullslast())
        )
    elif sort == "least_seen":
        statement = (
            statement.outerjoin(models.WordStats)
            .order_by(models.WordStats.times_seen.asc().nullsfirst())
        )

    return paginate_query(db, statement, page, limit)


def get_word_by_id(db: Session, word_id: int):
    return db.exec(select(models.Word).filter(models.Word.id == word_id)).first()


def create_word(db: Session, word_data: dict):
    normalized = word_data["main"].lower().strip()

    existing = db.exec(select(models.Word).filter(
        models.Word.normalized == normalized)).first()
    if existing:
        return None

    new_word = models.Word(**word_data, normalized=normalized)

    db.add(new_word)
    db.commit()
    db.refresh(new_word)
    return new_word


def increment_words_seen(db: Session, words):
    for w in words:
        if w.stats:
            w.stats.times_seen += 1
            w.stats.last_seen_at = datetime.now(timezone.utc)
        else:
            w.stats = models.WordStats(
                word_id=w.id,  # Asignamos explícitamente el id correspondiente
                times_seen=1,
                last_seen_at=datetime.now(timezone.utc)
            )
            db.add(w.stats)

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
    statement = (
        select(models.Word)
        .outerjoin(models.WordStats)
        .filter(models.Word.is_active == True)
        .order_by(models.WordStats.times_seen.asc().nullsfirst())
        .limit(limit)
    )
    return db.exec(statement).all()


def create_examples(db: Session, data: list[dict]):
    examples = []

    for item in data:
        example = models.Example(text=item["text"])
        db.add(example)
        db.flush()  # Genera el ID de example para usarlo abajo

        for word_data in item["words"]:
            example_word = models.ExampleWord(
                example_id=example.id,
                word_id=word_data["word_id"],
                text_form=word_data["word"]
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

    statement = statement.options(
        joinedload(models.Example.example_words).joinedload(
            models.ExampleWord.word)
    )

    # El cambio estructural de paginación debe aplicar .unique() al extraer los items
    return paginate_query(db, statement, page, limit)


def get_random_examples_by_words(db: Session, word_ids: List[int], limit: int = 5):
    if not word_ids:
        return []

    statement = (
        select(models.Example)
        .join(models.Example.example_words)
        .filter(
            models.Example.is_active == True,
            models.ExampleWord.word_id.in_(word_ids)
        )
        .options(joinedload(models.Example.example_words).joinedload(models.ExampleWord.word))
        .order_by(func.random())
        .limit(limit)
    )
    # 🔥 CORRECCIÓN: Agregamos .unique() antes de traer todo (.all())
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
