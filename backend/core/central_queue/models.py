from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from core.central_queue.enums import CentralStateEnum, CentralQueueStatus

class CentralLockState(SQLModel, table=True):
    """
    Representa el semáforo o lock distribuido central de la infraestructura.
    """
    __tablename__: str = "central_lock_state"

    lock_type: str = Field(primary_key=True)
    state: CentralStateEnum = Field(
        default=CentralStateEnum.IDLE, index=True
    )
    expires_at: Optional[datetime] = Field(default=None)


class CentralQueue(SQLModel, table=True):
    """
    Representa un ítem dentro de la infraestructura central y maestra de colas.
    """
    __tablename__: str = "central_queue"

    id: Optional[int] = Field(default=None, primary_key=True)
    queue_type: str = Field(index=True)
    payload: str  # JSON serializado o texto con los datos del evento
    status: CentralQueueStatus = Field(
        default=CentralQueueStatus.PENDING, index=True)
    process_event: str
    side_event: Optional[str] = Field(default=None)
    callback_event: Optional[str] = Field(default=None)
    error_log: Optional[str] = Field(default=None)
    result: Optional[str] = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    order_position: float = Field(
        default_factory=lambda: datetime.now(timezone.utc).timestamp(),
        index=True
    )
