from typing import Optional
from sqlmodel import Session, select
from logging_client import logger
from auth.models import User
from core.learning_path.models import LearningPathQueue
from core.enums import ContentType
from core.learning_path.repository import LearningPathRepository
from core.learning_path.content_repository import ContentRepository

from core.learning_path.content_queue import ContentQueue
from core.learning_path.content_planner import ContentPlanner
from core.learning_path.priority_engine import PriorityEngine
from core.learning_path.learning_tracker import LearningTracker


class LearningPathService:
    """
    Servicio para operaciones core de learning path.

    Responsabilidades:
    - Preparar y chequear contenido disponible
    - Triggear generación cuando es necesario
    - Manejo de ContentPlanner
    """

    def __init__(
        self,
        db: Session,
        content_repo: Optional[ContentRepository] = None,
    ):
        self.db = db
        self.queue_mgr = ContentQueue(db, content_repo)
        self.content_repo = content_repo
        self.priority_engine = PriorityEngine()

    def prepare_content_or_generate(
        self,
        user_id: int,
        content_type: ContentType = None,
    ) -> str:
        """
        Chequea si hay contenido disponible o triggea generación.

        Pasos:
        1. Chequea si hay palabras no-LEARNED disponibles
        2. Si no hay, retorna "no_words"
        3. Si hay pero la queue está vacía, triggea generación y retorna "generating"
        4. Si hay contenido, retorna "ok"

        Returns:
            "ok" - Contenido disponible
            "generating" - Se triggeró generación, espera a que termine
            "no_words" - Sin palabras disponibles para aprender
        """
        if content_type is None:
            content_type = ContentType.EXAMPLE

        logger.info(
            f"[LearningPathService.prepare_content_or_generate] "
            f"User {user_id}, content_type={content_type}"
        )

        # Inyectar generador unificado
        from features.content_generator import UnifiedContentGenerator

        content_planner = ContentPlanner(
            session=self.db,
            priority_engine=self.priority_engine,
            content_queue=self.queue_mgr,
            content_repo=self.content_repo,
            content_generator=UnifiedContentGenerator(),
        )

        # Chequear si hay palabras no-LEARNED
        has_words = content_planner.has_non_learned_words(user_id, content_type)

        if not has_words:
            logger.warning(
                f"[LearningPathService.prepare_content_or_generate] "
                f"User {user_id} has NO non-LEARNED words"
            )
            return "no_words"

        # Triggear generación si es necesario
        content_planner.ensure_ready(user_id, content_type)

        return "generating"

    # ==================== Generation Monitoring ====================

    def is_content_generating(
        self,
        user_id: int,
        content_type: ContentType = None,
    ) -> bool:
        """
        Chequea si el learning path está actualmente generando contenido.

        Args:
            user_id: ID del usuario
            content_type: Tipo de contenido (si no se especifica, chequea todos)

        Returns:
            True si hay generación en progreso, False en caso contrario
        """

        repo = LearningPathRepository(self.db)
        return repo.is_generating(user_id, content_type)

    def has_available_words_for_generation(
        self,
        user_id: int,
        content_type: ContentType = None,
    ) -> bool:
        """
        Chequea si hay palabras disponibles para generar más contenido.
        Retorna True si hay palabras no-LEARNED, False en caso contrario.

        Args:
            user_id: ID del usuario
            content_type: Tipo de contenido (si no se especifica, usa EXAMPLE)

        Returns:
            True si hay palabras disponibles para generar, False si no hay
        """
        if content_type is None:
            content_type = ContentType.EXAMPLE

        logger.info(
            f"[LearningPathService.has_available_words_for_generation] "
            f"User {user_id}, content_type={content_type}"
        )

        # Inyectar generador unificado
        from features.content_generator import UnifiedContentGenerator

        content_planner = ContentPlanner(
            session=self.db,
            priority_engine=self.priority_engine,
            content_queue=self.queue_mgr,
            content_repo=self.content_repo,
            content_generator=UnifiedContentGenerator(),
        )

        # Chequear si hay palabras no-LEARNED
        has_words = content_planner.has_non_learned_words(user_id, content_type)

        logger.info(
            f"[LearningPathService.has_available_words_for_generation] "
            f"User {user_id} has_words={has_words}"
        )

        return has_words

    # ==================== Queue Item Access ====================

    def get_queue_item(self, queue_item_id: int, user_id: int) -> LearningPathQueue | None:
        """
        Obtiene un item específico de la queue.

        Returns:
            Item de queue o None si no existe
        """
        return self.db.exec(
            select(LearningPathQueue).where(
                LearningPathQueue.id == queue_item_id,
                LearningPathQueue.user_id == user_id,
            )
        ).first()

    def is_queue_item_learned(self, queue_item: LearningPathQueue, user_id: int) -> bool:
        """
        Chequea si un item tiene todas sus palabras target en estado LEARNED.

        Returns:
            True si el item debe ser descartado (todas las palabras LEARNED)
            False si el item es válido (al menos una palabra no LEARNED)
        """
        if not self.content_repo:
            return False

        # Delegar al repositorio la lógica de verificación
        return self.content_repo.is_content_learned(
            content_id=queue_item.content_id,
            content_type=queue_item.content_type,
            user_id=user_id,
        )

    def load_batch(self, user_id: int, limit: int, content_type: ContentType = None) -> list:
        """
        Carga un batch de items desde la queue.

        Args:
            user_id: ID del usuario
            limit: Número máximo de items a cargar
            content_type: Tipo de contenido (si no se especifica, usa EXAMPLE por defecto)

        Returns:
            Lista de items cargados
        """
        if content_type is None:
            content_type = ContentType.EXAMPLE

        logger.debug(f"[load_batch] Loading {limit} items for user {user_id} (type={content_type})")

        items = self.queue_mgr.next_many(
            user_id=user_id,
            content_type=content_type,
            amount=limit,
        )

        return items if items else []

    # ==================== Queue Item Resolution ====================

    def resolve_queue_item(
        self,
        queue_item_id: int,
        user_id: int,
    ) -> bool:
        """
        Resuelve un item: registra exposición + marca CONSUMED.

        Returns:
            True si fue exitoso, False en caso contrario
        """
        from core.explore.explore_repository import ExploreRepository

        logger.debug(f"[resolve_queue_item] Resolving queue_item_id={queue_item_id}")

        session_repo = ExploreRepository(self.db)

        # Chequear si ya fue resuelto
        if session_repo.is_delivery_item_resolved(user_id, queue_item_id):
            logger.debug(f"[resolve_queue_item] Item {queue_item_id} already resolved, skipping")
            return True

        # Obtener item
        queue_item = self.db.exec(
            select(LearningPathQueue)
            .where(LearningPathQueue.id == queue_item_id)
            .with_for_update()
        ).first()

        if not queue_item or queue_item.user_id != user_id:
            logger.warning(f"[resolve_queue_item] Item {queue_item_id} not found or unauthorized")
            return False

        # Registrar exposición
        if self.content_repo:
            tracker = LearningTracker(self.db, self.content_repo)
            tracker.record_exposure(
                user_id=user_id,
                content_type=queue_item.content_type,
                content_id=queue_item.content_id,
            )

        # Marcar como consumido y visitado
        self.queue_mgr.consume(queue_item_id)
        session_repo.mark_delivery_item_as_resolved(user_id, queue_item_id)
        session_repo.mark_delivery_item_as_visited(user_id, queue_item_id)

        logger.debug(f"[resolve_queue_item] Successfully resolved queue_item_id={queue_item_id}")
        return True
