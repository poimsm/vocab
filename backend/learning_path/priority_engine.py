from datetime import datetime, timezone
from typing import Optional, List, Tuple

from sqlmodel import Session, select

# Importa tus modelos reales
from models import (
    Word,
    WordStatistics,
    LearningState,
    ContentType,
    LearningPath,
    LearningPathHistory,
    ContentQueue,
    ContentQueueStatus,
)


class PriorityEngine:
    """
    Calcula la necesidad/prioridad actual de una palabra.

    Esta clase NO modifica la base de datos.
    NO crea LearningPath.
    NO genera contenido.

    Su única responsabilidad es transformar el estado actual
    de una palabra en métricas útiles para el ContentPlanner.
    """

    def calculate_priority(
        self,
        word: Word,
        statistics: WordStatistics,
        now: Optional[datetime] = None,
        expected_exposure: float = 0.0,
    ) -> float:
        """
        Calcula la prioridad final de la palabra.

        La prioridad combina:

        - necesidad según learning_state
        - urgencia por spaced repetition
        - prioridad de palabra nueva
        - boost explícito del usuario
        - penalización por exposición reciente
        - penalización por contenido/exposición ya planificada

        El resultado está limitado entre 0.0 y 1.0.

        expected_exposure representa contenido que ya se espera
        que contribuya a la exposición futura de la palabra.

        Importante:
        no significa que la palabra esté aprendida o no.
        Sólo representa qué tan conveniente es volver a planificarla.
        """

        now = now or datetime.now(timezone.utc)

        learning_need = self.calculate_learning_need(statistics)
        review_urgency = self.calculate_review_urgency(
            statistics,
            now,
        )
        new_word_boost = self.calculate_new_word_boost(
            statistics,
        )
        user_boost = self.calculate_user_boost(word)
        recent_penalty = self.calculate_recent_exposure_penalty(
            statistics,
            now,
        )
        expected_penalty = self.calculate_expected_exposure_penalty(
            expected_exposure,
        )

        priority = (
            learning_need * 0.40
            + review_urgency * 0.25
            + new_word_boost * 0.15
            + user_boost * 0.20
        )

        priority -= recent_penalty
        priority -= expected_penalty

        return max(0.0, min(1.0, priority))

    def calculate_learning_need(
        self,
        statistics: WordStatistics,
    ) -> float:
        """
        Determina la necesidad base según el estado de aprendizaje.

        NEW:
            prioridad muy alta porque todavía no ha comenzado
            su aprendizaje.

        LEARNING:
            prioridad alta.

        REINFORCING:
            prioridad media/alta.

        LEARNED:
            prioridad baja.

        REVIEW:
            vuelve a aumentar porque necesita recuperación
            después de un período sin exposición.
        """

        values = {
            LearningState.NEW: 1.00,
            LearningState.LEARNING: 0.85,
            LearningState.REINFORCING: 0.65,
            LearningState.LEARNED: 0.15,
            LearningState.REVIEW: 0.80,
        }

        return values.get(
            statistics.learning_state,
            0.50,
        )

    def calculate_review_urgency(
        self,
        statistics: WordStatistics,
        now: datetime,
    ) -> float:
        """
        Aumenta gradualmente la prioridad mientras más tiempo
        haya pasado desde la última exposición.

        No intenta implementar todavía un algoritmo completo
        de spaced repetition.

        Simplemente produce una señal de urgencia que luego
        puede evolucionar hacia algo más sofisticado.
        """

        if statistics.last_seen_at is None:
            return 1.0

        elapsed = now - statistics.last_seen_at
        days = elapsed.total_seconds() / 86400.0

        if days <= 1:
            return 0.0

        if days >= 30:
            return 1.0

        return min(1.0, days / 30.0)

    def calculate_new_word_boost(
        self,
        statistics: WordStatistics,
    ) -> float:
        """
        Da prioridad temporal a palabras nuevas.

        Una palabra NEW no debería tener que esperar demasiado
        tiempo antes de entrar al LearningPath.
        """

        if statistics.learning_state == LearningState.NEW:
            return 1.0

        return 0.0

    def calculate_user_boost(
        self,
        word: Word,
    ) -> float:
        """
        Permite que el usuario fuerce temporalmente la prioridad
        de una palabra mediante is_boosted.

        Esto sirve para casos como:

            "Quiero practicar esta palabra ahora."
        """

        if not word.is_boosted:
            return 0.0

        if word.boosted_at is None:
            return 1.0

        elapsed = datetime.now(timezone.utc) - word.boosted_at
        hours = elapsed.total_seconds() / 3600.0

        # El boost puede ir perdiendo fuerza con el tiempo.
        if hours >= 24:
            return 0.0

        return max(0.0, 1.0 - (hours / 24.0))

    def calculate_recent_exposure_penalty(
        self,
        statistics: WordStatistics,
        now: datetime,
    ) -> float:
        """
        Penaliza palabras que fueron vistas recientemente.

        Esto evita que una palabra con alta prioridad termine
        monopolizando todos los slots del segmento.

        Es una penalización suave, no una exclusión.
        """

        if statistics.last_seen_at is None:
            return 0.0

        elapsed = now - statistics.last_seen_at
        hours = elapsed.total_seconds() / 3600.0

        if hours < 1:
            return 0.35

        if hours < 6:
            return 0.25

        if hours < 24:
            return 0.15

        if hours < 48:
            return 0.05

        return 0.0

    def calculate_expected_exposure_penalty(
        self,
        expected_exposure: float,
    ) -> float:
        """
        Penaliza palabras que ya tienen bastante exposición futura
        planificada o contenido preparado.

        Esto evita generar contenido innecesario.

        Por ejemplo:

            expected_exposure = 0
                -> no penalty

            expected_exposure = 1
                -> pequeña penalty

            expected_exposure = 3
                -> penalty considerable

            expected_exposure >= 5
                -> fuerte penalty
        """

        if expected_exposure <= 0:
            return 0.0

        if expected_exposure >= 5:
            return 0.40

        return expected_exposure * 0.08