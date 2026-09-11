import csv
import io
import re
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
import os


router = APIRouter()


# Load bad words list at startup
def load_bad_words():
    """Carga la lista de palabras prohibidas desde bad_words.txt"""
    bad_words_path = os.path.join(os.path.dirname(__file__), "..", "bad_words.txt")
    try:
        with open(bad_words_path, 'r', encoding='utf-8') as f:
            # Convertir a lowercase para búsqueda case-insensitive
            return set(word.strip().lower() for word in f.readlines() if word.strip())
    except Exception as e:
        logger.warning(f"[load_bad_words] Error loading bad_words.txt: {e}")
        return set()


BAD_WORDS_SET = load_bad_words()


def contains_bad_words(text: str) -> tuple[bool, str]:
    """
    Verifica si el texto contiene palabras prohibidas.
    Solo detecta palabras completas (no substrings), usando límites de palabra.

    Retorna:
        (tiene_bad_words, palabra_encontrada)
    """
    text_lower = text.lower()

    # Búsqueda de palabras completas con límites de palabra
    for bad_word in BAD_WORDS_SET:
        # Usar \b para límites de palabra (no funciona con caracteres especiales)
        # Para palabras con caracteres especiales, hacer búsqueda literal
        if re.search(r'\b' + re.escape(bad_word) + r'\b', text_lower):
            return True, bad_word

    return False, ""


@router.get("/words", response_model=dict)
@log_endpoint
def get_words(
    sort: str = "newest",
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    learning_state: str = Query(None),
    is_favorite: bool = Query(False),
    search: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene las palabras del usuario con paginación y ordenamiento.

    sort: newest, oldest, alphabetical
    learning_state: None (all), new, learning (in progress), mastered (learned)
    is_favorite: True para traer solo favoritas, False para traer todas
    """
    logger.info(f"[get_words] User {current_user.id}: Fetching words (sort={sort}, page={page}, limit={limit}, learning_state={learning_state}, is_favorite={is_favorite}, search={search})")

    word_repo = WordRepository(db)
    paginated_data = word_repo.get_words(
        user_id=current_user.id,
        sort=sort,
        page=page,
        limit=limit,
        learning_state=learning_state,
        is_favorite=is_favorite,
        search=search
    )

    logger.debug(f"[get_words] Retrieved {len(paginated_data['items'])} words")

    # Contar total de palabras favoritas del usuario
    total_favorites = word_repo.get_total_favorites(current_user.id)
    paginated_data["total_favorites"] = total_favorites

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


@router.get("/random", response_model=dict)
@log_endpoint
def get_random_words(
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene palabras aleatorias del usuario"""
    logger.info(f"[get_random_words] User {current_user.id}: Fetching {limit} random words")

    word_repo = WordRepository(db)
    random_words = word_repo.get_random_words(current_user.id, limit)

    items = [
        {
            "id": w.id,
            "main": TextFormatter.capitalize(w.main),
            "meaning": TextFormatter.capitalize(w.meaning),
            "type": w.type,
            "frequency": w.frequency,
            "level": w.level,
        }
        for w in random_words
    ]

    logger.debug(f"[get_random_words] Retrieved {len(items)} random words")

    return {
        "items": items,
        "total": len(items)
    }


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
        "examples": initial_examples,
        "explanation": word.explanation
    }


@router.post("/single", response_model=dict)
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

    Respuesta:
    - status: "existing" - palabra ya existe, retorna detalles completos
    - status: "queued" - nueva palabra, task encolada en background
    - status: "error" - error en validación

    Flujo para palabra nueva:
    1. Recibir texto libre
    2. Disparar task Celery en background (no espera)
    3. Retornar task_id inmediatamente
    4. Task Celery: extrae info con AI, crea palabra, genera ejemplos
    """

    logger.info(f"[create_single_word] User {current_user.id}: Processing word creation")
    logger.debug(f"[create_single_word] Text: {request_data.text}")

    text = request_data.text.strip()

    if not text:
        logger.warning(f"[create_single_word] Empty text provided")
        return {
            "status": "error",
            "message": "El campo 'text' no puede estar vacío"
        }

    # Validar que no contenga palabras prohibidas
    has_bad_words, bad_word = contains_bad_words(text)
    if has_bad_words:
        logger.warning(f"[create_single_word] Text contains bad word: {bad_word}")
        return {
            "status": "error",
            "message": "Cannot add this word. It contains inappropriate content."
        }

    try:
        # Extraer palabra del texto
        extracted = ai.extract_learning_intent([text])

        if not extracted or len(extracted) == 0:
            logger.warning(f"[create_single_word] Could not extract word from text for user {current_user.id}")
            return {
                "status": "error",
                "message": "No pudimos extraer una palabra del texto proporcionado"
            }

        main_word = extracted[0].get("main")

        if not main_word:
            logger.warning(f"[create_single_word] No main word extracted for user {current_user.id}")
            return {
                "status": "error",
                "message": "No pudimos extraer una palabra del texto proporcionado"
            }

        # Verificar si la palabra ya existe
        word_repo = WordRepository(db)
        existing_word = word_repo.get_by_main_word(current_user.id, main_word)

        if existing_word:
            logger.info(f"[create_single_word] Word '{main_word}' already exists for user {current_user.id}")

            # Retornar detalles de la palabra existente
            explore_examples_count = word_repo.get_explore_examples_count(existing_word.id)
            initial_examples = word_repo.get_initial_examples(existing_word.id)
            is_learned = word_repo.is_learned(existing_word.id, ContentType.EXAMPLE)

            return {
                "status": "existing",
                "message": "Esta palabra ya existe en tu lista",
                "word": {
                    "id": existing_word.id,
                    "main": TextFormatter.capitalize(existing_word.main),
                    "meaning": TextFormatter.capitalize(existing_word.meaning),
                    "synonyms": TextFormatter.capitalize(existing_word.synonyms),
                    "type": existing_word.type,
                    "frequency": existing_word.frequency,
                    "level": WordLevel.to_str(existing_word.level),
                    "context": TextFormatter.capitalize(existing_word.context),
                    "source_text": existing_word.source_text,
                    "is_favorite": existing_word.is_favorite,
                    "is_learned": is_learned,
                    "created_at": existing_word.created_at,
                    "total_examples": explore_examples_count,
                    "examples": initial_examples
                }
            }

        # Palabra no existe, enqueue task
        task = WordGenerator.create_single(current_user.id, text)

        logger.info(f"[create_single_word] Task {task.id} queued for user {current_user.id}")

        return {
            "status": "queued",
            "task_id": str(task.id),
            "message": "Creación de palabra iniciada en background. Los ejemplos se generarán automáticamente."
        }

    except Exception as e:
        logger.error(f"[create_single_word] Error processing word: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error al procesar la palabra: {str(e)}"
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
def toggle_learned_status(
    word_id: int = Path(..., ge=1),
    request_data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Toggle learned status para una palabra.

    Body esperado:
    {
        "is_learned": true/false
    }
    """
    logger.info(f"[toggle_learned_status] User {current_user.id}: Toggling learned status for word {word_id}")

    word_repo = WordRepository(db)
    word = word_repo.get(db, word_id)

    if not word or word.user_id != current_user.id:
        logger.warning(f"[toggle_learned_status] Word {word_id} not found")
        raise HTTPException(status_code=404, detail="Palabra no encontrada")

    is_learned_target = request_data.get("is_learned", True)

    if is_learned_target:
        # Marcar como aprendida
        success = word_repo.mark_as_learned(word_id)
        if not success:
            logger.warning(f"[toggle_learned_status] No statistics found for word {word_id}")
            return {"status": "warning", "message": "No statistics to update", "is_learned": False}
        logger.debug(f"[toggle_learned_status] Word {word_id} marked as learned")
    else:
        # Desmarcar como aprendida (cambiar learning_state de LEARNED a REINFORCING)
        success = word_repo.mark_as_not_learned(word_id)
        if not success:
            logger.warning(f"[toggle_learned_status] Could not update statistics for word {word_id}")
            return {"status": "warning", "message": "Could not update status", "is_learned": True}
        logger.debug(f"[toggle_learned_status] Word {word_id} marked as not learned")

    # Verificar el estado actualizado
    is_learned = word_repo.is_learned(word_id, ContentType.EXAMPLE)

    return {
        "status": "ok",
        "message": "Learned status updated",
        "word_id": word_id,
        "is_learned": is_learned
    }


@router.post("/words/{word_id}/explain")
@log_endpoint
def explain_word_endpoint(
    word_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Genera y almacena explicación de una palabra"""
    logger.info(f"[explain_word_endpoint] User {current_user.id}: Explaining word {word_id}")

    word_repo = WordRepository(db)
    word = word_repo.get(db, word_id)

    if not word or word.user_id != current_user.id:
        logger.warning(f"[explain_word_endpoint] Word {word_id} not found")
        raise HTTPException(status_code=404, detail="Palabra no encontrada")

    try:
        # Generar explicación usando AI
        explanation_json = ai.explain_vocabulary(word.main)

        # Parsear JSON response
        import json
        explanation_data = json.loads(explanation_json)
        explanation_text = explanation_data.get("explanation", "")

        # Almacenar en la palabra
        word.explanation = explanation_text
        db.add(word)
        db.commit()
        db.refresh(word)

        logger.info(f"[explain_word_endpoint] Word {word_id} explanation generated and stored")

        return {
            "status": "ok",
            "word_id": word_id,
            "explanation": explanation_text
        }

    except Exception as e:
        logger.error(f"[explain_word_endpoint] Error generating explanation for word {word_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating explanation: {str(e)}")


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
