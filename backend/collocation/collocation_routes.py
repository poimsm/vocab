from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session
from typing import List
from sqlalchemy import func
from sqlmodel import select

from db import get_db
from logging_client import logger
from auth.repository import get_current_user
from models import User, Word, WordStatistics, LearningState, ContentType
from decorators import log_endpoint
from ai import generate_natural_pairs_from_words
from collocation.collocation_schemas import (
    CollocationItem,
    CollocationListResponse,
    CollocationCreateRequest,
    CollocationToggleRequest,
    TextSegment
)
from collocation.collocation_repository import CollocationRepository
from words.word_repository import WordRepository


router = APIRouter()


@router.get("/list", response_model=dict)
@log_endpoint
def get_collocations(
    status: str = "all",
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene las collocations del usuario actual con paginación.

    Parameters:
    - status: "all" (default), "marked", "not_marked"
    - page: página actual (default: 1)
    - limit: items por página (default: 15, máximo: 100)
    """
    repository = CollocationRepository(db)

    # Obtener total de collocations
    all_collocations = repository.get_user_collocations_filtered(current_user.id, status)
    total = len(all_collocations)

    # Calcular offset y aplicar paginación
    offset = (page - 1) * limit
    paginated_collocations = all_collocations[offset:offset + limit]

    items = []
    for c in paginated_collocations:
        segments = repository.get_text_segments(c)
        logger.debug(f"Collocation {c.id}: phrase='{c.phrase}', text_form='{c.text_form}', segments={segments}")
        items.append(
            CollocationItem(
                id=c.id,
                phrase=c.phrase,
                word_id=c.word_id,
                text=[TextSegment(**seg) for seg in segments],
                is_marked=c.is_marked
            )
        )

    # Calcular total de páginas
    pages = (total + limit - 1) // limit

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
        "status": "ok"
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
@log_endpoint
def create_collocation(
    request: CollocationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crea una nueva colocación."""
    repository = CollocationRepository(db)
    collocation = repository.create(
        user_id=current_user.id,
        phrase=request.phrase,
        word_id=request.word_id
    )
    logger.info(f"Created collocation {collocation.id} for user {current_user.id}")
    segments = repository.get_text_segments(collocation)
    return CollocationItem(
        id=collocation.id,
        phrase=collocation.phrase,
        word_id=collocation.word_id,
        text=[TextSegment(**seg) for seg in segments],
        is_marked=collocation.is_marked
    )


@router.patch("/{collocation_id}", response_model=CollocationItem)
@log_endpoint
def toggle_collocation_status(
    collocation_id: int,
    request: CollocationToggleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza el estado de marcado de una colocación."""
    repository = CollocationRepository(db)
    collocation = repository.toggle_marked(collocation_id, current_user.id, request.is_marked)

    if not collocation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collocation not found"
        )

    logger.info(f"Updated collocation {collocation_id} is_marked={request.is_marked}")
    segments = repository.get_text_segments(collocation)
    return CollocationItem(
        id=collocation.id,
        phrase=collocation.phrase,
        word_id=collocation.word_id,
        text=[TextSegment(**seg) for seg in segments],
        is_marked=collocation.is_marked
    )


@router.post("/batch")
@log_endpoint
def create_collocations_batch(
    phrases: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crea múltiples collocations de una vez."""
    repository = CollocationRepository(db)
    collocations = repository.create_many(current_user.id, phrases)
    logger.info(f"Created {len(collocations)} collocations for user {current_user.id}")
    items = []
    for c in collocations:
        segments = repository.get_text_segments(c)
        items.append(
            CollocationItem(
                id=c.id,
                phrase=c.phrase,
                word_id=c.word_id,
                text=[TextSegment(**seg) for seg in segments],
                is_marked=c.is_marked
            )
        )

    return {
        "created": len(collocations),
        "items": items
    }


@router.delete("/{collocation_id}")
@log_endpoint
def delete_collocation(
    collocation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Elimina una colocación."""
    repository = CollocationRepository(db)
    success = repository.delete(collocation_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collocation not found"
        )

    logger.info(f"Deleted collocation {collocation_id}")
    return {"status": "deleted"}


@router.delete("/")
@log_endpoint
def delete_all_collocations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Elimina todas las collocations del usuario."""
    repository = CollocationRepository(db)
    count = repository.delete_all(current_user.id)
    logger.info(f"Deleted {count} collocations for user {current_user.id}")
    return {"deleted": count}


@router.post("/generate-initial")
@log_endpoint
def generate_initial_collocations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Genera collocations iniciales si el usuario no tiene ninguna."""
    repository = CollocationRepository(db)
    existing = repository.get_user_collocations(current_user.id)

    if existing:
        return {
            "status": "already_exist",
            "count": len(existing)
        }

    # Initial collocations to seed
    initial_phrases = [
        {"phrase": "quivering hands"},
        {"phrase": "flushed cheeks"},
        {"phrase": "flung stone"},
        {"phrase": "grimacing face"},
        {"phrase": "sledgehammer blow"},
        {"phrase": "blowlamp flame"},
        {"phrase": "deep hatred"},
        {"phrase": "religious heretic"},
        {"phrase": "neat goatee"}
    ]

    collocations = repository.create_many(current_user.id, initial_phrases)
    logger.info(f"Generated {len(collocations)} initial collocations for user {current_user.id}")

    items = []
    for c in collocations:
        segments = repository.get_text_segments(c)
        items.append(
            CollocationItem(
                id=c.id,
                phrase=c.phrase,
                word_id=c.word_id,
                text=[TextSegment(**seg) for seg in segments],
                is_marked=c.is_marked
            )
        )

    return {
        "status": "created",
        "count": len(collocations),
        "items": items
    }


@router.post("/generate")
@log_endpoint
def generate_collocations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Genera collocations automáticas basadas en palabras vistas del usuario.

    Estrategia:
    - Obtiene máximo 15 palabras que el usuario ya haya visto (no NEW)
    - Preferencia por palabras en progreso (LEARNING, REINFORCING, SPACING, ALMOST_LEARNED)
    - Para cada palabra:
      - Si tiene collocations disponibles (is_in_use=False), devuelve una y la marca como is_in_use=True
      - Si no, genera nuevas usando IA, devuelve una y la marca como is_in_use=True
    """
    collocation_repo = CollocationRepository(db)

    # Obtener palabras vistas (excluyendo NEW)
    in_progress_states = [
        LearningState.LEARNING,
        LearningState.REINFORCING,
        LearningState.SPACING,
        LearningState.ALMOST_LEARNED,
        LearningState.LEARNED,
        LearningState.REVIEW
    ]

    # Obtener palabras en progreso primero
    in_progress_words = db.exec(
        select(Word)
        .join(WordStatistics)
        .where(
            Word.user_id == current_user.id,
            Word.is_active == True,
            WordStatistics.type == ContentType.EXAMPLE,
            WordStatistics.learning_state.in_(in_progress_states)
        )
        .distinct(Word.id)
    ).all()

    logger.info(f"Found {len(in_progress_words)} in-progress words for user {current_user.id}")

    # Si no hay palabras en progreso, intenta obtener NEW words
    selected_words = list(in_progress_words)
    if len(selected_words) < 15:
        remaining_needed = 15 - len(selected_words)
        new_words = db.exec(
            select(Word)
            .join(WordStatistics)
            .where(
                Word.user_id == current_user.id,
                Word.is_active == True,
                WordStatistics.type == ContentType.EXAMPLE,
                WordStatistics.learning_state == LearningState.NEW
            )
            .distinct(Word.id)
            .limit(remaining_needed)
        ).all()
        selected_words.extend(new_words)
        logger.info(f"Added {len(new_words)} NEW words to reach minimum")

    # Limitar a máximo 15
    selected_words = selected_words[:15]

    if not selected_words:
        logger.warning(f"No words available for user {current_user.id}")
        return {
            "status": "no_words",
            "message": "No words available to generate collocations",
            "count": 0,
            "items": []
        }

    logger.info(f"Selected {len(selected_words)} words for collocation generation")

    # Para cada palabra, obtener collocation disponible o generar nuevas
    result_collocations = []
    words_to_generate = []

    for word in selected_words:
        # Buscar collocation disponible
        available_collocation = collocation_repo.get_available_collocation_for_word(current_user.id, word.id)

        if available_collocation:
            # Marcar como en uso y agregar al resultado
            collocation_repo.mark_as_in_use(available_collocation.id)
            result_collocations.append(available_collocation)
            logger.info(f"Found available collocation {available_collocation.id} for word {word.id}")
        else:
            # Esta palabra necesita generación de nuevas collocations
            words_to_generate.append(word)

    # Generar nuevas collocations para palabras que no tienen disponibles
    if words_to_generate:
        logger.info(f"Generating new collocations for {len(words_to_generate)} words")
        response = generate_natural_pairs_from_words(words_to_generate)

        if response and response.get("results"):
            logger.info(f"Generated pairs for {len(response['results'])} words")

            # Crear collocations desde la respuesta (que tiene estructura word_id -> pairs)
            collocations_to_create = []

            for result in response["results"]:
                word_id = result.get("word_id")
                pairs = result.get("pairs", [])

                # Crear una collocation por cada pair para esta palabra
                for pair in pairs:
                    collocation_data = {
                        "phrase": pair.get("text", ""),
                        "word_id": word_id,
                        "text_form": pair.get("text_form", "")
                    }
                    collocations_to_create.append(collocation_data)

            # Crear todas las collocations
            if collocations_to_create:
                new_collocations = collocation_repo.create_many(current_user.id, collocations_to_create)
                logger.info(f"Created {len(new_collocations)} collocations")

                # Tomar una collocation por palabra a generar y marcarlas como en uso
                for word in words_to_generate:
                    word_collocations = [c for c in new_collocations if c.word_id == word.id]
                    if word_collocations:
                        collocation_repo.mark_as_in_use(word_collocations[0].id)
                        result_collocations.append(word_collocations[0])
                        logger.info(f"Created and marked collocation {word_collocations[0].id} for word {word.id}")
        else:
            logger.warning(f"AI failed to generate pairs for {len(words_to_generate)} words")

    logger.info(f"Returning {len(result_collocations)} collocations for user {current_user.id}")

    items = []
    for c in result_collocations:
        segments = collocation_repo.get_text_segments(c)
        logger.debug(f"Generated collocation {c.id}: phrase='{c.phrase}', text_form='{c.text_form}', segments={segments}")
        items.append(
            CollocationItem(
                id=c.id,
                phrase=c.phrase,
                word_id=c.word_id,
                text=[TextSegment(**seg) for seg in segments],
                is_marked=c.is_marked
            )
        )

    return {
        "status": "created" if result_collocations else "no_collocations",
        "count": len(result_collocations),
        "words_used": len(selected_words),
        "items": items
    }
