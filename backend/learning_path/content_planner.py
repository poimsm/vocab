from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlmodel import Session, select
from models import (
    Word,
    WordStatistics,
    LearningPath,
    LearningPathHistory,
    LearningPathCursor,
    ContentType,
    LearningState,
)
from learning_path.priority_engine import PriorityEngine
from learning_path.content_queue import ContentQueue


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
            4. Medir cuánto contenido falta.
            5. Si falta, solicitar generación background.

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

        No elimina palabras existentes del Path.

        Si ya existe suficiente look-ahead:
            no hace nada.

        Si falta:
            crea un nuevo segmento.

        La cantidad de look-ahead puede crecer según
        la cantidad de palabras disponibles.
        """

        current_size = self.get_path_size(
            user_id=user_id,
            content_type=content_type,
        )

        available_words = self.get_candidate_words(
            user_id=user_id,
            content_type=content_type,
        )

        target_size = self.calculate_segment_size(
            user_id=user_id,
            available_word_count=len(available_words),
        )

        if current_size >= target_size:
            return

        missing = target_size - current_size

        self.build_segment(
            user_id=user_id,
            content_type=content_type,
            size=missing,
            candidates=available_words,
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
                current_segment=1,
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

        for word in words:
            statistics = self.get_statistics(
                word_id=word.id,
                content_type=content_type,
            )

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
        Construye un segmento completo.

        La misma palabra puede aparecer múltiples veces.

        La selección combina:

            prioridad
            repetición dentro del segmento
            aleatoriedad

        Una palabra con prioridad alta puede aparecer varias veces,
        pero existe una penalización por saturación para evitar
        que monopolice el segmento.
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

        selected: List[Word] = []
        path_items: List[LearningPath] = []

        for position in range(size):
            word = self.select_word_for_slot(
                candidates=scored,
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

        Esta operación debe ocurrir ANTES de pedir nueva
        generación a la AI.

        Así puedes tener:

            AI generó anteriormente
                ↓
            contenido almacenado
                ↓
            todavía no estaba en queue
                ↓
            ahora se reutiliza

        sin consumir tokens nuevamente.
        """

        pending_count = 0

        if content_type == ContentType.EXAMPLE:
            content_ids = (
                self.example_repository
                .get_available_content_for_path(
                    user_id=user_id,
                )
            )

        elif content_type == ContentType.BEST_OPTIONS:
            content_ids = (
                self.best_option_repository
                .get_available_content_for_path(
                    user_id=user_id,
                )
            )

        else:
            content_ids = []

        for content_id in content_ids:
            if self.content_queue.is_pending(
                user_id=user_id,
                content_type=content_type,
                content_id=content_id,
            ):
                continue

            self.content_queue.enqueue(
                user_id=user_id,
                content_type=content_type,
                content_id=content_id,
            )

            pending_count += 1

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

        if amount <= 0:
            return

        generation_words = self.get_generation_words(
            user_id=user_id,
            content_type=ContentType.BEST_OPTIONS,
        )

        if not generation_words:
            return

        word_ids = [w.id for w in generation_words]

        # Solicitar generación de best options
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

        if amount <= 0:
            return

        generation_words = self.get_generation_words(
            user_id=user_id,
            content_type=ContentType.EXAMPLE,
        )

        if not generation_words:
            return

        word_count = len(generation_words)

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

        # Solicitar generación simple
        if simple_amount > 0:
            word_ids = [w.id for w in generation_words]
            ExampleGenerator.generate_simple(
                user_id=user_id,
                word_ids=word_ids,
                amount=simple_amount,
            )

        # Solicitar generación mixed
        if mixed_amount > 0:
            mixed_words = self.get_mixed_candidate_words(user_id=user_id)
            if mixed_words:
                word_ids = [w.id for w in mixed_words]
                ExampleGenerator.generate_mixed(
                    user_id=user_id,
                    word_ids=word_ids,
                    amount=mixed_amount,
                )

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