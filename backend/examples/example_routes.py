
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional, List
from pydantic import BaseModel
import re
import json
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
from examples.user_example_session_repository import UserExampleSessionRepository
from best_options.best_options_repository import BestOptionRepository


class ExploreRequest(BaseModel):
    """Request para el endpoint de explore con acciones encadenables."""
    actions: List[str] = ["next"]  # Acciones a ejecutar: ["resolve", "next"], ["next"], ["sync"], etc.
    resolve_queue_item_id: Optional[int] = None  # Requerido si actions incluye "resolve"
    limit: int = 5  # Para la acción "next"
    buffer_queue_item_ids: List[int] = []  # IDs actuales del buffer
    buffer_position: int = 0  # Posición actual en el buffer


router = APIRouter()


# ==================== Acciones Auxiliares ====================

def _is_queue_item_with_learned_word(
    db: Session,
    queue_item: ContentQueue,
    current_user: User,
) -> bool:
    """
    Chequea si un ContentQueue item tiene una palabra target que es LEARNED.
    Retorna True si el item debe ser descartado (palabra LEARNED).
    """
    example = db.exec(
        select(Example).where(Example.id == queue_item.content_id)
    ).first()

    if not example:
        return True  # Si no existe el ejemplo, descartar

    example_repo = ExampleRepository(db)
    text_segments = example_repo.segment_example_text(example)

    if text_segments:
        first_target = None
        for seg in text_segments:
            if seg.get('target_word'):
                first_target = seg['target_word']['id']
                break

        if first_target:
            from models import Word, WordStatistics, LearningState
            word_stats = db.exec(
                select(WordStatistics).join(Word).where(
                    WordStatistics.word_id == first_target,
                    WordStatistics.type == ContentType.EXAMPLE,
                    Word.user_id == current_user.id
                )
            ).first()

            if word_stats and word_stats.learning_state == LearningState.LEARNED:
                return True

    return False


def _validate_buffer_and_get_valid_ids(
    db: Session,
    buffer_queue_item_ids: List[int],
    current_user: User,
) -> List[int]:
    """
    Valida items en el buffer, removiendo aquellos con palabras LEARNED y duplicados.

    Retorna: valid_ids que pasaron validación (sin duplicados).
    """
    valid_ids = []
    seen_ids = set()

    for queue_id in buffer_queue_item_ids:
        # Evitar duplicados
        if queue_id in seen_ids:
            logger.debug(f"[_validate_buffer_and_get_valid_ids] Item {queue_id} is duplicate, skipping")
            continue

        queue_item = db.exec(
            select(ContentQueue).where(
                ContentQueue.id == queue_id,
                ContentQueue.user_id == current_user.id
            )
        ).first()

        if not queue_item:
            logger.debug(f"[_validate_buffer_and_get_valid_ids] Item {queue_id} not found")
            continue

        if _is_queue_item_with_learned_word(db, queue_item, current_user):
            logger.debug(f"[_validate_buffer_and_get_valid_ids] Item {queue_id} has LEARNED word, removing")
            continue

        valid_ids.append(queue_id)
        seen_ids.add(queue_id)

    return valid_ids


def _adjust_position_after_removals(
    buffer_queue_item_ids: List[int],
    valid_ids: List[int],
    buffer_position: int,
) -> int:
    """
    Calcula la nueva posición después de remover items del buffer.

    Args:
        buffer_queue_item_ids: IDs originales del buffer
        valid_ids: IDs que permanecen después de validación
        buffer_position: Posición original

    Retorna: Nueva posición ajustada
    """
    removed_before_position = 0
    for i, queue_id in enumerate(buffer_queue_item_ids):
        if i < buffer_position and queue_id not in valid_ids:
            removed_before_position += 1

    new_position = max(0, buffer_position - removed_before_position)

    if valid_ids:
        new_position = min(new_position, len(valid_ids) - 1)
    else:
        new_position = 0

    return new_position


def _refill_buffer_to_limit(
    db: Session,
    buffer_ids: List[int],
    limit: int,
    current_user: User,
) -> List[int]:
    """
    Refill buffer hasta alcanzar limit, validando nuevos items para remover LEARNED y evitando duplicados.

    Retorna lista de IDs del buffer rellenado (sin duplicados).
    """
    if len(buffer_ids) >= limit:
        return buffer_ids

    logger.debug(f"[_refill_buffer_to_limit] Buffer has {len(buffer_ids)}, need to fill to {limit}")

    queue_mgr = ContentQueueManager(db)
    final_ids = list(buffer_ids)
    buffer_ids_set = set(buffer_ids)  # Para búsquedas rápidas de duplicados

    while len(final_ids) < limit:
        amount_needed = limit - len(final_ids)
        additional_items = queue_mgr.next_many(
            user_id=current_user.id,
            content_type=ContentType.EXAMPLE,
            amount=amount_needed,
        )

        if not additional_items:
            logger.info(f"[_refill_buffer_to_limit] ContentQueue empty")
            break

        # Validar nuevos items: filtrar LEARNED y duplicados
        items_added = 0
        for item in additional_items:
            # Evitar duplicados: no agregar si ya está en el buffer
            if item.id in buffer_ids_set:
                logger.debug(f"[_refill_buffer_to_limit] Item {item.id} already in buffer, skipping")
                continue

            # Filtrar items con palabras LEARNED
            if not _is_queue_item_with_learned_word(db, item, current_user):
                final_ids.append(item.id)
                buffer_ids_set.add(item.id)
                items_added += 1

        logger.debug(f"[_refill_buffer_to_limit] Added {items_added} valid items, buffer now has {len(final_ids)}")

        if items_added == 0:
            logger.info(f"[_refill_buffer_to_limit] All remaining items have LEARNED words or are duplicates")
            break

    return final_ids


def _build_examples_response(
    db: Session,
    buffer_queue_item_ids: List[int],
) -> list:
    """
    Convierte un buffer de queue items a respuesta de ejemplos segmentados.

    Retorna lista de ejemplos con text_segments, extracted_words, etc.
    """
    if not buffer_queue_item_ids:
        return []

    # Obtener ContentQueue items
    queue_items = db.exec(
        select(ContentQueue).where(ContentQueue.id.in_(buffer_queue_item_ids))
    ).all()

    queue_item_map = {item.id: item for item in queue_items}

    # Obtener ejemplos
    example_ids = [queue_item_map[qid].content_id for qid in buffer_queue_item_ids if qid in queue_item_map]
    examples = db.exec(
        select(Example).where(Example.id.in_(example_ids))
    ).all()

    example_repo = ExampleRepository(db)
    examples_response = []
    common_words = _load_common_words()

    # Mantener orden del buffer
    for queue_id in buffer_queue_item_ids:
        if queue_id not in queue_item_map:
            continue

        queue_item = queue_item_map[queue_id]
        ex = next((e for e in examples if e.id == queue_item.content_id), None)

        if not ex:
            continue

        text_segments = example_repo.segment_example_text(ex)
        target_word_ids = {seg['target_word']['id'] for seg in text_segments if seg.get('target_word')}
        target_word_strings = {seg['target_word']['main'].lower() for seg in text_segments if seg.get('target_word')}

        extracted_words = _extract_words_from_example(text_segments, target_word_ids, common_words)
        extracted_words = [w for w in extracted_words if w not in target_word_strings]

        examples_response.append({
            "queue_item_id": queue_id,
            "example_id": ex.id,
            "text": text_segments,
            "extracted_words": extracted_words,
            "is_favorite": ex.is_favorite,
            "is_marked": ex.is_marked,
        })

    return examples_response


def _validate_and_refill_buffer(
    db: Session,
    current_user: User,
    buffer_queue_item_ids: List[int],
    buffer_position: int,
    limit: int,
) -> tuple[List[int], int]:
    """
    Valida el buffer actual y lo refill si es necesario.

    1. Valida items - remueve aquellos con palabras LEARNED
    2. Ajusta position
    3. Refill hasta alcanzar limit

    Retorna: (nuevo_buffer_ids, nuevo_position)
    """
    logger.debug(
        f"[_validate_and_refill_buffer] Validating buffer: ids={buffer_queue_item_ids}, "
        f"position={buffer_position}, limit={limit}"
    )

    # Paso 1: Validar buffer
    valid_ids = _validate_buffer_and_get_valid_ids(db, buffer_queue_item_ids, current_user)

    # Paso 2: Ajustar posición
    new_position = _adjust_position_after_removals(buffer_queue_item_ids, valid_ids, buffer_position)

    logger.debug(
        f"[_validate_and_refill_buffer] After validation: valid_ids={valid_ids}, new_position={new_position}"
    )

    # Paso 3: Decidir si refill
    at_end_of_buffer = buffer_position >= len(valid_ids) - 1
    should_refill = len(valid_ids) < limit or (at_end_of_buffer and len(valid_ids) == limit)

    if should_refill:
        if at_end_of_buffer and len(valid_ids) == limit:
            logger.debug(f"[_validate_and_refill_buffer] At end of buffer, fetching new batch")
            valid_ids = []
            new_position = 0

        valid_ids = _refill_buffer_to_limit(db, valid_ids, limit, current_user)

    return valid_ids, new_position


def _action_resolve(
    db: Session,
    queue_item_id: int,
    current_user: User,
) -> bool:
    """
    Acción: Resolver un item (registrar exposición + marcar CONSUMED).
    Solo resuelve si el item no ha sido resuelto en esta sesión.

    Retorna True si fue exitoso, False si el item no existe o ya fue resuelto.
    """
    logger.debug(f"[_action_resolve] Attempting to resolve queue_item_id={queue_item_id}")

    # Chequear si ya fue resuelto en esta sesión
    session_repo = UserExampleSessionRepository(db)
    if session_repo.is_queue_item_resolved(current_user.id, queue_item_id):
        logger.debug(f"[_action_resolve] Item {queue_item_id} already resolved in this session, skipping")
        return True  # Ya fue resuelto, no error

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

    # Marcar en la sesión como resuelto Y visitado
    session_repo.mark_queue_item_as_resolved(current_user.id, queue_item_id)
    session_repo.mark_queue_item_as_visited(current_user.id, queue_item_id)

    logger.debug(f"[_action_resolve] Successfully resolved queue_item_id={queue_item_id}")
    return True


def _action_sync(
    db: Session,
    current_user: User,
    limit: int,
    buffer_queue_item_ids: List[int],
    buffer_position: int,
) -> tuple[List[int], int, str]:
    """
    Acción: Solo sincroniza la posición actual sin tocar el buffer.
    Usado cuando el usuario navega (next/prev) para actualizar la posición en el backend.

    Retorna (buffer_ids_sin_cambios, position_actualizada, "ok").
    """
    logger.info(
        f"[_action_sync] User {current_user.id}: Syncing position. Buffer={buffer_queue_item_ids}, "
        f"position={buffer_position}"
    )

    # Solo actualizar la posición en la sesión, sin tocar el buffer
    session_repo = UserExampleSessionRepository(db)
    session_repo.update_session(current_user.id, buffer_queue_item_ids, buffer_position)

    logger.info(f"[_action_sync] Position synced: position={buffer_position}")
    return buffer_queue_item_ids, buffer_position, "ok"


def _action_sync_buffer(
    db: Session,
    current_user: User,
    limit: int,
    buffer_queue_item_ids: List[int],
    buffer_position: int,
) -> tuple[List[int], int, str]:
    """
    Acción: Valida y refill el buffer de forma agresiva.
    Usado desde WordDetailPage cuando se marca palabra como learned.

    Pasos:
    1. Remover todos los items con palabras LEARNED
    2. Calcular nueva posición
    3. Llenar con nuevos items desde ContentQueue hasta completar limit

    Retorna (nuevo_buffer_ids, nueva_position, status).
    """
    logger.info(
        f"[_action_sync_buffer] User {current_user.id}: Aggressive sync-buffer with ids={buffer_queue_item_ids}, "
        f"position={buffer_position}"
    )

    # Validar y remover items LEARNED
    valid_ids = _validate_buffer_and_get_valid_ids(db, buffer_queue_item_ids, current_user)
    logger.debug(f"[_action_sync_buffer] After removal: {len(valid_ids)} items remain")

    # Calcular nueva posición
    new_position = _adjust_position_after_removals(buffer_queue_item_ids, valid_ids, buffer_position)
    logger.debug(f"[_action_sync_buffer] Position adjusted: {buffer_position} → {new_position}")

    # Refill buffer
    valid_ids = _refill_buffer_to_limit(db, valid_ids, limit, current_user)

    logger.info(
        f"[_action_sync_buffer] Buffer finalized: {len(valid_ids)} items, position={new_position}"
    )

    # Actualizar sesión
    session_repo = UserExampleSessionRepository(db)
    session_repo.update_session(current_user.id, valid_ids, new_position)

    return valid_ids, new_position, "ok"


def _action_resume(
    db: Session,
    current_user: User,
    limit: int,
    buffer_queue_item_ids: List[int],
    buffer_position: int,
) -> tuple[list, str, List[int], int]:
    """
    Acción: Resume la sesión del usuario (para onMounted).
    Devuelve ejemplos del buffer + información del buffer.

    Lógica:
    1. Si buffer está vacío, restaurar desde sesión guardada
    2. Remover items con palabras LEARNED
    3. Ajustar posición
    4. Si todos fueron visitados → descartar buffer y cargar nuevo
    5. Si no → refill si < limit
    6. Obtener ejemplos del buffer final

    Retorna (ejemplos_segmentados, status, buffer_ids, position).
    Status: "ok", "generating", o "no_words"
    """
    logger.info(
        f"[_action_resume] User {current_user.id}: Resuming session with buffer={buffer_queue_item_ids}, "
        f"position={buffer_position}"
    )

    session_repo = UserExampleSessionRepository(db)

    # PASO 1: Si buffer está vacío, restaurar desde sesión guardada
    if not buffer_queue_item_ids:
        logger.info(f"[_action_resume] Buffer is empty, attempting to restore from saved session")
        session = session_repo.get_or_create_session(current_user.id)

        try:
            restored_ids = json.loads(session.buffer_queue_item_ids) if session.buffer_queue_item_ids else []
            restored_position = session.buffer_position
        except (json.JSONDecodeError, TypeError):
            restored_ids = []
            restored_position = 0

        if restored_ids:
            logger.info(f"[_action_resume] Restored session with {len(restored_ids)} items, position {restored_position}")
            buffer_queue_item_ids = restored_ids
            buffer_position = restored_position
        else:
            logger.info(f"[_action_resume] No saved session found, returning empty")
            return [], "ok", [], 0

    visited_ids = session_repo.get_visited_queue_item_ids(current_user.id)
    all_visited = all(item_id in visited_ids for item_id in buffer_queue_item_ids)

    # PASO 2 y 3: Validar buffer y ajustar posición
    valid_ids = _validate_buffer_and_get_valid_ids(db, buffer_queue_item_ids, current_user)
    learned_items_removed = len(buffer_queue_item_ids) - len(valid_ids)
    new_position = _adjust_position_after_removals(buffer_queue_item_ids, valid_ids, buffer_position)

    logger.debug(f"[_action_resume] Removed {learned_items_removed} LEARNED items, position: {buffer_position} → {new_position}")

    final_buffer_ids = valid_ids
    final_position = new_position
    status = "ok"

    # PASO 4: Decidir si descartar buffer o refill
    should_load_new_batch = all_visited and learned_items_removed == 0

    if should_load_new_batch and buffer_queue_item_ids:
        logger.info(f"[_action_resume] All visited and no LEARNED items removed, loading new batch")

        queue_mgr = ContentQueueManager(db)
        new_items = queue_mgr.next_many(
            user_id=current_user.id,
            content_type=ContentType.EXAMPLE,
            amount=limit,
        )

        if new_items:
            final_buffer_ids = [item.id for item in new_items]
            final_position = 0

            if final_buffer_ids:
                session_repo.mark_queue_item_as_visited(current_user.id, final_buffer_ids[0])

            session_repo.update_session(current_user.id, final_buffer_ids, final_position)
            logger.info(f"[_action_resume] Loaded new batch with {len(final_buffer_ids)} items")
        else:
            final_buffer_ids = []
            final_position = 0

    else:
        # PASO 5: Refill buffer
        logger.info(
            f"[_action_resume] Buffer has unvisited items or LEARNED items were removed. "
            f"Current buffer: {len(final_buffer_ids)} items, limit: {limit}"
        )

        final_buffer_ids = _refill_buffer_to_limit(db, final_buffer_ids, limit, current_user)
        session_repo.update_session(current_user.id, final_buffer_ids, final_position)

    # PASO 6: Si buffer vacío, triggear generación o retornar no_words
    if not final_buffer_ids:
        logger.warning(f"[_action_resume] Buffer is empty, checking for available words")

        from learning_path.content_planner import ContentPlanner
        from learning_path.priority_engine import PriorityEngine
        from words.word_repository import WordRepository

        priority_engine = PriorityEngine()
        word_repo = WordRepository(db)
        best_option_repo = BestOptionRepository(db)
        example_repo = ExampleRepository(db)
        queue_mgr = ContentQueueManager(db)

        content_planner = ContentPlanner(
            session=db,
            priority_engine=priority_engine,
            content_queue=queue_mgr,
            word_repository=word_repo,
            example_repository=example_repo,
            best_option_repository=best_option_repo,
        )

        has_words = content_planner.has_non_learned_words(current_user.id, ContentType.EXAMPLE)

        if not has_words:
            logger.warning(f"[_action_resume] User has NO non-LEARNED words")
            return [], "no_words", [], 0

        logger.info(f"[_action_resume] Triggering generation")
        content_planner.ensure_ready(current_user.id, ContentType.EXAMPLE)

        return [], "generating", [], 0

    # PASO 7: Construir respuesta de ejemplos
    examples_response = _build_examples_response(db, final_buffer_ids)

    logger.info(f"[_action_resume] Resuming with {len(examples_response)} examples, status={status}")
    return examples_response, status, final_buffer_ids, final_position


def _action_next(
    db: Session,
    current_user: User,
    limit: int,
    buffer_queue_item_ids: List[int],
    buffer_position: int,
) -> tuple[list, str, List[int], int]:
    """
    Acción: Vacía el buffer completamente y carga nuevos items.

    Pasos:
    1. Descarta el buffer actual
    2. Limpia los items visitados
    3. Carga nuevos items desde ContentQueue hasta limit
    4. Retorna ejemplos con posición=0

    Retorna (ejemplos_segmentados, status, nuevo_buffer_ids, nuevo_position).
    Status puede ser: "ok", "generating", "no_words"
    """
    logger.info(
        f"[_action_next] User {current_user.id}: Fetching fresh batch"
    )

    session_repo = UserExampleSessionRepository(db)
    queue_mgr = ContentQueueManager(db)

    # Paso 1 y 2: Descartar buffer y limpiar visitados
    session_repo.reset_session(current_user.id)
    logger.info(f"[_action_next] Session reset")

    # Paso 3: Cargar nuevos items
    logger.info(f"[_action_next] Loading {limit} new items from ContentQueue")
    new_items = queue_mgr.next_many(
        user_id=current_user.id,
        content_type=ContentType.EXAMPLE,
        amount=limit,
    )

    new_buffer_ids = [item.id for item in new_items]
    logger.info(f"[_action_next] Loaded {len(new_buffer_ids)} items from ContentQueue")

    # Marcar primer item como visitado y actualizar sesión
    if new_buffer_ids:
        session_repo.mark_queue_item_as_visited(current_user.id, new_buffer_ids[0])
        session_repo.update_session(current_user.id, new_buffer_ids, 0)
        logger.info(f"[_action_next] Session updated with {len(new_buffer_ids)} items, position=0")

    # Si no hay items, triggear generación
    if not new_buffer_ids:
        logger.warning(f"[_action_next] ContentQueue empty")

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

        has_words = content_planner.has_non_learned_words(current_user.id, ContentType.EXAMPLE)

        if not has_words:
            logger.warning(f"[_action_next] User has NO non-LEARNED words")
            return [], "no_words", [], 0

        logger.warning(f"[_action_next] Triggering generation")
        content_planner.ensure_ready(current_user.id, ContentType.EXAMPLE)

        return [], "generating", [], 0

    # Construir respuesta
    examples_response = _build_examples_response(db, new_buffer_ids)
    return examples_response, "ok", new_buffer_ids, 0


# ==================== Funciones Auxiliares ====================

def _load_common_words():
    """Carga el set de palabras comunes desde most_common.txt, normalizando posesivos y contracciones"""
    # Intentar múltiples ubicaciones para encontrar most_common.txt
    possible_paths = [
        Path(__file__).parent.parent / "most_common.txt",  # backend/most_common.txt
        Path(__file__).parent.parent.parent / "backend" / "most_common.txt",  # /backend/most_common.txt
        Path("/app") / "most_common.txt",  # Docker
        Path("/app/backend") / "most_common.txt",  # Docker with backend
    ]

    common_words_path = None
    for path in possible_paths:
        if path.exists():
            common_words_path = path
            break

    if not common_words_path:
        logger.warning(f"[_load_common_words] File not found in any location. Tried: {possible_paths}")
        return set()

    common_words = set()
    with open(common_words_path, 'r', encoding='utf-8') as f:
        for word in f.readlines():
            word = word.strip().lower()
            if word:
                # Normalizar: remover 's al final y apóstrofos
                # Así "couldn't" → "couldnt", "team's" → "team", "could" → "could"
                normalized = re.sub(r"'s$", "", word).replace("'", "")
                common_words.add(normalized)

    return common_words


def _extract_words_from_example(text_segments, target_word_ids, common_words):
    """
    Extrae palabras del ejemplo, excluyendo:
    - Palabras comunes (de most_common.txt, ya normalizadas)
    - Palabras de una sola letra
    - Contracciones cuya raíz es común (ej: couldn't → could está en common_words)

    Normaliza posesivos (ej: team's → team, comedian's → comedian)

    Args:
        text_segments: Lista de TextSegment del ejemplo
        target_word_ids: Set de IDs de palabras que son target words en este ejemplo
        common_words: Set de palabras comunes (lowercased y normalizadas)

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

        # Detectar apostrofos: pueden ser ' (U+0027) o ' (U+2019) u otros
        has_any_apostrophe = any(c in word for c in ["'", "'", "`", "´", "’", "‘"])

        # Si tiene apóstrofo, verificar si la raíz es una palabra común
        # Ej: "couldn't" → raíz "could" está en common_words → excluir
        if has_any_apostrophe:
            # Intentar split con diferentes tipos de apóstrofos
            root = None
            for apostrophe in ["'", "'", "`", "´"]:
                if apostrophe in word:
                    root = word.split(apostrophe)[0]
                    break

            # Para contracciones con "n't" (don't, can't, couldn't, won't, etc.)
            # La raíz real es sin la "n". Ej: "couldn't" → raíz "could"
            if root and root.endswith("n"):
                root_without_n = root[:-1]
                if root_without_n in common_words:
                    continue

            # Verificar raíz tal cual
            if root and root in common_words:
                continue

        # Remover 's al final (normalizar posesivos: team's → team, comedian's → comedian)
        normalized = re.sub(r"'s$", "", word)

        # Remover apóstrofos restantes (contracciones: didn't → didnt)
        normalized = normalized.replace("'", "")

        # No extraer palabras de una sola letra
        if len(normalized) <= 1:
            continue

        # Excluir palabras comunes (common_words ya están normalizadas)
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
    Endpoint unificado con acciones encadenables y buffer management.

    Body:
    {
      "actions": ["resolve", "sync", "next"],  // Acciones a ejecutar en orden
      "resolve_queue_item_id": 47,             // Requerido si actions contiene "resolve"
      "limit": 5,                              // Para acciones "next" y "sync"
      "buffer_queue_item_ids": [1,2,3,4],      // Buffer actual
      "buffer_position": 0                     // Posición en buffer
    }

    Acciones disponibles:
    - "resolve": Resuelve un item (registra exposición) - requiere resolve_queue_item_id
    - "sync": Solo sincroniza la posición actual (sin tocar el buffer)
    - "sync-buffer": Valida y refill el buffer (para llenar después de marcar palabra como learned)
    - "resume": Resume sesión - carga nuevo buffer si todos fueron visitados, sino continúa (obtiene ejemplos)
    - "next": Descarta buffer completamente, limpia visitados, carga nuevos items y posición=0

    Ejemplos:
    - {"actions": ["resume"], "limit": 5, "buffer_queue_item_ids": [], "buffer_position": 0}
      → Resume sesión + obtener ejemplos (en onMounted)

    - {"actions": ["sync"], "limit": 4, "buffer_queue_item_ids": [1,2,3,4], "buffer_position": 2}
      → Solo sincronizar posición (al navegar)

    - {"actions": ["sync-buffer"], "limit": 4, "buffer_queue_item_ids": [1,2,3,4], "buffer_position": 1}
      → Validar y llenar buffer (después de marcar palabra como learned)

    - {"actions": ["next"], "limit": 4, "buffer_queue_item_ids": [], "buffer_position": 0}
      → Descartar buffer, limpiar visitados, cargar nuevos items, posición=0

    - {"actions": ["resolve"], "resolve_queue_item_id": 47, "limit": 4, "buffer_queue_item_ids": [1,2,3,4], "buffer_position": 1}
      → Resolver item 47 (registra exposición)

    Flujo de cada acción:
    - "resolve": Registra exposición + marca como resuelto y visitado
    - "sync": Actualiza posición únicamente
    - "sync-buffer": Valida buffer, remueve LEARNED, refill si es necesario
    - "resume": Carga nuevo buffer si todos visitados, sino mantiene buffer + posición
    - "next": Descarta buffer, limpia visitados, carga nuevos items, position=0
    """
    logger.info(
        f"[explore_examples] User {current_user.id}: actions={request.actions}, "
        f"resolve_id={request.resolve_queue_item_id}, limit={request.limit}, "
        f"buffer_ids={request.buffer_queue_item_ids}, buffer_pos={request.buffer_position}"
    )

    examples = []
    status = "ok"
    buffer_ids = request.buffer_queue_item_ids
    buffer_position = request.buffer_position
    session_updated = False  # Track if session was already updated by an action

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
            # resolve NO modifica buffer/posición, solo registra exposición

        elif action == "sync":
            buffer_ids, buffer_position, status = _action_sync(
                db=db,
                current_user=current_user,
                limit=request.limit,
                buffer_queue_item_ids=buffer_ids,
                buffer_position=buffer_position,
            )
            session_updated = True  # sync actualiza la sesión internamente

        elif action == "sync-buffer":
            buffer_ids, buffer_position, status = _action_sync_buffer(
                db=db,
                current_user=current_user,
                limit=request.limit,
                buffer_queue_item_ids=buffer_ids,
                buffer_position=buffer_position,
            )
            session_updated = True  # sync-buffer actualiza la sesión internamente

        elif action == "resume":
            examples, status, buffer_ids, buffer_position = _action_resume(
                db=db,
                current_user=current_user,
                limit=request.limit,
                buffer_queue_item_ids=buffer_ids,
                buffer_position=buffer_position,
            )
            session_updated = True  # resume actualiza la sesión internamente

        elif action == "next":
            examples, status, buffer_ids, buffer_position = _action_next(
                db=db,
                current_user=current_user,
                limit=request.limit,
                buffer_queue_item_ids=buffer_ids,
                buffer_position=buffer_position,
            )
            session_updated = True  # next debería actualizar la sesión

        else:
            logger.warning(f"[explore_examples] Unknown action: {action}")
            raise HTTPException(
                status_code=400,
                detail=f"Unknown action: {action}. Valid actions: 'resolve', 'sync', 'next'"
            )

    # Solo actualizar sesión si una acción requería hacerlo
    # Si solo se ejecutó 'resolve', NO actualizar (resolve no modifica buffer/posición)
    if not session_updated:
        logger.debug(f"[explore_examples] No action required session update - skipping")

    logger.info(
        f"[explore_examples] Completed with status={status}, returned {len(examples)} examples, "
        f"buffer_ids={buffer_ids}, buffer_position={buffer_position}"
    )

    return {
        "examples": examples,
        "buffer_queue_item_ids": buffer_ids,
        "buffer_position": buffer_position,
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


@router.patch("/{example_id}/toggle-marked")
@log_endpoint
def toggle_example_marked(
    example_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Alterna el estado de marcado de un ejemplo.

    Retorna el nuevo estado de is_marked.
    """
    logger.info(f"[toggle_example_marked] User {current_user.id}: Toggling marked status for example {example_id}")

    example_repo = ExampleRepository(db)
    is_marked = example_repo.toggle_marked(example_id)

    logger.debug(f"[toggle_example_marked] Example {example_id} is_marked: {is_marked}")

    return {
        "example_id": example_id,
        "is_marked": is_marked
    }


@router.get("/favorites", response_model=FavoritesResponse)
@log_endpoint
def get_favorite_examples(
    page: int = 1,
    limit: int = 15,
    is_marked: Optional[bool] = None,
    sort_by: str = 'not_marked_first',
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene ejemplos marcados como favoritos con paginación.

    Parámetros:
    - page: Número de página
    - limit: Items por página
    - is_marked: Filtrar por estado de marcado (true/false/null) - DEPRECATED, usar sort_by
    - sort_by: Modo de ordenamiento ('done', 'random', 'not_marked_first')
        - 'done': Solo favoritos marcados
        - 'not_marked_first': Todos, primero no marcados
        - 'random': Solo no marcados en orden aleatorio

    Retorna:
    - items: Lista de ejemplos favoritos con texto segmentado
    - total: Total de ejemplos favoritos
    - page: Página actual
    - limit: Items por página
    - pages: Total de páginas
    - status: "ok"
    """
    logger.info(f"[get_favorite_examples] User {current_user.id}: Fetching favorite examples (page={page}, limit={limit}, is_marked={is_marked}, sort_by={sort_by})")

    example_repo = ExampleRepository(db)
    paginated_data = example_repo.get_examples(page=page, limit=limit, is_marked=is_marked, sort_by=sort_by)

    # Segmentar el texto de cada ejemplo
    examples_response = []
    for example in paginated_data["items"]:
        text_segments = example_repo.segment_example_text(example)
        extracted_words = []  # Por ahora vacío, se puede implementar después
        examples_response.append({
            "id": example.id,
            "text": text_segments,
            "extracted_words": extracted_words,
            "is_favorite": example.is_favorite,
            "is_marked": example.is_marked
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

