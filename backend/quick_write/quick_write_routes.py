from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlmodel import Session
from db import get_db
from models import User
from auth.repository import get_current_user
from logging_client import logger
from decorators import log_endpoint
from typing import Optional, List
from quick_write.quick_write_schemas import (
    QuickWriteCreate,
    QuickWriteUpdate,
    QuickWriteResponse,
    QuickWriteListResponse,
    GenerateQuickWriteRequest
)
from quick_write.quick_write_repository import QuickWriteRepository
from quick_write.grammar_engine import GrammarEngine
from words.word_repository import WordRepository
from models import ContentType, LearningState
from sqlmodel import select
from activity.user_activity_service import UserActivityService
import ai


router = APIRouter()
grammar = GrammarEngine()


@router.get("", response_model=QuickWriteListResponse)
@log_endpoint
def get_quick_writes(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("newest"),
    status: str = Query("all", regex="^(all|completed)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene todos los ejercicios del usuario con paginación y filtro opcional"""
    logger.info(f"[get_quick_writes] User {current_user.id}: Fetching exercises (page={page}, limit={limit}, sort={sort}, status={status})")

    # Log de actividad
    UserActivityService.log_page_view(
        db=db,
        user_id=current_user.id,
        page_name="quick_write_list",
        details={
            "page": page,
            "limit": limit,
            "sort": sort,
            "status": status
        }
    )

    repo = QuickWriteRepository(db)
    data = repo.get_with_pagination(current_user.id, page, limit, sort, status)

    items = [QuickWriteResponse.model_validate(note) for note in data["items"]]

    return QuickWriteListResponse(
        items=items,
        total=data["total"],
        pages=data["pages"]
    )


@router.get("/{note_id}", response_model=QuickWriteResponse)
@log_endpoint
def get_quick_write(
    note_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene un ejercicio específico"""
    logger.debug(f"[get_quick_write] User {current_user.id}: Fetching exercise {note_id}")

    # Log de actividad
    UserActivityService.log_endpoint_visit(
        db=db,
        user_id=current_user.id,
        endpoint=f"/quick-write/{note_id}",
        method="GET",
        details={"note_id": note_id}
    )

    repo = QuickWriteRepository(db)
    note = repo.get(note_id, current_user.id)

    if not note:
        logger.warning(f"[get_quick_write] Exercise {note_id} not found")
        raise HTTPException(status_code=404, detail="Exercise not found")

    return QuickWriteResponse.model_validate(note)


@router.post("/generate")
@log_endpoint
def generate_quick_write_exercises(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    word_ids: Optional[List[int]] = Body(None),
    user_id: Optional[int] = Body(None)
):
    """Encola la generación de ejercicios Quick Write usando IA"""

    # Usar user_id proporcionado o por defecto current_user.id
    target_user_id = user_id if user_id is not None else current_user.id

    logger.info(f"[generate_quick_write_exercises] User {target_user_id}: Requesting generation")

    # Log de actividad
    UserActivityService.log_feature_interaction(
        db=db,
        user_id=current_user.id,
        feature_name="quick_write_generation",
        interaction_type="generate",
        details={
            "target_user_id": target_user_id,
            "word_ids_count": len(word_ids) if word_ids else 0
        }
    )

    # Si no se proporcionan word_ids, obtenerlas por prioridad de aprendizaje
    if not word_ids:
        logger.debug(f"[generate_quick_write_exercises] No word_ids provided, fetching words by learning priority")
        word_repo = WordRepository(db)

        # NIVEL 1: Intentar con tipo EXAMPLE
        words = word_repo.get_words_by_learning_priority(
            user_id=target_user_id,
            limit=40,
            content_type=ContentType.EXAMPLE
        )

        # FALLBACK 1: Si no hay con tipo EXAMPLE, intentar con BEST_OPTIONS
        if not words:
            logger.info(f"[generate_quick_write_exercises] No words with ContentType.EXAMPLE, trying BEST_OPTIONS")
            words = word_repo.get_words_by_learning_priority(
                user_id=target_user_id,
                limit=40,
                content_type=ContentType.BEST_OPTIONS
            )

        # FALLBACK 2: Si no hay con ningún tipo específico, traer cualquier palabra activa
        if not words:
            logger.info(f"[generate_quick_write_exercises] No words with specific content_type, trying all active words")
            from models import Word
            words = db.exec(
                select(Word).where(
                    Word.user_id == target_user_id,
                    Word.is_active == True
                )
            ).all()

            # Si hay más que el límite, tomar una muestra aleatoria
            if len(words) > 40:
                import random
                words = random.sample(words, 40)
                logger.info(f"[generate_quick_write_exercises] Sampled {len(words)} random active words")

        if not words:
            raise HTTPException(status_code=400, detail="No words available for exercise generation")

        word_ids = [word.id for word in words]
        logger.info(f"[generate_quick_write_exercises] Fetched {len(word_ids)} words")
    else:
        logger.info(f"[generate_quick_write_exercises] Using provided {len(word_ids)} word IDs")

    from quick_write.quick_write_generator import QuickWriteGenerator

    try:
        # Encolar la generación de ejercicios
        task = QuickWriteGenerator.generate(target_user_id, word_ids, amount=10)
        logger.info(f"[generate_quick_write_exercises] Task enqueued: {task.id}")

        return {
            "status": "generating",
            "message": "Exercises are being generated",
            "task_id": task.id
        }
    except Exception as e:
        logger.error(f"[generate_quick_write_exercises] Error enqueuing generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generating exercises")


@router.patch("/{note_id}", response_model=QuickWriteResponse)
@log_endpoint
def update_quick_write(
    note_id: int = Path(..., ge=1),
    request: QuickWriteUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza un ejercicio con validación de idioma y revisión de gramática"""
    logger.info(f"[update_quick_write] User {current_user.id}: Updating exercise {note_id}")

    # Log de actividad
    UserActivityService.log_button_click(
        db=db,
        user_id=current_user.id,
        button_name="update_quick_write",
        details={
            "note_id": note_id
        }
    )

    repo = QuickWriteRepository(db)
    update_data = {}

    # Si se proporciona contenido original, validar idioma y revisar gramática
    if request.original_content is not None:
        if not request.original_content.strip():
            raise HTTPException(status_code=400, detail="Content cannot be empty")

        original_content = request.original_content.strip()

        # Validar que tenga al menos 5 palabras
        word_count = len(original_content.split())
        if word_count < 8:
            logger.warning(f"[update_quick_write] Text is too short: {word_count} words.")
            raise HTTPException(
                status_code=400,
                detail=f"Your response is too short."
            )

        # Validar que sea inglés - detectar una sola vez
        is_english = grammar.detect_english_regex(original_content)

        if not is_english:
            logger.warning(f"[update_quick_write] Text is not in English")
            raise HTTPException(
                status_code=400,
                detail=f"Text must be in English"
            )

        # Obtener el quick_write actual para acceder a las palabras
        note = repo.get(note_id, current_user.id)
        if not note:
            logger.warning(f"[update_quick_write] Exercise {note_id} not found")
            raise HTTPException(status_code=404, detail="Exercise not found")

        # Extraer las palabras target del quick_write
        target_words = note.words if note.words else []
        logger.debug(f"[update_quick_write] Target words: {target_words}")

        # Revisar gramática con palabras target
        if target_words:
            corrected_content = ai.correct_text_with_target_words(original_content, target_words)
            logger.debug(f"[update_quick_write] Used AI correction with target words")
        else:
            corrected_content = grammar.correct_text(original_content)
            logger.debug(f"[update_quick_write] Used grammar engine (no target words available)")

        has_corrections = original_content != corrected_content

        update_data["original_content"] = original_content
        update_data["corrected_content"] = corrected_content
        update_data["has_corrections"] = has_corrections

        logger.debug(f"[update_quick_write] Grammar check completed - has_corrections={has_corrections}")

    if request.is_favorite is not None:
        update_data["is_favorite"] = request.is_favorite

    note = repo.update(note_id, current_user.id, update_data)

    if not note:
        logger.warning(f"[update_quick_write] Exercise {note_id} not found")
        raise HTTPException(status_code=404, detail="Exercise not found")

    logger.debug(f"[update_quick_write] Exercise {note_id} updated")
    return QuickWriteResponse.model_validate(note)


@router.patch("/{note_id}/favorite")
@log_endpoint
def toggle_favorite_quick_write(
    note_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Activa/desactiva ejercicio como favorito"""
    logger.info(f"[toggle_favorite_quick_write] User {current_user.id}: Toggling favorite for exercise {note_id}")

    repo = QuickWriteRepository(db)
    note = repo.toggle_favorite(note_id, current_user.id)

    if not note:
        logger.warning(f"[toggle_favorite_quick_write] Exercise {note_id} not found")
        raise HTTPException(status_code=404, detail="Exercise not found")

    logger.debug(f"[toggle_favorite_quick_write] Exercise {note_id} favorite toggled to {note.is_favorite}")

    # Log de actividad
    UserActivityService.log_button_click(
        db=db,
        user_id=current_user.id,
        button_name="toggle_favorite_quick_write",
        details={
            "note_id": note_id,
            "is_favorite": note.is_favorite
        }
    )

    return {
        "id": note.id,
        "is_favorite": note.is_favorite
    }


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
@log_endpoint
def delete_quick_write(
    note_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Elimina un ejercicio"""
    logger.info(f"[delete_quick_write] User {current_user.id}: Deleting exercise {note_id}")

    repo = QuickWriteRepository(db)
    success = repo.delete(note_id, current_user.id)

    if not success:
        logger.warning(f"[delete_quick_write] Exercise {note_id} not found")
        raise HTTPException(status_code=404, detail="Exercise not found")

    logger.debug(f"[delete_quick_write] Exercise {note_id} deleted")

    # Log de actividad
    UserActivityService.log_button_click(
        db=db,
        user_id=current_user.id,
        button_name="delete_quick_write",
        details={"note_id": note_id}
    )
    return None


@router.post("/check-grammar")
@log_endpoint
def check_grammar(
    text: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user)
):
    """Revisa la gramática y detecta idioma del texto"""
    logger.info(f"[check_grammar] User {current_user.id}: Checking grammar")

    # Log de actividad
    UserActivityService.log_button_click(
        db=Session(bind=db.bind),
        user_id=current_user.id,
        button_name="check_grammar",
        details={"text_length": len(text) if text else 0}
    )

    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Detectar idioma - una sola vez
    detected_lang = grammar.detect_language(text)
    is_english = detected_lang == 'en'

    if not is_english:
        logger.warning(f"[check_grammar] Text is not in English (detected: {detected_lang})")
        return {
            "is_english": False,
            "detected_language": detected_lang,
            "errors": [],
            "message": f"Text is in {detected_lang}, not English"
        }

    # Revisar gramática
    errors = grammar.check_grammar(text)
    corrected = grammar.correct_text(text)

    logger.debug(f"[check_grammar] Found {len(errors)} grammar errors")

    return {
        "is_english": True,
        "detected_language": language,
        "original": text,
        "corrected": corrected,
        "errors": [
            {
                "message": error["message"],
                "offset": error["offset"],
                "length": error["length"],
                "replacements": error.get("replacements", [])
            }
            for error in errors
        ]
    }
