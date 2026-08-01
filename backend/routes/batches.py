"""
Rutas para gestión avanzada de batches usando BatchManager.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from logging_config import logger

from db import get_db
from models import User, BatchFeaturedType
from auth import get_current_user
import crud
from batch_manager import BatchManager


router = APIRouter(prefix="/batches", tags=["batches"])


@router.get("/featured")
def get_batch_featured(
    featured_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene todos los BatchFeatured del usuario.

    Query params:
    - featured_type: Opcional, filtrar por tipo (active_learning, review, spaced_repetition)
    """
    try:
        featured_type_enum = None
        if featured_type:
            try:
                featured_type_enum = BatchFeaturedType(featured_type)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tipo inválido. Opciones: active_learning, review, spaced_repetition"
                )

        result = crud.get_all_batch_featured(db, current_user.id, featured_type_enum)
        logger.info(f"[get_batch_featured] User {current_user.id}: Retrieved {len(result)} featured batches")
        return {"featured_batches": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[get_batch_featured] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error obteniendo featured batches")


@router.get("/dormant")
def get_dormant_batches(
    days_threshold: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene batches dormidos (sin actividad por N días).

    Query params:
    - days_threshold: Número de días sin actividad (default: 7)
    """
    try:
        dormant = crud.get_dormant_batches(db, current_user.id, days_threshold)
        logger.info(f"[get_dormant_batches] User {current_user.id}: Found {len(dormant)} dormant batches")
        return {
            "days_threshold": days_threshold,
            "dormant_batches": dormant,
            "count": len(dormant)
        }
    except Exception as e:
        logger.error(f"[get_dormant_batches] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error obteniendo batches dormidos")


@router.get("/featured/type/{featured_type}/words")
def get_words_by_featured_type(
    featured_type: str,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene palabras asociadas a un tipo específico de BatchFeatured.

    Path params:
    - featured_type: active_learning, review, spaced_repetition

    Query params:
    - limit: Límite de palabras (default: 50)
    """
    try:
        featured_type_enum = BatchFeaturedType(featured_type)
        words = crud.get_words_by_batch_featured_type(
            db,
            current_user.id,
            featured_type_enum,
            limit
        )
        logger.info(f"[get_words_by_featured_type] User {current_user.id}: Retrieved {len(words)} words for type {featured_type}")
        return {
            "featured_type": featured_type,
            "words_count": len(words),
            "words": [
                {
                    "id": w.id,
                    "main": w.main,
                    "meaning": w.meaning,
                    "level": w.level,
                    "batch_id": w.batch_id
                }
                for w in words
            ]
        }
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Tipo inválido. Opciones: active_learning, review, spaced_repetition"
        )
    except Exception as e:
        logger.error(f"[get_words_by_featured_type] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error obteniendo palabras")


@router.post("/save-words-to-batches")
def save_words_to_batches(
    words_data: List[dict],
    source: str = Query("organic"),
    batch_title: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Guarda un lote de palabras en batches usando BatchManager.

    Body: Lista de diccionarios con datos de palabras
    [
        {
            "main": "serendipity",
            "meaning": "luck",
            "level": 3,
            "type": "noun"
        },
        ...
    ]

    Query params:
    - source: "organic" (default) o "bulk_import"
    - batch_title: Título del batch (solo para bulk_import)
    """
    try:
        if not words_data:
            raise HTTPException(status_code=400, detail="words_data vacío")

        from models import BatchSource
        try:
            source_enum = BatchSource(source)
        except ValueError:
            raise HTTPException(status_code=400, detail="source debe ser 'organic' o 'bulk_import'")

        result = crud.save_words_to_batches(
            db,
            current_user.id,
            words_data,
            source_enum,
            batch_title
        )

        logger.info(f"[save_words_to_batches] User {current_user.id}: Saved {result['words_count']} words to {len(result['batches'])} batches")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[save_words_to_batches] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
