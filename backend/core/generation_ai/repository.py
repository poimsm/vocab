import json
from typing import List, Optional, Any, Dict
from sqlmodel import Session, select
from datetime import datetime, timezone
from core.boost.dtos import SkillDemand
from core.central_queue.repository import CentralQueueRepository
from core.generation_ai.models import GenerationAIRegistry, GenerationAIStatus


class GenerationAIRepository:
    def __init__(self, session: Session):
        self.session = session
        self.central_repo = CentralQueueRepository(session)

    def enqueue_demand(
        self,
        user_id: int,
        word_id: int,
        demands: List[SkillDemand],
        source_type: str
    ) -> List[int]:

        created_central_ids = []
        for demand in demands:
            for _ in range(demand.quantity):
                payload_data = {
                    "user_id": user_id,
                    "word_id": word_id,
                    "skill_type": demand.skill_type,
                    "source_type": source_type
                }

                # 1. Agregamos a la cola central y obtenemos el ID retornado
                central_queue_id = self.central_repo.add_item(
                    queue_type="generator",
                    payload=json.dumps(payload_data),
                    process_event=demand.process_event,
                    side_event="ai_generation_side_event"
                )
                created_central_ids.append(central_queue_id)

                # 2. Guardamos el registro en la tabla intermedia con sus campos de filtro
                ai_queue_item = GenerationAIRegistry(
                    user_id=user_id,
                    word_id=word_id,
                    source_type=source_type,
                    central_queue_id=central_queue_id,
                    status=GenerationAIStatus.PENDING
                )
                self.session.add(ai_queue_item)

        self.session.commit()

        # Despachamos el drenaje a Celery
        self.central_repo.dispatch_background_drain(queue_type="generator")

        return created_central_ids

    def create_queue_item(
        self,
        user_id: int,
        word_id: int,
        source_type: str,
        payload: Dict[str, Any],
        process_event: str,
        callback_event: Optional[str] = None,
    ) -> int:
        payload_str = json.dumps(payload) if isinstance(
            payload, dict) else payload

        central_queue_id = self.central_repo.add_item(
            queue_type="generator",
            payload=payload_str,
            process_event=process_event,
            callback_event=callback_event,
            side_event="ai_generation_side_event",
        )

        ai_queue_item = GenerationAIRegistry(
            user_id=user_id,
            word_id=word_id,
            source_type=source_type,
            central_queue_id=central_queue_id,
            status=GenerationAIStatus.PENDING
        )
        self.session.add(ai_queue_item)
        self.session.commit()

        self.central_repo.dispatch_background_drain(queue_type="generator")

        return central_queue_id

    def cancel_pending_tasks_for_word(
        self,
        user_id: int,
        word_id: int,
        source_type: Optional[str] = "BOOST"
    ) -> int:
        """
        Busca y cancela tareas consultando ÚNICAMENTE la tabla intermedia GenerationAIRegistry,
        sin realizar ningún join con la cola central.
        """
        statement = (
            select(GenerationAIRegistry)
            .where(GenerationAIRegistry.user_id == user_id)
            .where(GenerationAIRegistry.word_id == word_id)
            .where(GenerationAIRegistry.status == GenerationAIStatus.PENDING)
        )
        if source_type:
            statement = statement.where(
                GenerationAIRegistry.source_type == source_type)

        pending_ai_items = self.session.exec(statement).all()

        central_ids_to_cancel = []
        for ai_item in pending_ai_items:
            if ai_item.central_queue_id:
                central_ids_to_cancel.append(ai_item.central_queue_id)

            # Actualizamos el estado local en la tabla intermedia
            ai_item.status = GenerationAIStatus.DISCARDED
            ai_item.updated_at = datetime.now(timezone.utc)
            self.session.add(ai_item)

        cancelled_count = 0
        if central_ids_to_cancel:
            reason = f"Cancelled automatically by user (word_id={word_id})"
            # Descartamos en lote en la cola central usando los IDs limpios
            cancelled_count = self.central_repo.discard_items(
                central_ids_to_cancel, reason=reason)
            self.session.commit()

        return cancelled_count

    def mark_as_completed(self, central_queue_id: int) -> bool:
        statement = select(GenerationAIRegistry).where(
            GenerationAIRegistry.central_queue_id == central_queue_id
        )
        ai_record = self.session.exec(statement).first()

        if ai_record:
            ai_record.status = GenerationAIStatus.COMPLETED
            ai_record.updated_at = datetime.now(timezone.utc)
            self.session.add(ai_record)
            self.session.commit()
            return True
        return False

    def mark_as_failed(self, central_queue_id: int) -> bool:
        statement = select(GenerationAIRegistry).where(
            GenerationAIRegistry.central_queue_id == central_queue_id
        )
        ai_record = self.session.exec(statement).first()

        if ai_record:
            ai_record.status = GenerationAIStatus.FAILED
            ai_record.updated_at = datetime.now(timezone.utc)
            self.session.add(ai_record)
            self.session.commit()
            return True
        return False
