from sqlmodel import Session, func, select


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
