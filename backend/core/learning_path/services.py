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

    def get_prioritized_content(
        self,
        user_id: int,
        content_type: ContentType = None,
        limit: int = 10,
    ) -> list:
        """
        Obtiene contenido del LearningPathQueue priorizando según el priority engine.

        Maneja correctamente diferentes tipos de contenido:
        - EXAMPLE: content_id → Example.id → ExampleWord.word_id → Word
        - BEST_OPTIONS: content_id → BestOption.id → BestOption.word_id → Word

        Args:
            user_id: ID del usuario
            content_type: Tipo de contenido (si no se especifica, usa EXAMPLE)
            limit: Cantidad máxima de items a retornar

        Returns:
            Lista de LearningPathQueue items priorizados
        """
        from features.words.models import Word, WordStatistics
        from core.learning_path.enums import LearningState
        from datetime import datetime, timezone

        if content_type is None:
            content_type = ContentType.EXAMPLE

        logger.debug(
            f"[get_prioritized_content] Getting {limit} prioritized items for user {user_id} "
            f"(content_type={content_type})"
        )

        # 1. Obtener todos los items PENDING del usuario para este content_type
        pending_items = self.db.exec(
            select(LearningPathQueue).where(
                LearningPathQueue.user_id == user_id,
                LearningPathQueue.content_type == content_type,
                LearningPathQueue.status.in_(["PENDING", "TRANSFERRED"]),
            )
        ).all()

        if not pending_items:
            logger.debug(
                f"[get_prioritized_content] No pending items for user {user_id} (type={content_type})"
            )
            return []

        # 2. Obtener word_id para cada item (varía según content_type)
        item_word_map = {}  # queue_item_id → word_id
        content_ids = [item.content_id for item in pending_items]

        if content_type == ContentType.EXAMPLE:
            # Para EXAMPLE: content_id → Example → ExampleWord → Word
            from features.examples.models import Example
            from features.words.models import ExampleWord

            examples_with_words = self.db.exec(
                select(Example.id, ExampleWord.word_id).join(
                    ExampleWord, Example.id == ExampleWord.example_id
                ).where(
                    Example.id.in_(content_ids)
                )
            ).all()

            for example_id, word_id in examples_with_words:
                for item in pending_items:
                    if item.content_id == example_id and item.id not in item_word_map:
                        item_word_map[item.id] = word_id

        elif content_type == ContentType.BEST_OPTIONS:
            # Para BEST_OPTIONS: content_id → BestOption → word_id
            from features.best_options.models import BestOption

            best_options = self.db.exec(
                select(BestOption.id, BestOption.word_id).where(
                    BestOption.id.in_(content_ids)
                )
            ).all()

            for best_option_id, word_id in best_options:
                for item in pending_items:
                    if item.content_id == best_option_id and item.id not in item_word_map:
                        item_word_map[item.id] = word_id

        if not item_word_map:
            logger.warning(
                f"[get_prioritized_content] Could not map any of {len(pending_items)} items to words (type={content_type}). "
                f"Content IDs: {content_ids}"
            )
            return []

        # 3. Obtener IDs de palabras únicas
        word_ids = list(set(item_word_map.values()))

        # 3a. Asegurar que todas las palabras tienen WordStatistics (crear si faltan)
        from core.learning_path.enums import LearningState as LearningStateEnum
        from datetime import datetime, timezone

        existing_stats = self.db.exec(
            select(WordStatistics.word_id).where(
                WordStatistics.word_id.in_(word_ids),
                WordStatistics.type == content_type,
            )
        ).all()

        existing_word_ids = set(existing_stats)
        missing_word_ids = [wid for wid in word_ids if wid not in existing_word_ids]

        if missing_word_ids:
            logger.debug(
                f"[get_prioritized_content] Creating missing WordStatistics for {len(missing_word_ids)} words"
            )
            for word_id in missing_word_ids:
                try:
                    new_stats = WordStatistics(
                        word_id=word_id,
                        type=content_type,
                        learning_state=LearningStateEnum.NEW,
                        times_seen=0,
                        current_cycle_seen=0,
                        created_at=datetime.now(timezone.utc),
                    )
                    self.db.add(new_stats)
                    self.db.flush()
                except Exception as e:
                    logger.error(f"[get_prioritized_content] Error creating stats for word {word_id}: {e}")
            self.db.commit()

        # 4. Obtener palabras y sus estadísticas
        words = self.db.exec(
            select(Word, WordStatistics).join(
                WordStatistics,
                (Word.id == WordStatistics.word_id) & (WordStatistics.type == content_type)
            ).where(
                Word.id.in_(word_ids),
                Word.user_id == user_id,
            )
        ).all()

        logger.debug(
            f"[get_prioritized_content] Found {len(words)} word-stats pairs for {len(word_ids)} words (type={content_type})"
        )

        if not words:
            logger.warning(
                f"[get_prioritized_content] No WordStatistics found for {len(word_ids)} words (type={content_type}). "
                f"Returning items without priority sorting (fallback). Word IDs: {word_ids}"
            )
            # Fallback: return items in their natural order if stats don't exist
            # This ensures content is still available even if stats generation is delayed
            result = pending_items[:limit]
            logger.info(
                f"[get_prioritized_content] Returning {len(result)} items without priority sorting for user {user_id}"
            )
            return result

        # 5. Calcular prioridad para cada palabra
        word_priorities = {}
        now = datetime.now(timezone.utc)
        spacing_words_count = sum(
            1 for w_tuple in words
            if len(w_tuple) >= 2 and w_tuple[1].learning_state == LearningState.SPACING
        )

        for word_tuple in words:
            word = word_tuple[0] if isinstance(word_tuple, tuple) else word_tuple
            stats = word_tuple[1] if isinstance(word_tuple, tuple) and len(word_tuple) > 1 else None

            if stats is None:
                continue

            priority = self.priority_engine.calculate_priority(
                word=word,
                statistics=stats,
                now=now,
                expected_exposure=0.0,
                spacing_words_count=spacing_words_count,
            )

            word_priorities[word.id] = priority

        # 6. Agrupar items por palabra para distribución inteligente
        items_by_word = {}
        for item in pending_items:
            word_id = item_word_map.get(item.id)
            if word_id not in items_by_word:
                items_by_word[word_id] = []
            items_by_word[word_id].append(item)

        # 7. Ordenar palabras por prioridad (highest first)
        sorted_word_ids = sorted(
            items_by_word.keys(),
            key=lambda wid: word_priorities.get(wid, 0.0),
            reverse=True,
        )

        # 8. Distribuir items en rotación entre palabras para mezclar contenido
        result = []
        word_queue_indices = {wid: 0 for wid in sorted_word_ids}

        while len(result) < limit and any(
            word_queue_indices[wid] < len(items_by_word[wid])
            for wid in sorted_word_ids
        ):
            for word_id in sorted_word_ids:
                if len(result) >= limit:
                    break

                idx = word_queue_indices[word_id]
                if idx < len(items_by_word[word_id]):
                    result.append(items_by_word[word_id][idx])
                    word_queue_indices[word_id] += 1

        logger.info(
            f"[get_prioritized_content] Returning {len(result)} mixed items for user {user_id} "
            f"(type={content_type}, word_order={sorted_word_ids}, "
            f"priorities={[round(word_priorities.get(wid, 0.0), 2) for wid in sorted_word_ids]})"
        )

        return result

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
