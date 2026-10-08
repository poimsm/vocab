import json
from typing import List, Optional, Any, Dict
from sqlmodel import Session, select
from datetime import datetime, timezone
from core.boost.dtos import SkillDemand
from core.central_queue.repository import CentralQueueRepository
from core.generation_ai.models import GenerationAIRegistry, GenerationAIStatus
from core.enums import ContentSourceType, ContentType
from logging_client import logger


class GenerationAIRepository:
    def __init__(self, session: Session):
        self.session = session
        self.central_repo = CentralQueueRepository(session)
        logger.debug("[GenerationAIRepository] Initialized")

    def enqueue_demand(
        self,
        user_id: int,
        word_id: int,
        demands: List[SkillDemand],
        source_type: ContentSourceType
    ) -> List[int]:
        logger.info(
            f"[GenerationAIRepository] Enqueuing demands for user_id={user_id}, word_id={word_id}, "
            f"num_demands={len(demands)}, source_type={source_type.value}"
        )

        created_central_ids = []

        for demand in demands:
            # Obtener cantidad de items por tarea de la demanda (configurable, por defecto 5)
            items_per_task = demand.items_per_task

            # Calcular cuántas tareas de IA se necesitan para generar demand.quantity ejemplos
            # quantity = ejemplos deseados, no tareas de IA
            num_tasks = (demand.quantity + items_per_task - 1) // items_per_task

            logger.debug(
                f"[GenerationAIRepository] Demand for {demand.quantity} {demand.skill_type}: "
                f"enqueueing {num_tasks} AI task(s) ({items_per_task} items per task)"
            )

            for _ in range(num_tasks):
                # Convertir skill_type string a ContentType enum
                content_type_enum = ContentType(demand.skill_type)

                payload_data = {
                    "user_id": user_id,
                    "word_ids": [word_id],  # La tarea espera word_ids (plural)
                    "content_type": content_type_enum.value,  # skill_type → content_type
                    "content_source_type": source_type.value,  # source_type → content_source_type
                }

                # Agregar parámetro dinámico según tipo de contenido
                if demand.skill_type == "example":
                    payload_data["amount"] = items_per_task  # Ejemplos por palabra
                elif demand.skill_type == "best_options":
                    payload_data["questions_per_word"] = items_per_task  # Preguntas por palabra

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
                    content_type=content_type_enum,
                    central_queue_id=central_queue_id,
                    status=GenerationAIStatus.PENDING
                )
                self.session.add(ai_queue_item)

        self.session.commit()
        logger.info(
            f"[GenerationAIRepository] Successfully enqueued {len(created_central_ids)} AI task(s) "
            f"for {sum(d.quantity for d in demands)} total examples to generate"
        )

        # Despachamos el drenaje a Celery
        self.central_repo.dispatch_background_drain(queue_type="generator")
        logger.debug("[GenerationAIRepository] Dispatched background drain for generator queue")

        return created_central_ids

    def create_queue_item(
        self,
        user_id: int,
        word_id: int,
        source_type: ContentSourceType,
        content_type: ContentType,
        payload: Dict[str, Any],
        process_event: str,
        callback_event: Optional[str] = None,
    ) -> int:
        logger.info(
            f"[GenerationAIRepository] Creating queue item: user_id={user_id}, word_id={word_id}, "
            f"source_type={source_type.value}, content_type={content_type.value}, process_event={process_event}"
        )
        payload_str = json.dumps(payload) if isinstance(
            payload, dict) else payload

        central_queue_id = self.central_repo.add_item(
            queue_type="generator",
            payload=payload_str,
            process_event=process_event,
            callback_event=callback_event,
            side_event="ai_generation_side_event",
        )
        logger.debug(f"[GenerationAIRepository] Central queue item created with id={central_queue_id}")

        ai_queue_item = GenerationAIRegistry(
            user_id=user_id,
            word_id=word_id,
            source_type=source_type,
            content_type=content_type,
            central_queue_id=central_queue_id,
            status=GenerationAIStatus.PENDING
        )
        self.session.add(ai_queue_item)
        self.session.commit()
        logger.info(f"[GenerationAIRepository] Queue item created successfully with central_queue_id={central_queue_id}")

        self.central_repo.dispatch_background_drain(queue_type="generator")
        logger.debug("[GenerationAIRepository] Dispatched background drain for generator queue")

        return central_queue_id

    def cancel_pending_tasks_for_word(
        self,
        user_id: int,
        word_id: int,
        source_type: Optional[ContentSourceType] = ContentSourceType.BOOST
    ) -> int:
        """
        Busca y cancela tareas consultando ÚNICAMENTE la tabla intermedia GenerationAIRegistry,
        sin realizar ningún join con la cola central.
        """
        logger.info(
            f"[GenerationAIRepository] Cancelling pending tasks: user_id={user_id}, word_id={word_id}, "
            f"source_type={source_type.value if source_type else 'ANY'}"
        )
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
        logger.debug(f"[GenerationAIRepository] Found {len(pending_ai_items)} pending tasks to cancel")

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
            logger.debug(f"[GenerationAIRepository] Cancelling {len(central_ids_to_cancel)} items in central queue")
            # Descartamos en lote en la cola central usando los IDs limpios
            cancelled_count = self.central_repo.discard_items(
                central_ids_to_cancel, reason=reason)
            self.session.commit()
            logger.info(f"[GenerationAIRepository] Successfully cancelled {cancelled_count} tasks")

        return cancelled_count

    def mark_as_completed(self, central_queue_id: int) -> bool:
        logger.debug(f"[GenerationAIRepository] Marking task as completed: central_queue_id={central_queue_id}")
        statement = select(GenerationAIRegistry).where(
            GenerationAIRegistry.central_queue_id == central_queue_id
        )
        ai_record = self.session.exec(statement).first()

        if ai_record:
            ai_record.status = GenerationAIStatus.COMPLETED
            ai_record.updated_at = datetime.now(timezone.utc)
            self.session.add(ai_record)
            self.session.commit()
            logger.info(f"[GenerationAIRepository] Task marked as completed: central_queue_id={central_queue_id}")
            return True
        logger.warning(f"[GenerationAIRepository] Task not found for completion: central_queue_id={central_queue_id}")
        return False

    def mark_as_failed(self, central_queue_id: int, error_message: Optional[str] = None) -> bool:
        logger.debug(
            f"[GenerationAIRepository] Marking task as failed: central_queue_id={central_queue_id}, "
            f"error_message={error_message}"
        )
        statement = select(GenerationAIRegistry).where(
            GenerationAIRegistry.central_queue_id == central_queue_id
        )
        ai_record = self.session.exec(statement).first()

        if ai_record:
            ai_record.status = GenerationAIStatus.FAILED
            ai_record.updated_at = datetime.now(timezone.utc)
            self.session.add(ai_record)
            self.session.commit()
            logger.error(
                f"[GenerationAIRepository] Task marked as failed: central_queue_id={central_queue_id}, "
                f"error={error_message}"
            )
            return True
        logger.warning(f"[GenerationAIRepository] Task not found for failure mark: central_queue_id={central_queue_id}")
        return False

    def is_generating(
        self,
        user_id: int,
        word_id: int,
        source_type: ContentSourceType,
        content_type: ContentType
    ) -> bool:
        """
        Verifica si hay generación en progreso para una combinación específica.

        Busca registros en GenerationAIRegistry con estado PENDING o PROCESSING
        que coincidan con los criterios especificados.

        Args:
            user_id: ID del usuario
            word_id: ID de la palabra
            source_type: Tipo de fuente (BOOST, LEARNING_PATH)
            content_type: Tipo de contenido (EXAMPLE, BEST_OPTIONS, etc.)

        Returns:
            True si hay tareas pendientes o procesando, False en caso contrario
        """
        logger.debug(
            f"[GenerationAIRepository] Checking if generating for user_id={user_id}, word_id={word_id}, "
            f"source_type={source_type.value}, content_type={content_type.value}"
        )

        statement = (
            select(GenerationAIRegistry)
            .where(GenerationAIRegistry.user_id == user_id)
            .where(GenerationAIRegistry.word_id == word_id)
            .where(GenerationAIRegistry.source_type == source_type)
            .where(GenerationAIRegistry.content_type == content_type)
            .where(
                (GenerationAIRegistry.status == GenerationAIStatus.PENDING) |
                (GenerationAIRegistry.status == GenerationAIStatus.PROCESSING)
            )
        )

        pending_or_processing_items = self.session.exec(statement).all()

        is_generating = len(pending_or_processing_items) > 0

        logger.debug(
            f"[GenerationAIRepository] Generation status for user_id={user_id}, word_id={word_id}, "
            f"source_type={source_type.value}, content_type={content_type.value}: is_generating={is_generating} "
            f"(found {len(pending_or_processing_items)} pending/processing tasks)"
        )

        return is_generating
