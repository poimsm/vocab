from typing import Optional
from sqlmodel import Session, select
from logging_client import logger
from auth.models import User
from core.learning_path.models import LearningPathQueue
from core.enums import ContentType
from core.learning_path.repository import LearningPathRepository
from core.learning_path.content_repository import ContentRepository
from features.words.models import Word, WordStatistics
from core.learning_path.enums import LearningState, LearningPathQueueStatus
from datetime import datetime, timezone

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

    def get_prioritized_content(
        self,
        user_id: int,
        content_type: ContentType = None,
    ) -> Optional[LearningPathQueue]:
        """
        Obtiene 1 item priorizado del learning path con distribución diversa.

        Estrategia de distribución:
        1. Carga 16 items (1 por palabra, de las 16 primeras no-LEARNED)
        2. Calcula prioridades usando PriorityEngine
        3. Aplica band-pass filtering: penaliza últimas N palabras mostradas
        4. Selecciona aleatoriamente con peso por prioridad (weighted random)
        5. Actualiza RecentWordHistory con la palabra seleccionada

        Returns:
            Un LearningPathQueue item, o None si no hay contenido
        """
        import random
        from core.learning_path.models import LearningPathCursor, RecentWordHistory, BandPassConfig

        if content_type is None:
            content_type = ContentType.EXAMPLE

        # 1. Obtener palabras no-LEARNED
        available_words = self.db.exec(
            select(Word.id).join(
                WordStatistics,
                (Word.id == WordStatistics.word_id) & (WordStatistics.type == content_type)
            ).where(
                Word.user_id == user_id,
                WordStatistics.learning_state != LearningState.LEARNED,
            )
        ).all()

        if not available_words:
            logger.debug(f"[get_prioritized_content] No available words for user {user_id}")
            return None

        # 2. Cargar 1 item de cada palabra (16 palabras para mayor diversidad)
        items_by_word = {}
        for word_id in available_words[:16]:  # Aumentado de 8 a 16 palabras
            item = self.db.exec(
                select(LearningPathQueue).where(
                    LearningPathQueue.user_id == user_id,
                    LearningPathQueue.content_type == content_type,
                    LearningPathQueue.status == LearningPathQueueStatus.PENDING,
                    LearningPathQueue.word_id == word_id,
                )
                .order_by(LearningPathQueue.priority.desc())
                .limit(1)
            ).first()
            if item:
                items_by_word[word_id] = item

        if not items_by_word:
            logger.debug(f"[get_prioritized_content] No pending items for user {user_id}")
            return None

        # 3. Obtener estadísticas de palabras y calcular prioridades
        word_priorities = {}
        words_data = self.db.exec(
            select(Word, WordStatistics).join(
                WordStatistics,
                (Word.id == WordStatistics.word_id) & (WordStatistics.type == content_type)
            ).where(
                Word.id.in_(list(items_by_word.keys())),
                Word.user_id == user_id,
            )
        ).all()

        now = datetime.now(timezone.utc)
        spacing_count = sum(
            1 for _, stats in words_data
            if stats.learning_state == LearningState.SPACING
        )

        for word, stats in words_data:
            priority = self.priority_engine.calculate_priority(
                word=word,
                statistics=stats,
                now=now,
                expected_exposure=0.0,
                spacing_words_count=spacing_count,
            )
            word_priorities[word.id] = priority

        # 4. Aplicar band-pass filtering: penalizar últimas N palabras mostradas
        band_pass_config = self.db.exec(
            select(BandPassConfig).where(
                (BandPassConfig.user_id == user_id) &
                (BandPassConfig.type == content_type)
            )
        ).first()

        # Usar config del usuario o defaults
        window_size = band_pass_config.window_size if band_pass_config else 3
        inflation_factor = band_pass_config.inflation_factor if band_pass_config else 0.2

        # Obtener las últimas N palabras en el histórico de band-pass
        recent_word_records = self.db.exec(
            select(RecentWordHistory).where(
                (RecentWordHistory.user_id == user_id) &
                (RecentWordHistory.type == content_type)
            )
            .order_by(RecentWordHistory.created_at.desc())
            .limit(window_size)
        ).all()

        # Recopilar word_ids del histórico
        recent_word_ids = set(record.word_id for record in recent_word_records)

        # Aplicar penalidad de banda: reducir prioridad de palabras recientes
        # Penalty es más fuerte si hay pocas palabras disponibles (graceful degradation)
        total_available = len(items_by_word)
        for word_id in recent_word_ids:
            if word_id in word_priorities:
                original = word_priorities[word_id]
                # Factor dinámico: más penalidad cuando hay pocas palabras
                # Si quedan 3 palabras y todas están en histórico, aún así pueden ser seleccionadas
                dynamic_penalty = inflation_factor * (1.0 + max(0, (float(window_size) - total_available) / float(window_size)))
                word_priorities[word_id] = max(0.01, original * (1.0 - dynamic_penalty))
                logger.debug(
                    f"[get_prioritized_content] Band-pass penalty applied to word {word_id}: "
                    f"{original:.3f} -> {word_priorities[word_id]:.3f} (factor={dynamic_penalty:.2f})"
                )

        # 5. Obtener último word_id seleccionado para rotación básica
        cursor = self.db.exec(
            select(LearningPathCursor).where(
                (LearningPathCursor.user_id == user_id) &
                (LearningPathCursor.type == content_type)
            )
        ).first()

        last_word = cursor.last_selected_word_id if cursor else None

        # 6. Selección ponderada aleatoria (weighted random selection)
        # Excluir la última palabra seleccionada para evitar repetición inmediata
        available_word_ids = [
            wid for wid in items_by_word.keys()
            if wid != last_word
        ]

        if not available_word_ids:
            # Si solo hay una palabra o la última es la única, usar todas
            available_word_ids = list(items_by_word.keys())

        # Calcular pesos: mayor prioridad = mayor probabilidad de selección
        weights = [max(0.01, word_priorities.get(wid, 0.0)) for wid in available_word_ids]

        # Seleccionar aleatoriamente ponderado
        selected_word_id = random.choices(available_word_ids, weights=weights, k=1)[0]
        selected_item = items_by_word[selected_word_id]

        # 7. Actualizar RecentWordHistory: agregar nuevo registro y mantener window_size registros
        # Insertar nuevo registro con la palabra seleccionada
        new_history_record = RecentWordHistory(
            user_id=user_id,
            type=content_type,
            word_id=selected_word_id,
        )
        self.db.add(new_history_record)
        self.db.flush()

        # Obtener todos los registros del usuario/tipo ordenados por fecha (más antiguos primero)
        all_history_records = self.db.exec(
            select(RecentWordHistory).where(
                (RecentWordHistory.user_id == user_id) &
                (RecentWordHistory.type == content_type)
            )
            .order_by(RecentWordHistory.created_at.asc())
        ).all()

        # Eliminar registros antiguos si superamos window_size
        if len(all_history_records) > window_size:
            records_to_delete = all_history_records[: len(all_history_records) - window_size]
            for record in records_to_delete:
                self.db.delete(record)

        # 8. Guardar cursor para próxima rotación en la BD
        if cursor:
            cursor.last_selected_word_id = selected_word_id
            self.db.add(cursor)
        else:
            new_cursor = LearningPathCursor(
                user_id=user_id,
                type=content_type,
                current_segment=1,
                current_position=0,
                last_selected_word_id=selected_word_id,
            )
            self.db.add(new_cursor)

        self.db.commit()

        logger.debug(
            f"[get_prioritized_content] Selected item (id={selected_item.id}, "
            f"word_id={selected_word_id}, priority={word_priorities.get(selected_word_id, 0.0):.2f}) "
            f"from {len(available_word_ids)} available words for user {user_id}"
        )

        return selected_item

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
