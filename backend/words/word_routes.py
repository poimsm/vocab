import csv
import io
from typing import List
from logging_client import logger
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from db import get_db
from models import WordLevel, User, ContentType
from helpers import TextFormatter
from auth.repository import get_current_user
from datetime import datetime, timezone
from words.word_schemas import WordListItem, WordDetail, CreateWordRequest, CreateWordFromTextRequest
from decorators import log_endpoint
from words.word_repository import WordRepository
from words.word_generator import WordGenerator
import ai


router = APIRouter()


@router.get("/words", response_model=dict)
@log_endpoint
def get_words(
    sort: str = "newest",
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    learning_state: str = Query(None),
    is_favorite: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene las palabras del usuario con paginación y ordenamiento.

    sort: newest, oldest, alphabetical
    learning_state: None (all), new, learning (in progress), mastered (learned)
    is_favorite: True para traer solo favoritas, False para traer todas
    """
    logger.info(f"[get_words] User {current_user.id}: Fetching words (sort={sort}, page={page}, limit={limit}, learning_state={learning_state}, is_favorite={is_favorite})")

    word_repo = WordRepository(db)
    paginated_data = word_repo.get_words(
        user_id=current_user.id,
        sort=sort,
        page=page,
        limit=limit,
        learning_state=learning_state,
        is_favorite=is_favorite
    )

    logger.debug(f"[get_words] Retrieved {len(paginated_data['items'])} words")

    # Transformar palabras para respuesta
    paginated_data["items"] = [
        {
            "id": w.id,
            "main": TextFormatter.capitalize(w.main),
            "meaning": TextFormatter.capitalize(w.meaning),
            "synonyms": TextFormatter.capitalize(w.synonyms),
            "type": w.type,
            "frequency": w.frequency,
            "level": WordLevel.to_str(w.level),
            "context": TextFormatter.capitalize(w.context),
            "is_favorite": w.is_favorite,
            "is_learned": word_repo.is_learned(w.id, ContentType.EXAMPLE),
            "total_examples": total_examples
        }
        for w, total_examples in paginated_data["items"]
    ]

    return paginated_data


@router.get("/words/{word_id}", response_model=WordDetail)
@log_endpoint
def get_word(
    word_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene detalles completos de una palabra"""
    logger.debug(f"[get_word] User {current_user.id}: Fetching word {word_id}")

    word_repo = WordRepository(db)
    word = word_repo.get(db, word_id)

    if not word or word.user_id != current_user.id:
        logger.warning(f"[get_word] Word {word_id} not found")
        raise HTTPException(status_code=404, detail="Palabra no encontrada")

    explore_examples_count = word_repo.get_explore_examples_count(word_id)
    initial_examples = word_repo.get_initial_examples(word_id)
    is_learned = word_repo.is_learned(word_id, ContentType.EXAMPLE)

    return {
        "id": word.id,
        "main": TextFormatter.capitalize(word.main),
        "meaning": TextFormatter.capitalize(word.meaning),
        "synonyms": TextFormatter.capitalize(word.synonyms),
        "type": word.type,
        "frequency": word.frequency,
        "level": WordLevel.to_str(word.level),
        "context": TextFormatter.capitalize(word.context),
        "source_text": word.source_text,
        "is_favorite": word.is_favorite,
        "is_learned": is_learned,
        "created_at": word.created_at,
        "total_examples": explore_examples_count,
        "examples": initial_examples
    }


@router.post("/single", status_code=status.HTTP_202_ACCEPTED, response_model=dict)
@log_endpoint
def create_single_word(
    request_data: CreateWordFromTextRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crea una palabra individual desde texto libre en background.

    La AI extrae automáticamente main, meaning, synonyms, etc.
    El proceso se ejecuta en background usando Celery.

    Body esperado:
    {
        "text": "Texto libre donde aparece la palabra a aprender"
    }

    Flujo:
    1. Recibir texto libre
    2. Disparar task Celery en background (no espera)
    3. Retornar task_id inmediatamente
    4. Task Celery: extrae info con AI, crea palabra, genera ejemplos
    """

    logger.info(f"[create_single_word] User {current_user.id}: Queuing word creation")
    logger.debug(f"[create_single_word] Text: {request_data.text}")

    text = request_data.text.strip()

    if not text:
        logger.warning(f"[create_single_word] Empty text provided")
        return {
            "status": "error",
            "message": "El campo 'text' no puede estar vacío"
        }

    try:
        # Disparar task Celery en background (retorna inmediatamente)
        task = WordGenerator.create_single(current_user.id, text)

        logger.info(f"[create_single_word] Task {task.id} queued for user {current_user.id}")

        return {
            "status": "queued",
            "task_id": str(task.id),
            "message": "Creación de palabra iniciada en background. Los ejemplos se generarán automáticamente."
        }

    except Exception as e:
        logger.error(f"[create_single_word] Error queuing task: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error al encolar la tarea: {str(e)}"
        }


@router.post("/bulk", status_code=status.HTTP_202_ACCEPTED)
@log_endpoint
def create_words_bulk(
    texts: List[str] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crea múltiples palabras desde una lista de textos.

    Procesa sequencialmente en background.

    Flujo:
    1. Validar textos
    2. Disparar task en Celery
    3. Retornar status inmediatamente

    Body esperado (array directo):
    ["texto 1", "texto 2", ...]
    """
    from words.word_generator import WordGenerator

    logger.info(f"[create_words_bulk] User {current_user.id}: Creating {len(texts)} words")

    if not texts:
        logger.warning(f"[create_words_bulk] No texts provided")
        return {
            "status": "error",
            "message": "Se requiere al menos un texto en el campo 'texts'"
        }

    # Validar que no haya textos vacíos
    valid_texts = [t.strip() for t in texts if isinstance(t, str) and t and t.strip()]

    if not valid_texts:
        logger.warning(f"[create_words_bulk] All texts were empty")
        return {
            "status": "error",
            "message": "Se requiere al menos un texto válido"
        }

    # Trigger word_generator para procesar en background
    task = WordGenerator.create_bulk(current_user.id, valid_texts)

    logger.info(f"[create_words_bulk] Task {task.id} queued for user {current_user.id}")

    return {
        "status": "queued",
        "task_id": str(task.id),
        "message": f"Processing {len(valid_texts)} texts sequentially in background."
    }


@router.patch("/words/{word_id}", response_model=WordDetail)
@log_endpoint
def update_word(
    word_id: int = Path(..., ge=1),
    request_data: CreateWordRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza una palabra existente"""
    logger.info(f"[update_word] User {current_user.id}: Updating word {word_id}")

    word_repo = WordRepository(db)
    word = word_repo.get(db, word_id)

    if not word or word.user_id != current_user.id:
        logger.warning(f"[update_word] Word {word_id} not found")
        raise HTTPException(status_code=404, detail="Palabra no encontrada")

    word_data = {
        "main": request_data.main,
        "meaning": request_data.meaning,
        "synonyms": request_data.synonyms,
        "type": request_data.type,
        "frequency": request_data.frequency,
        "level": request_data.level or word.level,
        "context": request_data.context,
    }

    updated_word = word_repo.update(word_id, word_data)
    logger.debug(f"[update_word] Word {word_id} updated")

    explore_examples_count = word_repo.get_explore_examples_count(word_id)
    initial_examples = word_repo.get_initial_examples(word_id)
    is_learned = word_repo.is_learned(word_id, ContentType.EXAMPLE)

    return {
        "id": updated_word.id,
        "main": TextFormatter.capitalize(updated_word.main),
        "meaning": TextFormatter.capitalize(updated_word.meaning),
        "synonyms": TextFormatter.capitalize(updated_word.synonyms),
        "type": updated_word.type,
        "frequency": updated_word.frequency,
        "level": WordLevel.to_str(updated_word.level),
        "context": TextFormatter.capitalize(updated_word.context),
        "source_text": updated_word.source_text,
        "is_favorite": updated_word.is_favorite,
        "is_learned": is_learned,
        "created_at": updated_word.created_at,
        "total_examples": explore_examples_count,
        "examples": initial_examples
    }


@router.patch("/words/{word_id}/favorite")
@log_endpoint
def toggle_favorite(
    word_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Activa/desactiva palabra como favorita"""
    logger.info(f"[toggle_favorite] User {current_user.id}: Toggling favorite for word {word_id}")

    word_repo = WordRepository(db)
    word = word_repo.get(db, word_id)

    if not word or word.user_id != current_user.id:
        logger.warning(f"[toggle_favorite] Word {word_id} not found")
        raise HTTPException(status_code=404, detail="Palabra no encontrada")

    updated_word = word_repo.toggle_favorite(word_id)
    logger.debug(f"[toggle_favorite] Word {word_id} favorite toggled to {updated_word.is_favorite}")

    return {
        "id": updated_word.id,
        "is_favorite": updated_word.is_favorite
    }


@router.patch("/words/{word_id}/learned")
@log_endpoint
def mark_word_as_learned(
    word_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Marca una palabra como aprendida"""
    logger.info(f"[mark_word_as_learned] User {current_user.id}: Marking word {word_id} as learned")

    word_repo = WordRepository(db)
    word = word_repo.get(db, word_id)

    if not word or word.user_id != current_user.id:
        logger.warning(f"[mark_word_as_learned] Word {word_id} not found")
        raise HTTPException(status_code=404, detail="Palabra no encontrada")

    success = word_repo.mark_as_learned(word_id)

    if not success:
        logger.warning(f"[mark_word_as_learned] No statistics found for word {word_id}")
        return {"status": "warning", "message": "No statistics to update"}

    logger.debug(f"[mark_word_as_learned] Word {word_id} marked as learned")

    return {
        "status": "ok",
        "message": "Palabra marcada como aprendida",
        "word_id": word_id
    }


@router.delete("/words/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
@log_endpoint
def delete_word(
    word_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Elimina una palabra (soft delete)"""
    logger.info(f"[delete_word] User {current_user.id}: Deleting word {word_id}")

    word_repo = WordRepository(db)
    word = word_repo.get(db, word_id)

    if not word or word.user_id != current_user.id:
        logger.warning(f"[delete_word] Word {word_id} not found")
        raise HTTPException(status_code=404, detail="Palabra no encontrada")

    word_repo.delete(word_id)
    logger.debug(f"[delete_word] Word {word_id} deleted")

    return None


@router.get("/words/export/csv")
@log_endpoint
def export_words_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Exporta las palabras del usuario como CSV"""
    logger.info(f"[export_words_csv] User {current_user.id}: Exporting words")

    word_repo = WordRepository(db)
    paginated_data = word_repo.get_words(user_id=current_user.id, limit=10000)
    words = [w for w, _ in paginated_data["items"]]

    # Crear CSV en memoria
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["Word", "Meaning", "Type", "Frequency", "Level", "Context", "Favorite", "Learned"])

    # Rows
    for word in words:
        is_learned = word_repo.is_learned(word.id, ContentType.EXAMPLE)
        writer.writerow([
            word.main,
            word.meaning or "",
            word.type or "",
            word.frequency or "",
            WordLevel.to_str(word.level),
            word.context or "",
            "Yes" if word.is_favorite else "No",
            "Yes" if is_learned else "No"
        ])

    # Crear stream de respuesta
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=words.csv"}
    )
