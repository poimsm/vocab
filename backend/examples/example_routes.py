
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
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


router = APIRouter()


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
    - Palabras que son target words

    Args:
        text_segments: Lista de TextSegment del ejemplo
        target_word_ids: Set de IDs de palabras que son target words en este ejemplo
        common_words: Set de palabras comunes (lowercased)

    Returns:
        Lista de palabras extraídas únicas
    """
    # Construir el texto completo del ejemplo
    full_text = ''.join(segment['text'] for segment in text_segments)

    # Extraer palabras (lowercase, sin puntuación)
    words = re.findall(r'\b[a-z]+\b', full_text.lower())

    extracted = set()
    for word in words:
        # Excluir palabras comunes
        if word in common_words:
            continue

        # Excluir palabras que estén resaltadas (target words)
        # Esto se filtra por los datos en text_segments
        extracted.add(word)

    return sorted(list(extracted))


@router.get("/explore", response_model=ExploreResponse)
@log_endpoint
def get_explore_feed(
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene los siguientes examples de la ContentQueue.

    Flujo:
    1. Obtener items PENDING de ContentQueue
    2. Si no hay, trigger ensure_ready() y retornar status "generating"
    3. Si hay, segmentar el texto en chunks con target words resaltados
    4. Retornar con estructura de texto segmentado y status "ok"
    """
    from learning_path.content_planner import ContentPlanner
    from learning_path.priority_engine import PriorityEngine
    from words.word_repository import WordRepository
    from best_options.best_options_repository import BestOptionRepository

    logger.info(f"[get_explore_feed] User {current_user.id}: Fetching examples (limit={limit})")

    queue_mgr = ContentQueueManager(db)

    # Obtener items pendientes (con filtrado de LEARNED items)
    queue_items = queue_mgr.next_many(
        user_id=current_user.id,
        content_type=ContentType.EXAMPLE,
        amount=limit,
    )

    logger.debug(f"[get_explore_feed] next_many returned {len(queue_items)} valid items (filtered out LEARNED examples)")

    if not queue_items:
        logger.debug(f"[get_explore_feed] No pending examples for user {current_user.id}")
        # Si no hay contenido, asegurar que hay suficiente
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
        content_planner.ensure_ready(current_user.id, ContentType.EXAMPLE)

        # Verificar si después de ensure_ready hay contenido pendiente
        pending_count = queue_mgr.count_pending(current_user.id, ContentType.EXAMPLE)

        # Determinar status
        if pending_count > 0:
            status = "generating"
        else:
            # Si no hay contenido pendiente, chequear si hay palabras candidatas
            candidates = content_planner.get_candidate_words(current_user.id, ContentType.EXAMPLE)
            status = "generating" if candidates else "no_words"

        logger.debug(
            f"[get_explore_feed] After ensure_ready: pending_count={pending_count}, candidates={len(candidates) if pending_count == 0 else 'N/A'}, status={status}"
        )

        return {
            "examples": [],
            "status": status,
        }

    # Obtener los examples asociados
    example_ids = [item.content_id for item in queue_items]
    examples = db.exec(
        select(Example).where(Example.id.in_(example_ids))
    ).all()

    logger.debug(f"[get_explore_feed] Retrieved {len(examples)} examples")

    # Segmentar el texto de cada ejemplo
    example_repo = ExampleRepository(db)
    examples_response = []

    # Crear un mapa de example_id -> queue_item_id
    example_to_queue = {item.content_id: item.id for item in queue_items}

    # Cargar palabras comunes una sola vez
    common_words = _load_common_words()

    for ex in examples:
        text_segments = example_repo.segment_example_text(ex)

        # Obtener los IDs de palabras que son target words en este ejemplo
        target_word_ids = {seg['target_word']['id'] for seg in text_segments if seg.get('target_word')}
        # También obtener los strings de palabras target para excluir
        target_word_strings = {seg['target_word']['main'].lower() for seg in text_segments if seg.get('target_word')}

        # Extraer palabras del ejemplo
        extracted_words = _extract_words_from_example(text_segments, target_word_ids, common_words)
        # Filtrar palabras que sean target words
        extracted_words = [w for w in extracted_words if w not in target_word_strings]

        examples_response.append(
            {
                "queue_item_id": example_to_queue[ex.id],
                "example_id": ex.id,
                "text": text_segments,
                "extracted_words": extracted_words,
                "is_favorite": ex.is_favorite,
            }
        )

    # Status: ok si hay ejemplos, generating si se activó ensure_ready, no_words si nada disponible
    status = "ok" if examples_response else "generating"

    return {
        "examples": examples_response,
        "status": status,
    }



@router.patch("/{queue_item_id}/resolve")
@log_endpoint
def resolve_queue_item(
    queue_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Marca un example como consumido y registra la exposición.

    Flujo:
    1. Obtener item de ContentQueue
    2. Llamar a LearningTracker.record_exposure()
    3. Marcar item como CONSUMED
    """

    logger.info(f"[resolve_queue_item] User {current_user.id}: Resolving queue item {queue_item_id}")

    # Obtener item
    queue_item = db.get(ContentQueue, queue_item_id)

    if not queue_item or queue_item.user_id != current_user.id:
        logger.warning(f"[resolve_queue_item] Queue item {queue_item_id} not found")
        raise HTTPException(status_code=404, detail="Item no encontrado")

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

    logger.debug(f"[resolve_queue_item] Queue item {queue_item_id} resolved")

    return {"status": "ok"}


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

