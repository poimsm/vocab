from fastapi import APIRouter, Depends, HTTPException, status
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
    CollocationToggleRequest
)
from collocation.collocation_repository import CollocationRepository
from words.word_repository import WordRepository


router = APIRouter()


@router.get("/list", response_model=CollocationListResponse)
@log_endpoint
def get_collocations(
    status: str = "all",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene las collocations del usuario actual.

    Parameters:
    - status: "all" (default), "marked", "not_marked"
    """
    repository = CollocationRepository(db)
    collocations = repository.get_user_collocations_filtered(current_user.id, status)

    items = [
        CollocationItem(id=c.id, phrase=c.phrase, is_marked=c.is_marked)
        for c in collocations
    ]

    return CollocationListResponse(items=items, total=len(items))


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
    return CollocationItem(id=collocation.id, phrase=collocation.phrase, is_marked=collocation.is_marked)


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
    return CollocationItem(id=collocation.id, phrase=collocation.phrase, is_marked=collocation.is_marked)


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
    return {
        "created": len(collocations),
        "items": [
            CollocationItem(id=c.id, phrase=c.phrase, is_marked=c.is_marked)
            for c in collocations
        ]
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

    return {
        "status": "created",
        "count": len(collocations),
        "items": [
            CollocationItem(id=c.id, phrase=c.phrase, is_marked=c.is_marked)
            for c in collocations
        ]
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
    - Si faltan palabras, completa con LEARNED/REVIEW
    - Usa round-robin para distribuir collocations entre palabras
    - Si se agotaron palabras nuevas, repite sobre las existentes
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

    # Generar pares naturales usando IA
    pairs = generate_natural_pairs_from_words(selected_words)

    if not pairs:
        logger.warning(f"AI failed to generate pairs for user {current_user.id}")
        return {
            "status": "generation_failed",
            "message": "Failed to generate natural word pairs",
            "count": 0,
            "items": []
        }

    logger.info(f"Generated {len(pairs)} natural pairs")

    # Crear collocations usando round-robin
    # Estrategia: distribuir pares entre palabras, repitiendo palabras si es necesario
    collocations_to_create = []
    word_index = 0
    selected_word_ids = [w.id for w in selected_words]

    for pair in pairs:
        # Round-robin: ciclar entre palabras seleccionadas
        word_id = selected_word_ids[word_index % len(selected_word_ids)]

        collocation_data = {
            "phrase": pair.get("text", ""),
            "word_id": word_id
        }
        collocations_to_create.append(collocation_data)
        word_index += 1

    # Crear todas las collocations
    collocations = collocation_repo.create_many(current_user.id, collocations_to_create)
    logger.info(f"Created {len(collocations)} collocations for user {current_user.id}")

    return {
        "status": "created",
        "count": len(collocations),
        "words_used": len(selected_words),
        "items": [
            CollocationItem(id=c.id, phrase=c.phrase, is_marked=c.is_marked)
            for c in collocations
        ]
    }
