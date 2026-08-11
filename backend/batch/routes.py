"""
Rutas para gestión avanzada de batches usando BatchManager.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlmodel import Session
from logging_client import logger

from db import get_db
from models import User, ContentType
from auth.repository import get_current_user
from batch_manager import BatchManager
from decorators import log_endpoint
from batch import repository


router = APIRouter(prefix="/batches", tags=["batches"])


@router.get("/featured")
@log_endpoint
def get_all_batch_featured(
    content_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene todos los BatchFeatured del usuario.

    Query params:
    - content_type: Opcional, filtrar por tipo (example, best_options)
    """
    logger.info(f"[get_all_batch_featured] User {current_user.id}: Fetching all batch featured (type={content_type})")

    content_type_enum = None
    if content_type:
        try:
            content_type_enum = ContentType(content_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Tipo inválido. Opciones: example, best_options"
            )

    manager = BatchManager(db)
    featured_list = manager.get_all_batch_featured_by_user(current_user.id, content_type_enum)
    logger.info(f"[get_all_batch_featured] Retrieved {len(featured_list)} batch featured")

    return {
        "total_featured": len(featured_list),
        "featured": featured_list
    }


@router.get("/dormant")
@log_endpoint
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
        dormant = repository.get_dormant_batches(db, current_user.id, days_threshold)
        logger.info(f"[get_dormant_batches] User {current_user.id}: Found {len(dormant)} dormant batches")
        return {
            "days_threshold": days_threshold,
            "dormant_batches": dormant,
            "count": len(dormant)
        }
    except Exception as e:
        logger.error(f"[get_dormant_batches] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error obteniendo batches dormidos")


@router.get("/featured/type/{content_type}/words")
@log_endpoint
def get_words_by_featured_type(
    content_type: str,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene palabras asociadas a un tipo específico de BatchFeatured.

    Path params:
    - content_type: example, best_options

    Query params:
    - limit: Límite de palabras (default: 50)
    """
    try:
        content_type_enum = ContentType(content_type)
        words = repository.get_words_by_batch_featured_type(
            db,
            current_user.id,
            content_type_enum,
            limit
        )
        logger.info(f"[get_words_by_featured_type] User {current_user.id}: Retrieved {len(words)} words for type {content_type}")
        return {
            "content_type": content_type,
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
            detail="Tipo inválido. Opciones: example, best_options"
        )
    except Exception as e:
        logger.error(f"[get_words_by_featured_type] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error obteniendo palabras")


@router.post("/save-words-to-batches")
@log_endpoint
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

        result = repository.save_words_to_batches(
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


# ==========================================
# GESTIÓN DE BATCH FEATURED ESPECÍFICOS
# ==========================================

@router.get("/featured/{batch_featured_id}/words")
@log_endpoint
def get_batch_featured_words(
    batch_featured_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene todas las palabras asociadas a un BatchFeatured específico.
    """
    logger.debug(f"[get_batch_featured_words] User {current_user.id}: Fetching words for batch featured {batch_featured_id}")
    manager = BatchManager(db)
    batch_data = manager.get_words_for_batch_featured(batch_featured_id)

    if not batch_data:
        logger.warning(f"[get_batch_featured_words] BatchFeatured {batch_featured_id} not found")
        raise HTTPException(status_code=404, detail="BatchFeatured no encontrado")

    logger.info(f"[get_batch_featured_words] Retrieved {batch_data['total_words']} words")
    return batch_data


@router.patch("/featured/{batch_featured_id}/reopen")
@log_endpoint
def reopen_batch_featured(
    batch_featured_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reabre un BatchFeatured específico para revisión.
    """
    logger.info(f"[reopen_batch_featured] User {current_user.id}: Reopening batch featured {batch_featured_id}")
    manager = BatchManager(db)
    result = manager.reopen_batch_featured(batch_featured_id)

    if not result:
        logger.warning(f"[reopen_batch_featured] BatchFeatured {batch_featured_id} not found")
        raise HTTPException(status_code=404, detail="BatchFeatured no encontrado")

    logger.info(f"[reopen_batch_featured] BatchFeatured {batch_featured_id} reopened successfully")
    return result


@router.patch("/featured/reopen/multiple")
@log_endpoint
def reopen_multiple_batch_featured(
    batch_featured_ids: List[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reabre múltiples BatchFeatured específicos para revisión.

    Body esperado:
    {
      "batch_featured_ids": [1, 3, 5]
    }
    """
    logger.info(f"[reopen_multiple_batch_featured] User {current_user.id}: Reopening batch featured")

    if not batch_featured_ids:
        logger.error("[reopen_multiple_batch_featured] No batch featured IDs provided")
        raise HTTPException(status_code=400, detail="Debe proporcionar al menos un batch_featured_id")

    manager = BatchManager(db)
    result = manager.reopen_multiple_batch_featured(batch_featured_ids)

    logger.info(f"[reopen_multiple_batch_featured] Reopened {result['reopened_count']} batch featured")
    if result["failed"]:
        logger.warning(f"[reopen_multiple_batch_featured] Some batch featured failed: {result['failed']}")

    return result
