import enum


class DeliveryStatus(str, enum.Enum):
    """Estados del contenido en DeliveryBuffer."""
    PENDING = "pending"           # Esperando ser despachado
    DISPATCHED = "dispatched"     # Enviado al usuario (mostrado en explore)
    DISCARDED = "discarded"       # Descartado (palabra desbosteada, etc.)


class RoundRobinWheelNodeStatus(str, enum.Enum):
    """Estados de nodos en el round-robin wheel."""
    INITIAL = "initial"           # Inicializado, no procesado aún
    GENERATING = "generating"     # Generando contenido
    READY = "ready"               # Contenido listo para colectar
    EXHAUSTED = "exhausted"       # Se agotó el contenido (para control)
