# src/core/boost/services.py
from sqlmodel import Session
from core.boost.repository import BoostRepository
from core.boost.rules import validate_max_boost_slots, validate_toggle_cooldown
from core.boost.policies import BoostLearningPolicy
from core.boost.strategies import BoostDemandStrategy
from core.generation_ai.repository import GenerationAIRepository
from core.delivery.repository import DeliveryRepository
from core.event_bus import publish_event_background
from logging_client import logger


class BoostService:
    def __init__(self, session: Session, max_slots: int = 5):
        self.session = session
        self.repo = BoostRepository(session)
        self.generation_repo = GenerationAIRepository(session)
        self.delivery_repo = DeliveryRepository(session)
        self.max_slots = max_slots

    def toggle_boost(self, user_id: int, word_id: int, enable: bool) -> dict:
        active_boosts = self.repo.get_active_boosts(user_id)
        current_boost = self.repo.get_boost_by_word(user_id, word_id)

        # -------------------------------------------------------------
        # CASO 1: ACTIVAR BOOST (enable = True)
        # -------------------------------------------------------------
        if enable:
            if current_boost and current_boost.is_boosted:
                return {"status": "noop", "word_id": word_id}

            # Validar reglas de negocio
            if current_boost:
                validate_toggle_cooldown(current_boost.boosted_at)

            validate_max_boost_slots(len(active_boosts), self.max_slots)

            # Persistir activación en la tabla de boosts
            self.repo.activate(user_id, word_id)

            # Publicar evento word.boosted para que la rueda se actualice
            publish_event_background(
                'word.boosted',
                user_id=user_id,
                word_id=word_id,
            )
            logger.info(f"[BoostService] Published word.boosted event for user {user_id}, word {word_id}")

            # Encolar la demanda de generación (usando refill pack como pack único)
            from core.enums import ContentSourceType
            demands = BoostDemandStrategy.get_refill_pack()
            self.generation_repo.enqueue_demand(
                user_id=user_id,
                word_id=word_id,
                demands=demands,
                source_type=ContentSourceType.BOOST
            )

            return {"status": "activated", "word_id": word_id}

        # -------------------------------------------------------------
        # CASO 2: DESACTIVAR BOOST (enable = False)
        # -------------------------------------------------------------
        else:
            if not current_boost or not current_boost.is_boosted:
                return {"status": "noop", "word_id": word_id}

            validate_toggle_cooldown(current_boost.boosted_at)

            # Publicar evento word.unboosted para que la rueda se actualice
            publish_event_background(
                'word.unboosted',
                user_id=user_id,
                word_id=word_id,
            )
            logger.info(f"[BoostService] Published word.unboosted event for user {user_id}, word {word_id}")

            return {
                "status": "deactivated",
                "word_id": word_id,
            }

    def is_word_in_infinite_mode(self, user_id: int, word_id: int) -> bool:
        """Consultado por el módulo de LearningPath o ContentManager."""
        is_boosted = self.repo.is_word_boosted(user_id, word_id)
        return BoostLearningPolicy.allows_infinite_generation(is_boosted)
