# src/core/boost/services.py
from sqlmodel import Session
from core.boost.repository import BoostRepository
from core.boost.rules import validate_max_boost_slots, validate_toggle_cooldown
from core.boost.policies import BoostLearningPolicy
from core.boost.strategies import BoostDemandStrategy
from core.generation_ai.repository import GenerationAIRepository
from core.delivery.repository import DeliveryRepository
from celery_app import celery_app


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

            # Encolar la demanda inicial de generación
            demands = BoostDemandStrategy.get_initial_boost_pack()
            for demand in demands:
                self.generation_repo.enqueue_demand(
                    user_id=user_id,
                    word_id=word_id,
                    skill_type=demand.skill_type,
                    quantity=demand.quantity,
                    is_boost=True
                )

            return {"status": "activated", "word_id": word_id}

        # -------------------------------------------------------------
        # CASO 2: DESACTIVAR BOOST (enable = False)
        # -------------------------------------------------------------
        else:
            if not current_boost or not current_boost.is_boosted:
                return {"status": "noop", "word_id": word_id}

            validate_toggle_cooldown(current_boost.boosted_at)

            celery_app.send_task(
                'boost.on_word_unboosted',
                kwargs={
                    "user_id": user_id,
                    "word_id": word_id
                },
                exchange="app_events",
                routing_key="event.word.unboosted"
            )

            return {
                "status": "deactivated",
                "word_id": word_id,
            }

    def is_word_in_infinite_mode(self, user_id: int, word_id: int) -> bool:
        """Consultado por el módulo de LearningPath o ContentManager."""
        is_boosted = self.repo.is_word_boosted(user_id, word_id)
        return BoostLearningPolicy.allows_infinite_generation(is_boosted)
