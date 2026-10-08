from enum import Enum


class CentralStateEnum(str, Enum):
    IDLE = "IDLE"
    BUSY = "BUSY"


class CentralQueueStatus(str, Enum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    DISCARDED = "DISCARDED"
    FAILED = "FAILED"
