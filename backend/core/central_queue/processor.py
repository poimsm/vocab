import asyncio
import json
from sqlmodel import Session, select
from typing import Optional, Tuple, Any
from core.central_queue.locks import DistributedLock
from core.central_queue.models import CentralQueueStatus, CentralQueue
from core.event_bus import publish_event_ai, publish_event_background
from logging_client import logger


class CentralQueueProcessor:
    def __init__(self, engine, queue_type: str):
        self.engine = engine
        self.queue_type = queue_type

        # Instanciamos el semáforo específico para este tipo de cola
        self.lock = DistributedLock(engine, lock_type=queue_type)
        logger.debug(f"[CentralQueueProcessor] Initialized for queue_type={queue_type}")

        # Nota: Se eliminó la suscripción a new_job_signal.connect()
        # para que el procesador ya no escuche eventos globales de forma automática.

    def process_sync(self, queue_type: str):
        """
        Procesa la cola de forma síncrona.
        Llamado desde tareas Celery en background workers.
        """
        logger.info(f"[CentralQueueProcessor] Starting sync processing for queue_type={queue_type}")
        self._drain_queue(queue_type=queue_type)
        logger.info(f"[CentralQueueProcessor] Finished sync processing for queue_type={queue_type}")

    async def start_processing(self):
        """Método principal para adquirir el lock y comenzar a drenar la cola."""
        logger.info(f"[CentralQueueProcessor] Attempting to acquire lock for queue_type={self.queue_type}")
        if not self.lock.try_acquire():
            logger.debug(f"[CentralQueueProcessor] Failed to acquire lock for queue_type={self.queue_type}")
            return

        logger.info(f"[CentralQueueProcessor] Lock acquired for queue_type={self.queue_type}")
        # Lanzamos el heartbeat en paralelo manejado por el semáforo genérico
        heartbeat_task = asyncio.create_task(self.lock.heartbeat_loop())

        try:
            self._drain_queue(queue_type=self.queue_type)
        finally:
            # Cancelamos el latido porque ya terminamos o perdimos el lock
            heartbeat_task.cancel()
            self.lock.release()
            logger.info(f"[CentralQueueProcessor] Lock released for queue_type={self.queue_type}")

    def _drain_queue(self, queue_type: str = None):
        """Consume secuencialmente los ítems pendientes y los publica como eventos."""
        if queue_type is None:
            queue_type = self.queue_type

        processed_count = 0
        logger.debug(f"[CentralQueueProcessor] Starting drain for queue_type={queue_type}")

        while True:
            item_data = self._claim_next_item()
            if not item_data:
                logger.debug(f"[CentralQueueProcessor] Drain finished: processed {processed_count} items")
                break  # No hay más tareas pendientes de este tipo

            item_id, payload, process_event_name, callback_event_name, side_event_name = item_data
            processed_count += 1
            logger.debug(
                f"[CentralQueueProcessor] Processing item_id={item_id}, event={process_event_name}, "
                f"queue_type={queue_type}"
            )

            try:
                # Parsear payload JSON si es string
                try:
                    payload_data = json.loads(payload) if isinstance(payload, str) else payload
                except json.JSONDecodeError as e:
                    logger.error(
                        f"[CentralQueueProcessor] Item {item_id}: Invalid JSON payload. "
                        f"Details: {str(e)} | Payload: {payload}"
                    )
                    self._mark_as_failed(item_id, f"Invalid JSON: {str(e)}")
                    continue

                # Seleccionar la función de publicación según el tipo de cola
                try:
                    if queue_type == "generator":
                        logger.debug(
                            f"[CentralQueueProcessor] Item {item_id}: Unpacked kwargs for AI event: {payload_data}"
                        )
                        publish_event_ai(
                            process_event_name,
                            queue_item_id=item_id,
                            **payload_data,
                        )
                    else:
                        logger.debug(
                            f"[CentralQueueProcessor] Item {item_id}: Unpacked kwargs for background event: {payload_data}"
                        )
                        publish_event_background(
                            process_event_name,
                            central_queue_id=item_id,
                            **payload_data,
                        )
                    logger.info(f"[CentralQueueProcessor] Item {item_id}: Event published successfully")

                    # Marcar el item como COMPLETED después de publicar exitosamente
                    self._mark_as_completed(item_id)

                except Exception as publish_error:
                    logger.error(
                        f"[CentralQueueProcessor] Item {item_id}: Failed to publish event '{process_event_name}'. "
                        f"Error type: {type(publish_error).__name__} | Details: {str(publish_error)}"
                    )
                    self._mark_as_failed(item_id, f"{type(publish_error).__name__}: {str(publish_error)}")

            except Exception as e:
                logger.error(
                    f"[CentralQueueProcessor] Item {item_id}: Unexpected error. "
                    f"Error type: {type(e).__name__} | Details: {str(e)}"
                )
                self._mark_as_failed(item_id, f"{type(e).__name__}: {str(e)}")
            # Note: Side events (ai_generation_side_event) are optional monitoring events
            # They don't have subscribers currently, so we skip them to avoid warnings

    def _claim_next_item(self) -> Optional[Tuple[int, Any, str, Optional[str]]]:
        """
        Selecciona y reclama atómicamente el siguiente ítem PENDING
        ordenado por order_position y filtrado por el queue_type del procesador.
        """
        with Session(self.engine) as session:
            query = (
                select(CentralQueue)
                .where(CentralQueue.status == CentralQueueStatus.PENDING)
                .where(CentralQueue.queue_type == self.queue_type)
                .order_by(CentralQueue.order_position.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            item = session.exec(query).first()

            if not item:
                return None  # No hay más tareas

            logger.debug(f"[CentralQueueProcessor] Claimed item_id={item.id} from queue_type={self.queue_type}")
            item.status = CentralQueueStatus.DISPATCHED
            session.add(item)
            session.commit()
            session.refresh(item)

            return (
                item.id,
                item.payload,
                item.process_event,
                getattr(item, "callback_event", None),
                getattr(item, "side_event", None),
            )

    def _mark_as_completed(self, item_id: int):
        """Marca una tarea como completada en la base de datos después de procesarla exitosamente."""
        try:
            with Session(self.engine) as session:
                db_item = session.get(CentralQueue, item_id)
                if db_item:
                    db_item.status = CentralQueueStatus.COMPLETED
                    session.add(db_item)
                    session.commit()
                    logger.info(f"[CentralQueueProcessor] Item {item_id}: Status updated to COMPLETED ✓")
                else:
                    logger.warning(
                        f"[CentralQueueProcessor] Item {item_id}: NOT FOUND in database when marking as COMPLETED"
                    )
        except Exception as e:
            logger.error(
                f"[CentralQueueProcessor] Item {item_id}: Failed to mark as COMPLETED. "
                f"Error: {type(e).__name__}: {str(e)}"
            )

    def _mark_as_failed(self, item_id: int, error_message: Optional[str] = None):
        """Marca una tarea como fallida en la base de datos si ocurre un error."""
        try:
            with Session(self.engine) as session:
                db_item = session.get(CentralQueue, item_id)
                if db_item:
                    db_item.status = CentralQueueStatus.FAILED
                    if hasattr(db_item, "error_log") and error_message:
                        db_item.error_log = error_message
                    session.add(db_item)
                    session.commit()
                    logger.error(
                        f"[CentralQueueProcessor] Item {item_id}: Status updated to FAILED ✗ | "
                        f"Reason: {error_message}"
                    )
                else:
                    logger.warning(
                        f"[CentralQueueProcessor] Item {item_id}: NOT FOUND in database when marking as FAILED | "
                        f"Reason: {error_message}"
                    )
        except Exception as e:
            logger.error(
                f"[CentralQueueProcessor] Item {item_id}: Failed to mark as FAILED. "
                f"Error: {type(e).__name__}: {str(e)} | Original reason: {error_message}"
            )