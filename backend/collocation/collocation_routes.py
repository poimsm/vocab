from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List

from db import get_db
from logging_client import logger
from auth.repository import get_current_user
from models import User
from decorators import log_endpoint
from collocation.collocation_schemas import (
    CollocationItem,
    CollocationListResponse,
    CollocationCreateRequest,
    CollocationToggleRequest
)
from collocation.collocation_repository import CollocationRepository


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
