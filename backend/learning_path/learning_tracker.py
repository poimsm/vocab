from datetime import datetime, timezone
from typing import List
from sqlmodel import Session, select
from models import (
    Word,
    WordStatistics,
    LearningState,
    ContentType,
    LearningPathCursor,
    LearningPath,
)


class LearningTracker:
    """
    Registra lo que realmente ocurrió con el usuario.

    Esta clase trabaja con EXPOSICIONES REALES.

    Esto es diferente de ContentPlanner, que trabaja con
    exposiciones PLANIFICADAS/ESPERADAS.
    """

    def __init__(
        self,
        session: Session,
        example_repository,
        best_option_repository,
    ):
        self.session = session
        self.example_repository = example_repository
        self.best_option_repository = best_option_repository

    def record_exposure(
        self,
        user_id: int,
        content_type: ContentType,
        content_id: int,
    ) -> None:
        """
        Registra que el usuario realmente consumió un contenido.

        Obtiene las palabras asociadas al contenido y actualiza
        sus estadísticas.

        Para un Example:

            Example
              ↓
            ExampleWord
              ↓
            Word A
            Word B

        Para BestOption:

            BestOption
              ↓
            Word asociada

        Cada palabra recibe una exposición real.

        NOTA: El cursor NO se actualiza aquí.
        El cursor avanza cuando se GENERA contenido, no cuando se consume.
        """

        word_ids = self.get_content_word_ids(
            content_type=content_type,
            content_id=content_id,
        )

        for word_id in word_ids:
            self.record_word_exposure(
                word_id=word_id,
                content_type=content_type,
            )

    def get_content_word_ids(
        self,
        content_type: ContentType,
        content_id: int,
    ) -> List[int]:
        """
        Determina qué palabras están asociadas al contenido.

        La diferencia entre Example y Mixed Example se resuelve
        naturalmente mediante ExampleWord.

        Un Example puede tener:

            [word_a]

        o:

            [word_a, word_b]
        """

        if content_type == ContentType.EXAMPLE:
            return self.example_repository.get_word_ids(
                content_id
            )

        if content_type == ContentType.BEST_OPTIONS:
            word_id = self.best_option_repository.get_word_id(
                content_id
            )

            return [word_id] if word_id else []

        return []

    def record_word_exposure(
        self,
        word_id: int,
        content_type: ContentType,
    ) -> None:
        """
        Registra una exposición real para una palabra y tipo
        de contenido.

        times_seen:
            histórico absoluto.

        current_cycle_seen:
            contador del ciclo actual.

        last_seen_at:
            última exposición real.
        """

        statistics = self.session.exec(
            select(WordStatistics)
            .where(
                WordStatistics.word_id == word_id,
                WordStatistics.type == content_type,
            )
        ).first()

        if statistics is None:
            statistics = WordStatistics(
                word_id=word_id,
                type=content_type,
                learning_state=LearningState.NEW,
                times_seen=0,
                current_cycle_seen=0,
                created_at=datetime.now(timezone.utc),
            )

            self.session.add(statistics)

        statistics.times_seen += 1
        statistics.current_cycle_seen += 1
        statistics.last_seen_at = datetime.now(timezone.utc)

        statistics.learning_state = self.calculate_learning_state(
            statistics
        )

        self.session.add(statistics)
        self.session.commit()

    def calculate_learning_state(
        self,
        statistics: WordStatistics,
    ) -> LearningState:
        """
        Determina el estado actual de aprendizaje con spaced repetition.

        Flujo de estados:
        - NEW (0 veces): Palabra recién creada
        - LEARNING (1 vez): Fijación inicial en memoria
        - REINFORCING (2-3 veces): Refuerzo moderado
        - SPACING (4-5 veces): Fase de espaciamiento prolongado (baja urgencia)
        - LEARNED (6+ veces): Aprendida, listo para revisión ocasional
        - REVIEW: Estado sticky, se mantiene indefinidamente
        """

        if statistics.times_seen == 0:
            return LearningState.NEW

        if statistics.learning_state == LearningState.REVIEW:
            return LearningState.REVIEW

        if statistics.times_seen < 2:
            return LearningState.LEARNING

        if statistics.times_seen <= 4:
            return LearningState.REINFORCING

        if statistics.times_seen <= 5:
            return LearningState.SPACING

        return LearningState.LEARNED

