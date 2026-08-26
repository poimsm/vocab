
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional, List
from pydantic import BaseModel
import re
from pathlib import Path

from db import get_db
from logging_client import logger
from auth.repository import get_current_user
from models import User, ContentType, ContentQueue, Example
from decorators import log_endpoint
from examples.example_schemas import ExploreResponse, ExploreExample, FavoritesResponse
from learning_path.content_queue import ContentQueue as ContentQueueManager
from learning_path.learning_tracker import LearningTracker
from examples.example_repository import ExampleRepository
from best_options.best_options_repository import BestOptionRepository


class ExploreRequest(BaseModel):
    """Request para el endpoint de explore con acciones encadenables."""
    actions: List[str] = ["next"]  # Acciones a ejecutar: ["resolve", "next"], ["next"], etc.
    resolve_queue_item_id: Optional[int] = None  # Requerido si actions incluye "resolve"
    limit: int = 5  # Para la acción "next"


router = APIRouter()


# ==================== Acciones Auxiliares ====================

def _action_resolve(
    db: Session,
    queue_item_id: int,
    current_user: User,
) -> bool:
    """
    Acción: Resolver un item (registrar exposición + marcar CONSUMED).

    Retorna True si fue exitoso, False si el item no existe.
    """
    logger.debug(f"[_action_resolve] Resolving queue_item_id={queue_item_id}")

    # Obtener con FOR UPDATE para bloquear la fila
    queue_item = db.exec(
        select(ContentQueue)
        .where(ContentQueue.id == queue_item_id)
        .with_for_update()
    ).first()

    if not queue_item or queue_item.user_id != current_user.id:
        logger.warning(f"[_action_resolve] Queue item {queue_item_id} not found or unauthorized")
        return False

    # Registrar exposición
    example_repo = ExampleRepository(db)
    best_option_repo = BestOptionRepository(db)
    tracker = LearningTracker(db, example_repo, best_option_repo)

    tracker.record_exposure(
        user_id=current_user.id,
        content_type=queue_item.type,
        content_id=queue_item.content_id,
    )

    # Marcar como consumido
    queue_mgr = ContentQueueManager(db)
    queue_mgr.consume(queue_item_id)

    logger.debug(f"[_action_resolve] Successfully resolved queue_item_id={queue_item_id}")
    return True


def _action_next(
    db: Session,
    current_user: User,
    limit: int,
) -> tuple[list, str]:
    """
    Acción: Obtener los siguientes items de la cola.

    Retorna (ejemplos_segmentados, status).
    Status puede ser: "ok", "generating", "no_words"
    """
    logger.debug(f"[_action_next] Fetching next {limit} examples")

    queue_mgr = ContentQueueManager(db)

    # Obtener items pendientes
    queue_items = queue_mgr.next_many(
        user_id=current_user.id,
        content_type=ContentType.EXAMPLE,
        amount=limit,
    )

    logger.debug(f"[_action_next] Got {len(queue_items)} items from queue")

    if not queue_items:
        logger.debug(f"[_action_next] No pending items, checking if content generation is needed")

        # Inicializar componentes para planificación
        from learning_path.content_planner import ContentPlanner
        from learning_path.priority_engine import PriorityEngine
        from words.word_repository import WordRepository

        priority_engine = PriorityEngine()
        word_repo = WordRepository(db)
        best_option_repo = BestOptionRepository(db)
        example_repo = ExampleRepository(db)

        content_planner = ContentPlanner(
            session=db,
            priority_engine=priority_engine,
            content_queue=queue_mgr,
            word_repository=word_repo,
            example_repository=example_repo,
            best_option_repository=best_option_repo,
        )

        # Chequear si hay palabras NO LEARNED
        has_words = content_planner.has_non_learned_words(current_user.id, ContentType.EXAMPLE)

        if not has_words:
            logger.info(f"[_action_next] User {current_user.id} has no non-LEARNED words")
            return [], "no_words"

        # Trigger generation
        content_planner.ensure_ready(current_user.id, ContentType.EXAMPLE)
        logger.debug(f"[_action_next] Content generation triggered")

        return [], "generating"

    # Segmentar ejemplos
    example_ids = [item.content_id for item in queue_items]
    examples = db.exec(
        select(Example).where(Example.id.in_(example_ids))
    ).all()

    logger.debug(f"[_action_next] Retrieved {len(examples)} example records")

    example_repo = ExampleRepository(db)
    examples_response = []
    example_to_queue = {item.content_id: item.id for item in queue_items}
    common_words = _load_common_words()

    for ex in examples:
        text_segments = example_repo.segment_example_text(ex)
        target_word_ids = {seg['target_word']['id'] for seg in text_segments if seg.get('target_word')}
        target_word_strings = {seg['target_word']['main'].lower() for seg in text_segments if seg.get('target_word')}

        extracted_words = _extract_words_from_example(text_segments, target_word_ids, common_words)
        extracted_words = [w for w in extracted_words if w not in target_word_strings]

        examples_response.append({
            "queue_item_id": example_to_queue[ex.id],
            "example_id": ex.id,
            "text": text_segments,
            "extracted_words": extracted_words,
            "is_favorite": ex.is_favorite,
        })

    return examples_response, "ok"


# ==================== Funciones Auxiliares ====================

def _load_common_words():
    """Carga el set de palabras comunes desde most_common.txt"""
    common_words_path = Path(__file__).parent.parent / "most_common.txt"
    if not common_words_path.exists():
        return set()

    with open(common_words_path, 'r', encoding='utf-8') as f:
        return {word.strip().lower() for word in f.readlines() if word.strip()}


def _extract_words_from_example(text_segments, target_word_ids, common_words):
    """
    Extrae palabras del ejemplo, excluyendo:
    - Palabras comunes (de most_common.txt)
    - Palabras de una sola letra
    - Contracciones (ej: didn't, couldn't)

    Normaliza posesivos (ej: team's → team, comedian's → comedian)

    Args:
        text_segments: Lista de TextSegment del ejemplo
        target_word_ids: Set de IDs de palabras que son target words en este ejemplo
        common_words: Set de palabras comunes (lowercased)

    Returns:
        Lista de palabras extraídas únicas
    """
    # Construir el texto completo del ejemplo
    full_text = ''.join(segment['text'] for segment in text_segments)

    # Extraer palabras: captura palabras simples y palabras con apóstrofos (contracciones/posesivos)
    # Pattern: una o más letras, opcionalmente seguidas de apóstrofo+letras
    words = re.findall(r"[a-z]+(?:'[a-z]+)?", full_text.lower())

    extracted = set()
    for word in words:
        if not word:  # Ignorar strings vacíos
            continue

        # Excluir contracciones completas que están en common_words (ej: didn't)
        if word in common_words:
            continue

        # Remover 's al final (normalizar posesivos: team's → team, comedian's → comedian)
        normalized = re.sub(r"'s$", "", word)

        # Remover apóstrofos restantes
        normalized = normalized.replace("'", "")

        # No extraer palabras de una sola letra
        if len(normalized) <= 1:
            continue

        # Excluir palabras comunes (versión normalizada)
        if normalized in common_words:
            continue

        extracted.add(normalized)

    return sorted(list(extracted))


@router.post("/explore", response_model=ExploreResponse)
@log_endpoint
def explore_examples(
    request: ExploreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint unificado con acciones encadenables.

    Body:
    {
      "actions": ["resolve", "next"],  // Acciones a ejecutar en orden
      "resolve_queue_item_id": 47,      // Requerido si actions contiene "resolve"
      "limit": 5                        // Para acción "next"
    }

    Ejemplos:
    - {"actions": ["next"], "limit": 5}
      → Solo obtener 5 ejemplos

    - {"actions": ["resolve", "next"], "resolve_queue_item_id": 47, "limit": 4}
      → Resolver item 47, luego obtener 4 ejemplos

    - {"actions": ["resolve"], "resolve_queue_item_id": 47}
      → Solo resolver item 47, no obtener nuevos

    TODO ATÓMICO - una sola transacción.
    """
    logger.info(
        f"[explore_examples] User {current_user.id}: actions={request.actions}, "
        f"resolve_id={request.resolve_queue_item_id}, limit={request.limit}"
    )

    examples = []
    status = "ok"

    # Ejecutar acciones en orden
    for action in request.actions:
        if action == "resolve":
            if request.resolve_queue_item_id is None:
                logger.warning(f"[explore_examples] Action 'resolve' requires resolve_queue_item_id")
                raise HTTPException(
                    status_code=400,
                    detail="Action 'resolve' requires resolve_queue_item_id parameter"
                )

            success = _action_resolve(db, request.resolve_queue_item_id, current_user)
            if not success:
                logger.warning(f"[explore_examples] Action 'resolve' failed for item {request.resolve_queue_item_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Item to resolve not found"
                )

        elif action == "next":
            examples, status = _action_next(db, current_user, request.limit)

        else:
            logger.warning(f"[explore_examples] Unknown action: {action}")
            raise HTTPException(
                status_code=400,
                detail=f"Unknown action: {action}. Valid actions: 'resolve', 'next'"
            )

    logger.info(f"[explore_examples] Completed with status={status}, returned {len(examples)} examples")

    return {
        "examples": examples,
        "status": status,
    }



@router.patch("/{example_id}/toggle-favorite")
@log_endpoint
def toggle_example_favorite(
    example_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Alterna el estado de favorito de un ejemplo.

    Retorna el nuevo estado de is_favorite.
    """
    logger.info(f"[toggle_example_favorite] User {current_user.id}: Toggling favorite for example {example_id}")

    example_repo = ExampleRepository(db)
    is_favorite = example_repo.toggle_favorite(example_id)

    logger.debug(f"[toggle_example_favorite] Example {example_id} is_favorite: {is_favorite}")

    return {
        "example_id": example_id,
        "is_favorite": is_favorite
    }


@router.get("/favorites", response_model=FavoritesResponse)
@log_endpoint
def get_favorite_examples(
    page: int = 1,
    limit: int = 15,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene ejemplos marcados como favoritos con paginación.

    Retorna:
    - items: Lista de ejemplos favoritos con texto segmentado
    - total: Total de ejemplos favoritos
    - page: Página actual
    - limit: Items por página
    - pages: Total de páginas
    - status: "ok"
    """
    logger.info(f"[get_favorite_examples] User {current_user.id}: Fetching favorite examples (page={page}, limit={limit})")

    example_repo = ExampleRepository(db)
    paginated_data = example_repo.get_examples(page=page, limit=limit)

    # Segmentar el texto de cada ejemplo
    examples_response = []
    for example in paginated_data["items"]:
        text_segments = example_repo.segment_example_text(example)
        extracted_words = []  # Por ahora vacío, se puede implementar después
        examples_response.append({
            "id": example.id,
            "text": text_segments,
            "extracted_words": extracted_words,
            "is_favorite": example.is_favorite
        })

    logger.debug(f"[get_favorite_examples] Retrieved {len(examples_response)} favorite examples")

    return {
        "items": examples_response,
        "total": paginated_data["total"],
        "page": paginated_data["page"],
        "limit": paginated_data["limit"],
        "pages": paginated_data["pages"],
        "status": "ok"
    }

