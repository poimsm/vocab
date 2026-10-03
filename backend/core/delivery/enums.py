import enum


class DeliveryStatus(str, enum.Enum):
    """Estados de un ítem en el buffer de delivery."""
    PENDING = "pending"      # Esperando ser mostrado al usuario
    DISPATCHED = "dispatching"   # Ya fue enviado/entregado al buffer del usuario
    DISCARDED = "discarded"  # Descartado (ej: palabra des-boosteada)

