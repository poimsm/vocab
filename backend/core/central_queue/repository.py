from typing import List, Optional, Any, Dict, Callable, Awaitable, Union
from sqlmodel import Session, select
from sqlalchemy import func
from core.central_queue.models import CentralQueue, CentralQueueStatus
from core.central_queue.processor import CentralQueueProcessor
from core.central_queue.tasks import process_central_queue

class CentralQueueRepository:
    def __init__(self, session: Session, engine=None):
        self.session = session
        # Si prefieres pasar el engine opcionalmente o extraerlo de la sesión:
        self.engine = engine or getattr(session, "bind", None)

    def add_item(
        self,
        queue_type: str,
        payload: str,
        process_event: str,
        callback_event: Optional[str] = None,
        side_event: Optional[str] = None
    ) -> CentralQueue:
        """Agrega un nuevo ítem a la cola central."""
        max_pos = self.session.exec(
            select(func.max(CentralQueue.order_position))
            .where(CentralQueue.queue_type == queue_type)
        ).first() or 0
        order_position = max_pos + 1

        new_item = CentralQueue(
            queue_type=queue_type,
            payload=payload,
            process_event=process_event,
            callback_event=callback_event,
            side_event=side_event,
            status=CentralQueueStatus.PENDING,
            order_position=order_position,
        )
        self.session.add(new_item)
        self.session.commit()
        self.session.refresh(new_item)
        return new_item.id

    def discard_items(self, item_ids: List[int], reason: Optional[str] = None) -> int:
        """
        Marca una lista de ítems pendientes como descartados (DISCARDED) por lote.
        Retorna la cantidad de ítems que fueron descartados exitosamente.
        """
        if not item_ids:
            return 0

        statement = (
            select(CentralQueue)
            .where(CentralQueue.id.in_(item_ids))
            .where(CentralQueue.status == CentralQueueStatus.PENDING)
        )
        items = self.session.exec(statement).all()
        
        count = 0
        for item in items:
            item.status = CentralQueueStatus.DISCARDED
            if reason:
                item.error_log = reason
            self.session.add(item)
            count += 1
            
        if count > 0:
            self.session.commit()
            
        return count

    def discard_item(self, item_id: int, reason: Optional[str] = None) -> bool:
        """Marca un ítem pendiente como descartado (DISCARDED)."""
        item = self.session.get(CentralQueue, item_id)
        if item and item.status == CentralQueueStatus.PENDING:
            item.status = CentralQueueStatus.DISCARDED
            if reason:
                item.error_log = reason
            self.session.add(item)
            self.session.commit()
            return True
        return False

    def mark_as_completed(self, item_id: int):
        item = self.session.get(CentralQueue, item_id)
        if item:
            item.status = CentralQueueStatus.COMPLETED
            self.session.add(item)
            self.session.commit()

    def mark_as_failed(self, item_id: int, error_message: str):
        item = self.session.get(CentralQueue, item_id)
        if item:
            item.status = CentralQueueStatus.FAILED
            item.error_log = error_message
            self.session.add(item)
            self.session.commit()

    def drain_sync(
        self,
        queue_type: str,
        job_handler: Callable[[int, str, Optional[str]], Any]
    ):
        """Lanza el procesador para drenar la cola de forma síncrona."""
        if not self.engine:
            raise ValueError(
                "Se requiere el engine de base de datos para instanciar el procesador.")

        processor = CentralQueueProcessor(
            engine=self.engine,
            queue_type=queue_type,
            job_handler=job_handler
        )
        processor.process_sync()

    async def drain_async(
        self,
        queue_type: str,
        job_handler: Callable[[int, str, Optional[str]], Awaitable[Any]]
    ):
        """Lanza el procesador para drenar la cola de forma asíncrona (con asyncio)."""
        if not self.engine:
            raise ValueError(
                "Se requiere el engine de base de datos para instanciar el procesador.")

        processor = CentralQueueProcessor(
            engine=self.engine,
            queue_type=queue_type,
            job_handler=job_handler
        )
        await processor.process_async()

    def dispatch_background_drain(self, queue_type: str):
        """
        Dispatches the queue draining task to Celery using the 'background_queue'.
        """
        process_central_queue.delay(queue_type)
