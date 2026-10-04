from typing import List, Tuple, Optional
from sqlmodel import Session, select
import json

from logging_client import logger
from auth.models import User

from core.enums import ContentType
from core.learning_path.services import LearningPathService
from core.delivery.service import DeliveryService
from core.explore.explore_buffer_service import ExploreBufferService
from core.explore.explore_repository import ExploreRepository
from core.explore.protocols import ContentRepository, ContentValidator


class ExploreActions:
    """
    Gestiona las acciones del explore endpoint.

    Responsabilidades:
    - Ejecutar acciones (resolve, sync, sync-buffer, resume, next)
    - Validar y gestionar buffer del usuario
    - Orquestar buffer de delivery y queue items

    No construye respuestas (eso se delega a feature-specific builders en backend.features)

    Nota: Las dependencias se inyectan para mantener desacoplamiento de features.
    """

    def __init__(
        self,
        db: Session,
        content_repo: ContentRepository,
        content_validator: ContentValidator,
    ):
        self.db = db
        self.explore_repo = ExploreRepository(db)
        self.content_repo = content_repo

        self.learning_path_service = LearningPathService(
            db,
            content_repo=content_repo,
        )
        self.explore_buffer_service = ExploreBufferService(db, content_validator=content_validator)
        self.delivery_service = DeliveryService(db)

    # ==================== Orquestación ====================

    def execute_actions(
        self,
        user_id: int,
        actions: List[str],
        content_type: ContentType,
        resolve_queue_item_id: Optional[int] = None,
        limit: int = 5,
        buffer_delivery_ids: List[int] = None,
        buffer_position: int = 0,
    ) -> Tuple[str, List[int], int]:
        """
        Ejecuta acciones de explore en orden.

        Returns:
            (status, updated_buffer_ids, updated_position)
        """
        if buffer_delivery_ids is None:
            buffer_delivery_ids = []

        logger.info(
            f"[ExploreActions.execute_actions] User {user_id}: "
            f"actions={actions}, limit={limit}, buffer_size={len(buffer_delivery_ids)}"
        )

        current_user = self.db.exec(select(User).where(User.id == user_id)).first()
        if not current_user:
            raise ValueError(f"User {user_id} not found")

        status = "ok"
        buffer_ids = buffer_delivery_ids
        buffer_pos = buffer_position

        # Ejecutar acciones en orden
        for action in actions:
            if action == "resolve":
                if resolve_queue_item_id is None:
                    raise ValueError("Action 'resolve' requires resolve_queue_item_id")
                self.action_resolve(resolve_queue_item_id, current_user)

            elif action == "sync":
                buffer_ids, buffer_pos, status = self.action_sync(
                    current_user, content_type, buffer_ids, buffer_pos
                )

            elif action == "sync-buffer":
                buffer_ids, buffer_pos, status = self.action_sync_buffer(
                    current_user, content_type, limit, buffer_ids, buffer_pos
                )

            elif action == "resume":
                status, buffer_ids, buffer_pos = self.action_resume(
                    current_user, content_type, limit, buffer_ids, buffer_pos
                )

            elif action == "next":
                status, buffer_ids, buffer_pos = self.action_next(
                    current_user, content_type, limit, buffer_ids, buffer_pos
                )

            else:
                raise ValueError(f"Unknown action: {action}")

        logger.info(
            f"[ExploreActions.execute_actions] Completed: status={status}, "
            f"buffer_size={len(buffer_ids)}"
        )

        return status, buffer_ids, buffer_pos

    # ==================== Acciones ====================

    def action_resolve(
        self,
        queue_item_id: int,
        current_user: User,
    ) -> None:
        """Resuelve un item: registra exposición + marca CONSUMED."""
        self.learning_path_service.resolve_queue_item(queue_item_id, current_user.id)

    def action_sync(
        self,
        current_user: User,
        content_type: ContentType,
        buffer_delivery_ids: List[int],
        buffer_position: int,
    ) -> Tuple[List[int], int, str]:
        """
        Sincroniza la posición actual.

        IMPORTANTE: Si buffer está vacío, restaura buffer desde sesión
        pero SIEMPRE actualiza la posición. Esto permite que la posición
        se sincronice cuando el usuario navega entre items.
        """
        logger.info(
            f"[action_sync] User {current_user.id}: Syncing position={buffer_position}, buffer_size={len(buffer_delivery_ids)}"
        )

        # Si buffer está vacío, restaurar desde sesión guardada
        if not buffer_delivery_ids:
            logger.debug(f"[action_sync] Buffer is empty, restoring from saved session")
            session = self.explore_repo.get_or_create_session(current_user.id, content_type.value)
            try:
                restored_ids = (
                    json.loads(session.buffer_delivery_ids)
                    if session.buffer_delivery_ids
                    else []
                )
            except (json.JSONDecodeError, TypeError):
                restored_ids = []

            if restored_ids:
                logger.info(
                    f"[action_sync] Restored {len(restored_ids)} items from session, "
                    f"updating position from {session.buffer_position} to {buffer_position}"
                )
                # Actualizar SOLO la posición, mantener buffer restaurado
                self.explore_repo.update_session(current_user.id, restored_ids, buffer_position, content_type.value)
                return restored_ids, buffer_position, "ok"
            else:
                logger.debug(f"[action_sync] No saved session with items found")
                return [], buffer_position, "ok"

        # Si buffer tiene items, actualizar sesión normalmente
        self.explore_repo.update_session(current_user.id, buffer_delivery_ids, buffer_position, content_type.value)

        return buffer_delivery_ids, buffer_position, "ok"

    def action_sync_buffer(
        self,
        current_user: User,
        content_type: ContentType,
        limit: int,
        buffer_delivery_ids: List[int],
        buffer_position: int,
    ) -> Tuple[List[int], int, str]:
        """Valida y refill el buffer de forma agresiva."""
        logger.info(
            f"[action_sync_buffer] User {current_user.id}: Aggressive sync-buffer "
            f"with {len(buffer_delivery_ids)} items"
        )

        # Validar y remover items LEARNED
        valid_ids = self.explore_buffer_service.validate_buffer_items(
            buffer_delivery_ids, current_user.id
        )

        # Calcular nueva posición
        new_position = self.explore_buffer_service.adjust_position_after_removals(
            buffer_delivery_ids, valid_ids, buffer_position
        )

        # Refill buffer
        valid_ids = self.explore_buffer_service.refill_buffer(valid_ids, content_type, limit, current_user.id)

        # Actualizar sesión
        self.explore_repo.update_session(current_user.id, valid_ids, new_position, content_type.value)

        logger.info(
            f"[action_sync_buffer] Buffer finalized: {len(valid_ids)} items, position={new_position}"
        )

        return valid_ids, new_position, "ok"

    def action_resume(
        self,
        current_user: User,
        content_type: ContentType,
        limit: int,
        buffer_delivery_ids: List[int],
        buffer_position: int,
    ) -> Tuple[str, List[int], int]:
        """Resume la sesión del usuario."""
        logger.info(
            f"[action_resume] User {current_user.id}: Resuming session "
            f"with {len(buffer_delivery_ids)} items"
        )

        was_session_restored = False

        # PASO 1: Si buffer vacío, restaurar desde sesión guardada
        if not buffer_delivery_ids:
            logger.info(f"[action_resume] Buffer is empty, restoring from saved session")
            session = self.explore_repo.get_or_create_session(current_user.id, content_type.value)

            try:
                restored_ids = (
                    json.loads(session.buffer_delivery_ids)
                    if session.buffer_delivery_ids
                    else []
                )
                restored_position = session.buffer_position
            except (json.JSONDecodeError, TypeError):
                restored_ids = []
                restored_position = 0

            if restored_ids:
                logger.info(f"[action_resume] Restored {len(restored_ids)} items at position {restored_position}")
                buffer_delivery_ids = restored_ids
                buffer_position = restored_position
                was_session_restored = True
            else:
                logger.info(f"[action_resume] No saved session found")
                return "ok", [], 0

        # PASO 1.5: Si sesión fue restaurada, retornar items exactamente como estaban
        # Sin validar ni remover items (eso debería hacerse cuando se navega/sync)
        if was_session_restored:
            logger.info(
                f"[action_resume] Returning restored session as-is: "
                f"{len(buffer_delivery_ids)} items at position {buffer_position}"
            )
            # Reset generation monitor since we successfully recovered content
            from core.learning_path.repository import LearningPathRepository
            lp_repo = LearningPathRepository(self.db)
            lp_repo.reset_generation_monitor(current_user.id, content_type)
            return "ok", buffer_delivery_ids, buffer_position

        # PASO 2-5: Lógica de validación solo si NO se restauró sesión guardada
        visited_ids = self.explore_repo.get_visited_delivery_ids(current_user.id, content_type.value)
        all_visited = all(item_id in visited_ids for item_id in buffer_delivery_ids)

        # Validar buffer y ajustar posición
        valid_ids = self.explore_buffer_service.validate_buffer_items(
            buffer_delivery_ids, current_user.id
        )
        learned_items_removed = len(buffer_delivery_ids) - len(valid_ids)
        new_position = self.explore_buffer_service.adjust_position_after_removals(
            buffer_delivery_ids, valid_ids, buffer_position
        )

        final_buffer_ids = valid_ids
        final_position = new_position
        status = "ok"

        # PASO 4: Decidir si descartar buffer o refill
        should_load_new_batch = all_visited and learned_items_removed == 0

        if should_load_new_batch and buffer_delivery_ids:
            logger.info(f"[action_resume] All visited, loading new batch")

            final_buffer_ids = self.explore_buffer_service.load_next_batch(
                current_user.id, content_type, limit
            )

            if final_buffer_ids:
                final_position = 0

                if final_buffer_ids:
                    self.explore_repo.mark_delivery_item_as_visited(
                        current_user.id, final_buffer_ids[0], content_type.value
                    )

                self.explore_repo.update_session(current_user.id, final_buffer_ids, final_position, content_type.value)
                logger.info(f"[action_resume] Loaded {len(final_buffer_ids)} items")
            else:
                final_buffer_ids = []
                final_position = 0

        else:
            # PASO 5: Refill buffer
            logger.info(
                f"[action_resume] Buffer has unvisited items, refilling to {limit}"
            )

            final_buffer_ids = self.explore_buffer_service.refill_buffer(
                final_buffer_ids, content_type, limit, current_user.id
            )
            self.explore_repo.update_session(current_user.id, final_buffer_ids, final_position, content_type.value)

        # PASO 6: Si buffer vacío, obtener contenido mixto
        if not final_buffer_ids:
            logger.warning(f"[action_resume] Buffer is empty, checking for content")

            result = self.delivery_service.get_mixed_content(current_user.id, content_type, limit)
            status = result["status"]

            return status, [], 0

        # Safety check: Ensure position is within valid range
        if final_buffer_ids and final_position >= len(final_buffer_ids):
            logger.warning(
                f"[action_resume] Position {final_position} out of bounds for buffer of {len(final_buffer_ids)} items. "
                f"Clamping to {len(final_buffer_ids) - 1}"
            )
            final_position = len(final_buffer_ids) - 1

        logger.info(f"[action_resume] Resuming with {len(final_buffer_ids)} items")

        return status, final_buffer_ids, final_position

    def action_next(
        self,
        current_user: User,
        content_type: ContentType,
        limit: int,
        buffer_delivery_ids: List[int],
        buffer_position: int,
    ) -> Tuple[str, List[int], int]:
        """Vacía el buffer y carga nuevos items."""
        logger.info(f"[action_next] User {current_user.id}: Fetching fresh batch")

        # Descartar buffer y limpiar visitados
        self.explore_repo.reset_session(current_user.id, content_type.value)

        # Cargar nuevos items
        new_buffer_ids = self.explore_buffer_service.load_next_batch(
            current_user.id, content_type, limit
        )

        logger.info(f"[action_next] Loaded {len(new_buffer_ids)} items")

        # Marcar primer item como visitado
        if new_buffer_ids:
            self.explore_repo.mark_delivery_item_as_visited(current_user.id, new_buffer_ids[0], content_type.value)
            self.explore_repo.update_session(current_user.id, new_buffer_ids, 0, content_type.value)

        # Si no hay items, obtener contenido mixto
        if not new_buffer_ids:
            logger.warning(f"[action_next] ContentQueue empty, checking for content")

            result = self.delivery_service.get_mixed_content(current_user.id, content_type, limit)
            status = result["status"]

            return status, [], 0

        return "ok", new_buffer_ids, 0


