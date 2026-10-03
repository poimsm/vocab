import asyncio
from sqlmodel import Session, select
from typing import Optional, Tuple, Any
from core.central_queue.locks import DistributedLock
from core.central_queue.models import CentralQueueStatus, CentralQueue
from core.event_bus import publish_event
from logging_client import logger


class CentralQueueProcessor:
    def __init__(self, engine, queue_type: str):
        self.engine = engine
        self.queue_type = queue_type
        
        # Instanciamos el semáforo específico para este tipo de cola
        self.lock = DistributedLock(engine, lock_type=queue_type)
        
        # Nota: Se eliminó la suscripción a new_job_signal.connect() 
        # para que el procesador ya no escuche eventos globales de forma automática.

    async def start_processing(self):
        """Método principal para adquirir el lock y comenzar a drenar la cola."""
        if not self.lock.try_acquire():
            return

        # Lanzamos el heartbeat en paralelo manejado por el semáforo genérico
        heartbeat_task = asyncio.create_task(self.lock.heartbeat_loop())

        try:
            self._drain_queue()
        finally:
            # Cancelamos el latido porque ya terminamos o perdimos el lock
            heartbeat_task.cancel()
            self.lock.release()

    def _drain_queue(self):
        """Consume secuencialmente los ítems pendientes y los publica como eventos."""
        while True:
            item_data = self._claim_next_item()
            if not item_data:
                break  # No hay más tareas pendientes de este tipo

            item_id, payload, process_event_name, callback_event_name, side_event_name = item_data

            try:
                publish_event(
                    process_event_name,
                    central_queue_id=item_id,
                    payload=payload,
                    callback_event=callback_event_name,
                )
            except Exception as e:
                self._mark_as_failed(item_id, str(e))
            finally:
                if side_event_name:
                    publish_event(
                        side_event_name,
                        item_id=item_id,
                        payload=payload,
                    )

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

    def _mark_as_failed(self, item_id: int, error_message: Optional[str] = None):
        """Marca una tarea como fallida en la base de datos si ocurre un error."""
        with Session(self.engine) as session:
            db_item = session.get(CentralQueue, item_id)
            if db_item:
                db_item.status = CentralQueueStatus.FAILED
                if hasattr(db_item, "error_log") and error_message:
                    db_item.error_log = error_message
                session.add(db_item)
                session.commit()