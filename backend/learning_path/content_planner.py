from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict
from sqlmodel import Session, select, func
from logging_client import logger
from models import (
    Word,
    WordStatistics,
    LearningPath,
    LearningPathHistory,
    LearningPathCursor,
    ContentType,
    LearningState,
    ContentQueueStatus,
    ContentQueue as ContentQueueModel,  # Modelo de BD
)
from learning_path.priority_engine import PriorityEngine
from learning_path.content_queue import ContentQueue  # Clase de negocio


class ContentPlanner:
    """
    Cerebro de planificación.

    Coordina:

        Word
        WordStatistics
        PriorityEngine
        LearningPath
        LearningPathHistory
        ContentQueue
        ExampleRepository
        BestOptionRepository
        AI generators

    Su responsabilidad es decidir qué debe prepararse
    y mantener un buffer de contenido suficiente.

    NO registra exposiciones reales.
    NO administra directamente las estadísticas de aprendizaje.
    Eso pertenece a LearningTracker.
    """

    def __init__(
        self,
        session: Session,
        priority_engine: PriorityEngine,
        content_queue: ContentQueue,
        word_repository,
        example_repository,
        best_option_repository,
    ):
        self.session = session

        self.priority_engine = priority_engine
        self.content_queue = content_queue

        self.word_repository = word_repository
        self.example_repository = example_repository
        self.best_option_repository = best_option_repository

    def ensure_ready(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> None:
        """
        Punto de entrada principal.

        Flujo:

            1. Asegurar LearningPath suficiente.
            2. Buscar contenido ya generado.
            3. Encolarlo.
            4. Actualizar cursor basándose en contenido encolado.
            5. Medir cuánto contenido falta.
            6. Si falta, solicitar generación background.

        Esto permite que el usuario reciba contenido inmediatamente
        siempre que exista suficiente contenido preparado.
        """

        self.ensure_path(
            user_id=user_id,
            content_type=content_type,
        )

        self.enqueue_existing_content(
            user_id=user_id,
            content_type=content_type,
        )

        # Actualizar cursor basándose en qué contenido fue encolado
        self.update_cursor_by_enqueued_content(
            user_id=user_id,
            content_type=content_type,
        )

        gap = self.calculate_content_gap(
            user_id=user_id,
            content_type=content_type,
        )

        if gap > 0:
            self.request_generation(
                user_id=user_id,
                content_type=content_type,
                amount=gap,
            )

    def ensure_path(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> None:
        """
        Garantiza que exista suficiente LearningPath futuro.

        Basándose en el CURSOR (hasta dónde preparamos contenido),
        verifica si hay suficiente look-ahead.

        No elimina palabras existentes del Path.

        Si ya existe suficiente look-ahead después del cursor:
            no hace nada.

        Si falta:
            crea un nuevo segmento.

        IMPORTANTE: Este método crea ESTRUCTURA (palabras en path).
        NO está limitado por wave-check. La wave-check solo aplica
        a request_generation() (generación de contenido).
        """

        # Obtener cursor actual
        cursor = self.session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == user_id,
                LearningPathCursor.type == content_type,
            )
        ).first()

        if not cursor:
            # Si no existe cursor, crear uno en el inicio
            cursor = LearningPathCursor(
                user_id=user_id,
                type=content_type,
                current_segment=0,
                current_position=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.session.add(cursor)
            self.session.commit()

        # Obtener palabras totales en path desde cursor en adelante
        total_path_items = self.session.exec(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.type == content_type,
            )
            .order_by(LearningPath.segment.asc(), LearningPath.position.asc())
        ).all()

        # Contar cuántas palabras hay DESPUÉS del cursor
        look_ahead_count = 0
        for path_item in total_path_items:
            is_after_cursor = (
                path_item.segment > cursor.current_segment or
                (path_item.segment == cursor.current_segment and
                 path_item.position > cursor.current_position)
            )
            if is_after_cursor:
                look_ahead_count += 1

        available_words = self.get_candidate_words(
            user_id=user_id,
            content_type=content_type,
        )

        logger.info(
            f"[ContentPlanner] ensure_path: found {len(available_words)} candidate words"
        )

        # Usar wave-based sizing para controlar la saturación
        target_look_ahead = self.calculate_segment_size_wave_based(
            user_id=user_id,
            available_word_count=len(available_words),
            content_type=content_type,
        )

        logger.info(
            f"[ContentPlanner] ensure_path for user {user_id} ({content_type}): "
            f"look_ahead={look_ahead_count}, target={target_look_ahead}, "
            f"candidates={len(available_words)}"
        )

        # Si no hay suficiente look-ahead, crear nuevo segmento
        if look_ahead_count < target_look_ahead:
            missing = target_look_ahead - look_ahead_count
            logger.info(
                f"[ContentPlanner] BUILDING: Creating {missing} new path items for user {user_id} ({content_type})"
            )

            result = self.build_segment(
                user_id=user_id,
                content_type=content_type,
                size=missing,
                candidates=available_words,
            )

            logger.info(
                f"[ContentPlanner] BUILD RESULT: created {len(result) if result else 0} path items"
            )
        else:
            logger.info(
                f"[ContentPlanner] SKIP BUILD: look_ahead ({look_ahead_count}) >= target ({target_look_ahead})"
            )

    def get_path_size(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> int:
        """
        Obtiene la cantidad de slots actualmente planificados.
        """

        statement = (
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.type == content_type,
            )
        )

        return len(
            self.session.exec(statement).all()
        )

    def get_next_segment_number(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> int:
        """
        Obtiene el siguiente número de segmento.
        Usar LearningPathCursor
        """
        from models import LearningPathCursor

        cursor = self.session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == user_id,
                LearningPathCursor.type == content_type,
            )
        ).first()

        if not cursor:
            # Crear cursor inicial
            cursor = LearningPathCursor(
                user_id=user_id,
                type=content_type,
                current_segment=0,
                current_position=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.session.add(cursor)
            self.session.commit()
            self.session.refresh(cursor)

        return cursor.current_segment + 1

    def calculate_segment_size(
        self,
        user_id: int,
        available_word_count: int,
    ) -> int:
        """
        Determina cuánto look-ahead crear.

        La idea es:

            pocas palabras
                -> segmento pequeño

            muchas palabras
                -> segmento progresivamente mayor

        Esto evita que un usuario que recién agregó una palabra
        termine con un LearningPath enorme y monótono.

        NOTA: Esta función está deprecada. Usar calculate_segment_size_wave_based() en su lugar.
        """

        if available_word_count <= 1:
            return 3

        if available_word_count <= 3:
            return 5

        if available_word_count <= 7:
            return 8

        if available_word_count <= 15:
            return 12

        if available_word_count <= 30:
            return 16

        return 20

    def calculate_path_saturation(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> Dict:
        """
        Analiza el estado actual del learning path.

        Calcula la "carga activa" basada en:
        - Palabras en LEARNING (peso 2.0)
        - Palabras en REINFORCING (peso 1.5)
        - Palabras en SPACING (peso 0.5)

        Retorna:
        {
            'saturation_level': float (0.0 a 1.0),
            'words_in_learning': int,
            'words_in_reinforcing': int,
            'words_in_spacing': int,
            'words_learned': int,
            'pending_in_queue': int,
            'can_accept_wave': bool,
            'wave_intensity': float (0.0 a 1.0),
            'active_load': float,
        }
        """

        # Contar palabras por estado
        stats_by_state = self.session.exec(
            select(
                WordStatistics.learning_state,
                func.count(WordStatistics.id).label('count')
            )
            .join(Word, Word.id == WordStatistics.word_id)
            .where(
                Word.user_id == user_id,
                WordStatistics.type == content_type,
                Word.is_active == True,
            )
            .group_by(WordStatistics.learning_state)
        ).all()

        state_counts = {state: count for state, count in stats_by_state}

        words_learning = state_counts.get(LearningState.LEARNING, 0)
        words_reinforcing = state_counts.get(LearningState.REINFORCING, 0)
        words_spacing = state_counts.get(LearningState.SPACING, 0)
        words_learned = state_counts.get(LearningState.LEARNED, 0)

        # Contar pendientes en queue
        pending_queue = self.session.exec(
            select(func.count(ContentQueueModel.id))
            .where(
                ContentQueueModel.user_id == user_id,
                ContentQueueModel.type == content_type,
                ContentQueueModel.status == ContentQueueStatus.PENDING,
            )
        ).first() or 0

        # Calcular saturación
        # Peso: LEARNING (x2) > REINFORCING (x1.5) > SPACING (x0.5)
        active_load = (
            (words_learning * 2.0) +
            (words_reinforcing * 1.5) +
            (words_spacing * 0.5)
        )

        # Máxima capacidad recomendada antes de bloquear
        # Con LEARNING (peso 2.0) + REINFORCING (peso 1.5) + SPACING (peso 0.5)
        # Para ~15 LEARNING + 5 REINFORCING = (15*2.0) + (5*1.5) = 37.5
        max_capacity = 35

        saturation = min(1.0, active_load / max_capacity)

        # Lógica de olas
        # Bloqueamos solo si REALMENTE muy saturado (>95%)
        # De otra forma permitimos olas pequeñas para mantener contenido disponible
        can_accept_wave = saturation < 0.95  # Acepta ola si < 95% (más permisivo)

        # Intensidad de la ola (inversamente proporcional a saturación)
        # Cuando saturación baja, olas grandes; cuando alta, olas muy pequeñas
        wave_intensity = max(0.05, 1.0 - saturation)  # Mínimo 5% de intensidad

        return {
            'saturation_level': saturation,
            'words_in_learning': words_learning,
            'words_in_reinforcing': words_reinforcing,
            'words_in_spacing': words_spacing,
            'words_learned': words_learned,
            'pending_in_queue': pending_queue,
            'can_accept_wave': can_accept_wave,
            'wave_intensity': wave_intensity,
            'active_load': active_load,
        }

    def calculate_segment_size_wave_based(
        self,
        user_id: int,
        available_word_count: int,
        content_type: ContentType,
    ) -> int:
        """
        Calcula tamaño del segmento basado en OLAS (wave-based intake).

        Controla la entrada de palabras nuevas según saturación del path:
        - Baja saturación (<30%): ola grande
        - Saturación media (30-70%): ola pequeña
        - Alta saturación (>70%): pausa (retorna 0)
        - PLUS: respeta límite máximo del path (~50 palabras)

        Esto simula pulsaciones de entrada vs consumo de contenido.
        """

        saturation_data = self.calculate_path_saturation(
            user_id, content_type
        )

        # Verificar tamaño actual del path
        current_path_size = self.get_path_size(user_id, content_type)
        max_path_size = 20  # Límite máximo del learning path

        # Contar palabras activas (LEARNING, REINFORCING, SPACING)
        # Ponderar SPACING con peso bajo (0.2) porque tiene prioridad muy baja
        # Esto permite que se intercalen palabras SPACING con LEARNING sin bloquear entrada
        active_words = (
            saturation_data['words_in_learning'] * 1.0 +
            saturation_data['words_in_reinforcing'] * 0.8 +
            saturation_data['words_in_spacing'] * 0.4
        )

        logger.info(
            f"[ContentPlanner] Wave check for user {user_id} ({content_type}): "
            f"path_size={current_path_size}/{max_path_size}, active_words={active_words}, "
            f"available_words={available_word_count}, saturation={saturation_data['saturation_level']:.2f}"
        )

        # OBJETIVO: mantener ~15-20 palabras ACTIVAS en aprendizaje
        # Algoritmo: "refill when depleting"
        # Si active_words <= 10 → agregar palabras nuevas AGRESIVAMENTE
        # (incluso si path_size > 20, porque hay muchas palabras LEARNED que no se usan)
        if active_words <= 10:
            logger.info(
                f"[ContentPlanner] Low active words ({active_words} <= 10) - FILLING path "
                f"(current path_size={current_path_size} has mostly LEARNED words)"
            )
            if available_word_count <= 5:
                return 5
            elif available_word_count <= 15:
                return 8
            else:
                return 10

        # LÍMITE DURO: si path está lleno Y hay suficientes palabras activas, no agregar más
        if current_path_size >= max_path_size:
            logger.info(
                f"[ContentPlanner] Path FULL for user {user_id} ({content_type}): "
                f"{current_path_size}/{max_path_size} and active_words={active_words} - blocking new words"
            )
            return 0

        # Si 10 < active_words < 15 → agregar moderadamente
        if active_words < 15:
            logger.info(
                f"[ContentPlanner] Medium active words ({active_words}) - moderate refill"
            )
            if available_word_count <= 10:
                return 2
            else:
                return 3

        # Si active_words >= 15 → pausar y dejar que usuario consuma
        logger.info(
            f"[ContentPlanner] High active words ({active_words}) - pausing new words"
        )
        return 0

    def get_candidate_words(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> List[Word]:
        """
        Obtiene las palabras que pueden participar en la planificación.

        No excluye automáticamente palabras LEARNED.

        Una palabra aprendida puede volver a aparecer como REVIEW
        cuando aumenta su necesidad por spaced repetition.

        La decisión final se realiza mediante PriorityEngine.
        """
        from models import Word

        words = self.session.exec(
            select(Word).where(
                Word.user_id == user_id,
                Word.is_active == True,
            )
        ).all()

        return words

    def get_expected_exposure(
        self,
        user_id: int,
        word_id: int,
        content_type: ContentType,
    ) -> float:
        """
        Calcula aproximadamente cuánto contenido futuro existe
        para una palabra.

        Incluye:

            - apariciones futuras en LearningPath
            - contenido PENDING relacionado con la palabra

        Esta métrica no representa exposición real.
        Representa exposición potencial.
        """

        path_items = self.session.exec(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.word_id == word_id,
                LearningPath.type == content_type,
            )
        ).all()

        return float(len(path_items))

    def score_candidates(
        self,
        user_id: int,
        words: List[Word],
        content_type: ContentType,
    ) -> List[Tuple[Word, float]]:
        """
        Calcula la prioridad de todas las palabras candidatas.

        Retorna:

            [
                (word_a, 0.92),
                (word_b, 0.81),
                ...
            ]

        No modifica el LearningPath.
        """

        result = []

        now = datetime.now(timezone.utc)

        # Contar palabras en estado SPACING para ajuste dinámico de prioridad
        spacing_words_count = self.session.exec(
            select(func.count(WordStatistics.id))
            .join(Word, Word.id == WordStatistics.word_id)
            .where(
                Word.user_id == user_id,
                WordStatistics.type == content_type,
                WordStatistics.learning_state == LearningState.SPACING,
                Word.is_active == True,
            )
        ).first() or 0

        for word in words:
            statistics = self.get_statistics(
                word_id=word.id,
                content_type=content_type,
            )

            # Excluir palabras en estado LEARNED - nunca deben aparecer en el path
            if statistics.learning_state == LearningState.LEARNED:
                continue

            expected_exposure = self.get_expected_exposure(
                user_id=user_id,
                word_id=word.id,
                content_type=content_type,
            )

            priority = self.priority_engine.calculate_priority(
                word=word,
                statistics=statistics,
                now=now,
                expected_exposure=expected_exposure,
                spacing_words_count=spacing_words_count,
            )

            result.append(
                (word, priority)
            )

        result.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        return result

    def get_statistics(
        self,
        word_id: int,
        content_type: ContentType,
    ) -> WordStatistics:
        """
        Obtiene las estadísticas de una palabra.

        Si todavía no existen, crea el estado NEW.
        """

        statistics = self.session.exec(
            select(WordStatistics)
            .where(
                WordStatistics.word_id == word_id,
                WordStatistics.type == content_type,
            )
        ).first()

        if statistics:
            return statistics

        statistics = WordStatistics(
            word_id=word_id,
            type=content_type,
            learning_state=LearningState.NEW,
            times_seen=0,
            current_cycle_seen=0,
            created_at=datetime.now(timezone.utc),
        )

        self.session.add(statistics)
        self.session.commit()
        self.session.refresh(statistics)

        return statistics

    def build_segment(
        self,
        user_id: int,
        content_type: ContentType,
        size: int,
        candidates: List[Word],
    ) -> List[LearningPath]:
        """
        Construye un segmento completo mezclando:

        - Palabras con prioridad alta (ya vistas, necesitan refuerzo)
        - Palabras nuevas (intercaladas aleatoriamente)

        La proporción de nuevas depende de cuántas haya disponibles.

        Flujo:
        1. Separar candidatos en NEW vs NO_NEW
        2. Calcular cuántos slots reservar para nuevas
        3. Intercalar aleatoriamente los slots
        4. Construir segmento respetando la intercalación

        La misma palabra puede aparecer múltiples veces dentro del
        segmento, con penalización por saturación.
        """

        scored = self.score_candidates(
            user_id=user_id,
            words=candidates,
            content_type=content_type,
        )

        if not scored:
            return []

        segment = self.get_next_segment_number(
            user_id=user_id,
            content_type=content_type,
        )

        # Paso 1: Separar palabras NEW de NO_NEW
        new_words = []
        not_new_words = []

        for word, priority in scored:
            stats = self.get_statistics(word.id, content_type)
            if stats.learning_state == LearningState.NEW:
                new_words.append((word, priority))
            else:
                not_new_words.append((word, priority))

        # Paso 2: Calcular slots para palabras nuevas
        new_slots = self._calculate_new_word_slots(
            size=size,
            new_word_count=len(new_words),
        )

        # Paso 3: Intercalar aleatoriamente los slots para nuevas
        import random
        all_positions = list(range(size))
        new_positions = set(random.sample(all_positions, min(new_slots, size)))

        # Paso 4: Construir segmento
        selected: List[Word] = []
        path_items: List[LearningPath] = []

        for position in range(size):
            # Decidir si esta posición es para palabra nueva o prioritaria
            if position in new_positions and new_words:
                candidates_pool = new_words
            else:
                candidates_pool = not_new_words if not_new_words else new_words

            word = self.select_word_for_slot(
                candidates=candidates_pool,
                selected=selected,
            )

            if word is None:
                break

            selected.append(word)

            item = LearningPath(
                user_id=user_id,
                type=content_type,
                word_id=word.id,
                segment=segment,
                position=position,
                created_at=datetime.now(timezone.utc),
            )

            self.session.add(item)
            path_items.append(item)

            history = LearningPathHistory(
                user_id=user_id,
                type=content_type,
                word_id=word.id,
                segment=segment,
                position=position,
                created_at=datetime.now(timezone.utc),
            )

            self.session.add(history)

        self.session.commit()

        return path_items

    def _calculate_new_word_slots(
        self,
        size: int,
        new_word_count: int,
    ) -> int:
        """
        Calcula cuántos slots reservar para palabras nuevas.

        Lógica:
        - Si hay pocas nuevas: reservar menos slots
        - Si hay muchas nuevas: reservar más slots
        - Máximo: 25% del segmento (más conservador, enfoque en refuerzo)
        """

        if new_word_count == 0:
            return 0

        if new_word_count <= 2:
            return max(1, int(size * 0.10))

        if new_word_count <= 5:
            return max(2, int(size * 0.15))

        if new_word_count <= 10:
            return max(3, int(size * 0.20))

        return max(4, int(size * 0.25))

    def select_word_for_slot(
        self,
        candidates: List[Tuple[Word, float]],
        selected: List[Word],
    ) -> Optional[Word]:
        """
        Selecciona una palabra para un slot.

        La prioridad no determina una posición fija.

        Se utiliza una distribución ponderada para permitir
        cierta aleatoriedad.

        Además se reduce la probabilidad de una palabra
        cuanto más veces ya haya aparecido en el segmento.

        Esto produce algo como:

            A
            B
            A
            C
            D
            A
            B
            E

        en lugar de:

            A
            A
            A
            A
            B
            C
            D
        """

        if not candidates:
            return None

        weighted = []

        for word, priority in candidates:
            occurrences = sum(
                1
                for selected_word in selected
                if selected_word.id == word.id
            )

            # Saturación suave.
            saturation = 1.0 / (1.0 + occurrences)

            weight = max(
                0.001,
                priority * saturation,
            )

            weighted.append(
                (word, weight)
            )

        total = sum(
            weight
            for _, weight in weighted
        )

        if total <= 0:
            return candidates[0][0]

        import random

        value = random.uniform(
            0,
            total,
        )

        accumulated = 0.0

        for word, weight in weighted:
            accumulated += weight

            if value <= accumulated:
                return word

        return weighted[-1][0]

    def persist_segment(
        self,
        user_id: int,
        content_type: ContentType,
        words: List[Word],
        segment: int,
    ) -> None:
        """
        Método auxiliar para persistir un segmento.

        Si build_segment ya realiza la persistencia directamente,
        este método puede omitirse.

        Se deja separado porque puede ser útil si posteriormente
        quieres construir el segmento primero en memoria y luego
        persistirlo en una única transacción.
        """

        for position, word in enumerate(words):
            item = LearningPath(
                user_id=user_id,
                type=content_type,
                word_id=word.id,
                segment=segment,
                position=position,
                created_at=datetime.now(timezone.utc),
            )

            history = LearningPathHistory(
                user_id=user_id,
                type=content_type,
                word_id=word.id,
                segment=segment,
                position=position,
                created_at=datetime.now(timezone.utc),
            )

            self.session.add(item)
            self.session.add(history)

        self.session.commit()

    def enqueue_existing_content(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> int:
        """
        Busca contenido que ya existe pero todavía no está
        en ContentQueue.

        Encola SOLO lo necesario:
        - Respetando el CURSOR (no encola más allá de donde preparamos)
        - Basándose en el gap de contenido (cuánto falta en queue)

        Itera el LearningPath desde el cursor en adelante
        hasta alcanzar el target de queue.

        Para cada palabra, busca UN SOLO contenido disponible
        (el más antiguo por sequence) y lo encola.

        Sin consumir tokens innecesarios.
        """
        from models import Example, BestOption

        pending_count = 0

        # Obtener cursor
        cursor = self.session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == user_id,
                LearningPathCursor.type == content_type,
            )
        ).first()

        if not cursor:
            logger.debug(f"[ContentPlanner] No cursor found for user {user_id} ({content_type})")
            return 0

        # Calcular cuánto contenido falta
        target = self.calculate_queue_target(user_id, content_type)
        pending = self.content_queue.count_pending(user_id, content_type)
        gap = self.calculate_content_gap(user_id, content_type)

        logger.info(
            f"[ContentPlanner] enqueue_existing_content for user {user_id} ({content_type}): "
            f"target={target}, pending={pending}, gap={gap}"
        )

        if gap <= 0:
            # Ya hay suficiente contenido en queue
            logger.debug(
                f"[ContentPlanner] Sufficient content in queue (gap={gap}), skipping enqueue"
            )
            return 0

        # Obtener el LearningPath ordenado
        all_path_items = self.session.exec(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.type == content_type,
            )
            .order_by(LearningPath.segment.asc(), LearningPath.position.asc())
        ).all()

        # Filtrar solo items DESPUÉS del cursor
        path_items_to_process = []
        for path_item in all_path_items:
            is_after_cursor = (
                path_item.segment > cursor.current_segment or
                (path_item.segment == cursor.current_segment and
                 path_item.position > cursor.current_position)
            )
            if is_after_cursor:
                path_items_to_process.append(path_item)

        # Iterar el LearningPath en orden, solo hasta llenar el gap
        logger.debug(
            f"[ContentPlanner] Processing {len(path_items_to_process)} path items to fill gap={gap}"
        )

        for path_item in path_items_to_process:
            if pending_count >= gap:
                logger.debug(f"[ContentPlanner] Reached target pending_count={pending_count}, stopping")
                break

            word_id = path_item.word_id
            logger.debug(f"[ContentPlanner] Looking for content for word_id={word_id}")

            # Obtener UN SOLO contenido disponible para esta palabra
            if content_type == ContentType.EXAMPLE:
                content_id = (
                    self.example_repository
                    .get_available_content_for_word(word_id)
                )
            elif content_type == ContentType.BEST_OPTIONS:
                content_id = (
                    self.best_option_repository
                    .get_available_content_for_word(word_id)
                )
            else:
                content_id = None

            if content_id is None:
                continue

            # Encolar y marcar como encolado
            if not self.content_queue.is_pending(
                user_id=user_id,
                content_type=content_type,
                content_id=content_id,
            ):
                self.content_queue.enqueue(
                    user_id=user_id,
                    content_type=content_type,
                    content_id=content_id,
                )
                pending_count += 1

                # Marcar el contenido como encolado
                if content_type == ContentType.EXAMPLE:
                    example = self.session.get(Example, content_id)
                    if example:
                        example.enqueued = True
                        self.session.add(example)
                elif content_type == ContentType.BEST_OPTIONS:
                    best_option = self.session.get(BestOption, content_id)
                    if best_option:
                        best_option.enqueued = True
                        self.session.add(best_option)

        self.session.commit()

        # FALLBACK: Si no pudimos enqueuear nada pero hay gap, buscar ejemplos disponibles
        # de cualquier palabra (emergency case cuando el path está completamente saturado)
        if pending_count == 0 and gap > 0:
            logger.info(
                f"[ContentPlanner] Fallback: no path items found but gap={gap}. "
                f"Searching available content from active words (balanced by priority)..."
            )

            # Obtener palabras del path actual CON sus estadísticas de aprendizaje
            path_word_ids = set(
                self.session.exec(
                    select(LearningPath.word_id)
                    .where(
                        LearningPath.user_id == user_id,
                        LearningPath.type == content_type,
                    )
                ).all()
            )

            # Obtener palabras con su estado de aprendizaje
            user_words_with_stats = self.session.exec(
                select(Word, WordStatistics)
                .join(WordStatistics,
                      (Word.id == WordStatistics.word_id) &
                      (WordStatistics.type == content_type))
                .where(
                    Word.user_id == user_id,
                    Word.is_active == True,
                    Word.id.in_(path_word_ids) if path_word_ids else True,
                )
            ).all()

            # Ordenar por prioridad de learning_state
            # LEARNING > REINFORCING > SPACING > LEARNED > REVIEW
            priority_order = {
                LearningState.LEARNING: 0,
                LearningState.REINFORCING: 1,
                LearningState.SPACING: 2,
                LearningState.LEARNED: 3,
                LearningState.REVIEW: 4,
                LearningState.NEW: 5,
            }

            user_words_in_path = sorted(
                [word for word, _ in user_words_with_stats],
                key=lambda w: (
                    priority_order.get(self.get_statistics(w.id, content_type).learning_state, 99),
                    w.id
                )
            )

            found_in_fallback = 0
            round_num = 0

            # Round-robin: en cada ronda, buscar 1 ejemplo de cada palabra
            # Esto asegura distribución balanceada
            while pending_count < gap and round_num < 5:  # máximo 5 rondas
                round_num += 1
                enqueued_in_round = 0

                for word in user_words_in_path:
                    if pending_count >= gap:
                        break

                    # Buscar UN ejemplo disponible para esta palabra
                    if content_type == ContentType.EXAMPLE:
                        content_id = self.example_repository.get_available_content_for_word(word.id)
                    elif content_type == ContentType.BEST_OPTIONS:
                        content_id = self.best_option_repository.get_available_content_for_word(word.id)
                    else:
                        content_id = None

                    if content_id is None:
                        continue  # Sin contenido disponible para esta palabra

                    # Encolar si no está ya encolado
                    if not self.content_queue.is_pending(user_id, content_type, content_id):
                        self.content_queue.enqueue(user_id, content_type, content_id)
                        pending_count += 1
                        found_in_fallback += 1
                        enqueued_in_round += 1

                        # Marcar como encolado
                        if content_type == ContentType.EXAMPLE:
                            example = self.session.get(Example, content_id)
                            if example:
                                example.enqueued = True
                                self.session.add(example)
                        elif content_type == ContentType.BEST_OPTIONS:
                            best_option = self.session.get(BestOption, content_id)
                            if best_option:
                                best_option.enqueued = True
                                self.session.add(best_option)

                if enqueued_in_round == 0:
                    break  # Ninguna palabra tiene más contenido disponible

                logger.debug(
                    f"[ContentPlanner] Fallback round {round_num}: enqueued {enqueued_in_round} items"
                )

            if found_in_fallback > 0:
                logger.info(
                    f"[ContentPlanner] Fallback: successfully enqueued {found_in_fallback} items "
                    f"across {round_num} balanced rounds (total: {pending_count})"
                )
                self.session.commit()
            else:
                logger.warning(
                    f"[ContentPlanner] Fallback: no available content found for user {user_id} ({content_type})"
                )

        return pending_count

    def calculate_content_gap(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> int:
        """
        Calcula cuánto contenido falta para alcanzar
        el buffer objetivo.

        Ejemplo:

            target = 15
            pending = 9

            gap = 6
        """

        target = self.calculate_queue_target(
            user_id=user_id,
            content_type=content_type,
        )

        pending = self.content_queue.count_pending(
            user_id=user_id,
            content_type=content_type,
        )

        return max(
            0,
            target - pending,
        )

    def calculate_queue_target(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> int:
        """
        Determina cuánto contenido preparado queremos mantener.

        Puede evolucionar posteriormente para utilizar:

            - tamaño del LearningPath
            - velocidad de consumo
            - tiempo de generación de AI
            - cantidad de palabras
            - historial del usuario

        Por ahora mantiene un buffer relativamente pequeño.
        """

        path_size = self.get_path_size(
            user_id=user_id,
            content_type=content_type,
        )

        if path_size <= 5:
            return 5

        if path_size <= 10:
            return 8

        if path_size <= 20:
            return 12

        return 15

    def plan_best_option_generation(self, user_id: int, amount: int) -> None:
        """
        Planifica generación de best_options para la ventana actual del LearningPath.
        """
        from best_options.best_options_generator import BestOptionGenerator
        from best_options.best_options_repository import BestOptionRepository

        if amount <= 0:
            return

        generation_words = self.get_generation_words(
            user_id=user_id,
            content_type=ContentType.BEST_OPTIONS,
        )

        if not generation_words:
            return

        # Filtrar palabras que realmente necesitan generación
        best_option_repo = BestOptionRepository(self.session)
        words_needing_generation = []

        for word in generation_words:
            available_count = best_option_repo.count_available_best_options_for_word(word.id)
            if available_count < 2:
                words_needing_generation.append(word)
            else:
                logger.debug(
                    f"[ContentPlanner] Word {word.id} ({word.main}) already has {available_count} available best options, skipping"
                )

        if not words_needing_generation:
            logger.info(
                f"[ContentPlanner] No words need best_options generation (all have >= 2 available)"
            )
            return

        word_ids = [w.id for w in words_needing_generation]

        logger.info(
            f"[ContentPlanner] Requesting best_options generation for {len(word_ids)} words"
        )

        # Solicitar generación de best options solo para palabras que lo necesitan
        BestOptionGenerator.generate(
            user_id=user_id,
            word_ids=word_ids,
        )

    def plan_generation(
        self,
        user_id: int,
        content_type: ContentType,
        amount: int,
    ) -> None:
        """
        Decide qué tipo de generación hace falta.

        Example:
            genera examples directos y mixed.

        Best options:
            genera preguntas.

        Esta función sólo planifica.

        La generación real debería ejecutarse en background.
        """

        if amount <= 0:
            return

        if content_type == ContentType.EXAMPLE:
            self.plan_example_generation(
                user_id=user_id,
                amount=amount,
            )

        elif content_type == ContentType.BEST_OPTIONS:
            self.plan_best_option_generation(
                user_id=user_id,
                amount=amount,
            )

    def request_generation(
        self,
        user_id: int,
        content_type: ContentType,
        amount: int,
    ) -> None:
        """
        Punto de entrada para solicitar generación background.

        Antes de crear un nuevo job debería comprobarse
        que no exista una generación activa.

        La implementación concreta puede utilizar Celery,
        Redis, una cola propia, etc.
        """

        if amount <= 0:
            return

        if self.is_generation_running(
            user_id=user_id,
            content_type=content_type,
        ):
            return

        self.plan_generation(
            user_id=user_id,
            content_type=content_type,
            amount=amount,
        )

    def is_generation_running(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> bool:
        """
        Determina si ya existe una generación activa.

        Esto evita que múltiples requests del usuario
        disparen simultáneamente la misma generación.
        """

        # Aquí conectarías con GenerationQueueMonitor
        # o con tu sistema real de jobs.

        return False

    def plan_example_generation(self, user_id: int, amount: int) -> None:
        """
        Planifica examples simples y mixed para la ventana actual del
        LearningPath.

        La proporción de mixed aumenta según la diversidad disponible.
        Con pocas words se priorizan examples simples; a medida que
        aumenta la diversidad se incorporan más mixed.

        Los examples simples deben reutilizar primero contenido de
        reserva disponible y generar con AI solo si realmente hace falta.

        La generación de AI debe ejecutarse en background.
        """
        from examples.example_generator import ExampleGenerator
        from examples.example_repository import ExampleRepository

        if amount <= 0:
            return

        generation_words = self.get_generation_words(
            user_id=user_id,
            content_type=ContentType.EXAMPLE,
        )

        if not generation_words:
            return

        # Filtrar palabras que realmente necesitan generación
        # (descartar aquellas que ya tienen suficientes ejemplos disponibles)
        example_repo = ExampleRepository(self.session)
        words_needing_generation = []

        for word in generation_words:
            available_count = example_repo.count_available_examples_for_word(word.id)
            if available_count < 3:
                words_needing_generation.append(word)
            else:
                logger.debug(
                    f"[ContentPlanner] Word {word.id} ({word.main}) already has {available_count} available examples, skipping"
                )

        if not words_needing_generation:
            logger.info(
                f"[ContentPlanner] No words need generation (all have >= 3 available examples)"
            )
            return

        word_count = len(words_needing_generation)

        # Decidir proporción simple vs mixed según diversidad
        if word_count <= 1:
            simple_ratio = 1.0
        elif word_count <= 3:
            simple_ratio = 0.8
        elif word_count <= 7:
            simple_ratio = 0.6
        else:
            simple_ratio = 0.4

        simple_amount = max(1, int(amount * simple_ratio))
        mixed_amount = amount - simple_amount

        # Solicitar generación simple solo para palabras que lo necesitan
        if simple_amount > 0:
            word_ids = [w.id for w in words_needing_generation]
            logger.info(
                f"[ContentPlanner] Requesting generation for {len(word_ids)} words (simple_amount={simple_amount})"
            )
            ExampleGenerator.generate_simple(
                user_id=user_id,
                word_ids=word_ids,
                amount=simple_amount,
            )

        # TODO: Mixed examples generation temporarily disabled - focusing on simple examples only
        # if mixed_amount > 0:
        #     mixed_words = self.get_mixed_candidate_words(user_id=user_id)
        #     if mixed_words:
        #         word_ids = [w.id for w in mixed_words]
        #         ExampleGenerator.generate_mixed(
        #             user_id=user_id,
        #             word_ids=word_ids,
        #             amount=mixed_amount,
        #         )

    def get_generation_words(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> List[Word]:
        """
        Obtiene palabras únicamente desde la ventana
        actual del LearningPath.

        Esto mantiene la generación alineada con el
        momento actual del aprendizaje.
        """
        from models import LearningPath, LearningPathCursor, Word

        cursor = self.session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == user_id,
                LearningPathCursor.type == content_type,
            )
        ).first()

        if not cursor:
            return []

        current_segment = cursor.current_segment

        # Obtener palabras del segmento actual
        path_items = self.session.exec(
            select(LearningPath).where(
                LearningPath.user_id == user_id,
                LearningPath.type == content_type,
                LearningPath.segment == current_segment,
            )
        ).all()

        word_ids = [item.word_id for item in path_items]

        if not word_ids:
            return []

        words = self.session.exec(
            select(Word).where(Word.id.in_(word_ids))
        ).all()

        return words

    def get_mixed_candidate_words(
        self,
        user_id: int,
    ) -> List[Word]:
        """
        Obtiene palabras de la ventana actual del Path.

        La ventana contiene deliberadamente:

            pasado reciente
            +
            presente
            +
            futuro cercano

        De esta manera los mixed examples pueden combinar
        palabras que el usuario acaba de ver con palabras
        que está a punto de encontrar.
        """
        from models import LearningPath, LearningPathCursor, Word

        cursor = self.session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == user_id,
                LearningPathCursor.type == ContentType.EXAMPLE,
            )
        ).first()

        if not cursor:
            return []

        current_segment = cursor.current_segment

        # Ventana: segmento anterior, actual, y próximo
        segments = [
            current_segment - 1,
            current_segment,
            current_segment + 1,
        ]

        path_items = self.session.exec(
            select(LearningPath).where(
                LearningPath.user_id == user_id,
                LearningPath.type == ContentType.EXAMPLE,
                LearningPath.segment.in_(segments),
            )
        ).all()

        word_ids = list(set([item.word_id for item in path_items]))

        if not word_ids:
            return []

        words = self.session.exec(
            select(Word).where(Word.id.in_(word_ids))
        ).all()

        return words

    def register_generated_mixed_examples(
        self,
        user_id: int,
        examples: List,
    ) -> None:
        """
        Procesa mixed examples generados por AI.

        Para cada example:

            1. Se guarda el Example.
            2. Se guardan sus ExampleWord.
            3. Se identifica qué palabras fueron utilizadas realmente.
            4. Se agrega el contenido a ContentQueue.

        No modifica el LearningPath existente.

        Esto es importante porque el Path debe mantenerse estable.
        """

        for example in examples:

            # El repository debería encargarse de persistir
            # el Example y sus ExampleWord.
            saved_example = (
                self.example_repository.save(
                    example
                )
            )

            self.content_queue.enqueue(
                user_id=user_id,
                content_type=ContentType.EXAMPLE,
                content_id=saved_example.id,
            )

    def update_cursor_by_enqueued_content(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> None:
        """
        Actualiza el cursor basándose en cuáles palabras del path
        ya tienen contenido encolado/preparado.

        El cursor marca la posición más alta del path cuya palabra
        tiene al menos un contenido pendiente encolado.

        Flujo:
        1. Obtener todos los items del path ordenados (segment, position)
        2. Para cada path_item, verificar si su palabra tiene contenido pending
        3. Encontrar la posición más alta con contenido
        4. Actualizar cursor a esa posición
        """
        from models import ContentQueue

        cursor = self.session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == user_id,
                LearningPathCursor.type == content_type,
            )
        ).first()

        if not cursor:
            return

        # Obtener todos los items del path ordenados
        path_items = self.session.exec(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.type == content_type,
            )
            .order_by(LearningPath.segment.asc(), LearningPath.position.asc())
        ).all()

        if not path_items:
            return

        # Obtener todos los word_ids del path que tienen contenido pending
        pending_queue_items = self.session.exec(
            select(ContentQueue).where(
                ContentQueue.user_id == user_id,
                ContentQueue.type == content_type,
                ContentQueue.status == "PENDING",
            )
        ).all()

        pending_word_ids = set()
        for item in pending_queue_items:
            # Obtener el word_id del contenido encolado
            word_ids = self._get_content_word_ids(
                content_type=content_type,
                content_id=item.content_id,
            )
            pending_word_ids.update(word_ids)

        if not pending_word_ids:
            return

        # Encontrar la posición máxima del path cuya palabra tiene contenido
        max_segment = 0
        max_position = 0

        for path_item in path_items:
            if path_item.word_id in pending_word_ids:
                max_segment = path_item.segment
                max_position = path_item.position

        # Actualizar cursor a la posición más alta con contenido
        if (max_segment > cursor.current_segment or
            (max_segment == cursor.current_segment and max_position > cursor.current_position)):
            cursor.current_segment = max_segment
            cursor.current_position = max_position
            cursor.updated_at = datetime.now(timezone.utc)
            self.session.add(cursor)
            self.session.commit()

    def _get_content_word_ids(
        self,
        content_type: ContentType,
        content_id: int,
    ) -> list:
        """Obtiene los word_ids asociados a un contenido"""
        from models import Example, BestOption, ExampleWord

        if content_type == ContentType.EXAMPLE:
            example_words = self.session.exec(
                select(ExampleWord).where(ExampleWord.example_id == content_id)
            ).all()
            return [ew.word_id for ew in example_words]

        elif content_type == ContentType.BEST_OPTIONS:
            best_option = self.session.get(BestOption, content_id)
            if best_option:
                return [best_option.word_id]

        return []

    def start_next_segment_if_needed(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> None:
        """
        Cuando el usuario ha consumido suficiente Path,
        garantiza que exista un siguiente segmento.

        No destruye el segmento anterior.

        Simplemente genera look-ahead adicional.
        """

        self.ensure_path(
            user_id=user_id,
            content_type=content_type,
        )