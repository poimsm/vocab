from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from core.delivery.enums import DeliveryStatus, RoundRobinWheelNodeStatus
from core.enums import ContentSourceType, ContentType


class DeliveryBuffer(SQLModel, table=True):
    __tablename__: str = "delivery_buffer"

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Identificación del usuario destinatario
    user_id: int = Field(index=True)

    # Referencia al contenido generado que se va a servir
    content_id: int = Field(index=True)

    # Tipo de contenido (EXAMPLE, BEST_OPTIONS, etc.)
    content_type: ContentType = Field(default=ContentType.EXAMPLE, index=True)

    # Origen del contenido para saber cómo aplicar las reglas al consumirlo
    source_type: ContentSourceType = Field(
        default=ContentSourceType.LEARNING_PATH, index=True
    )

    # ID de la palabra asociada al contenido (obligatorio)
    # Clave para purgar si se desactiva un boost, para priorización, etc.
    word_id: int = Field(foreign_key="words.id", index=True)

    # Opcional: ID del learning path queue item (solo para contenido de learning path, NULL para boost)
    learning_path_queue_id: Optional[int] = Field(default=None, index=True)

    # Estado del ciclo de vida del ítem en la vista
    status: DeliveryStatus = Field(
        default=DeliveryStatus.PENDING, index=True
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    
    # Momento en que el usuario consumió o interactuó con el ítem
    consumed_at: Optional[datetime] = Field(default=None)


class RoundRobinWheel(SQLModel, table=True):
    """
    Representa una posición en la rueda circular de distribución de contenido.

    La rueda es una lista enlazada circular que alterna entre:
    - Nodos de palabras boosteadas (word_id != NULL, is_learning_slot = False)
    - Nodos de learning path (word_id = NULL, is_learning_slot = True)

    Ejemplo con 2 palabras boosteadas y learning path intercalado:
    A -> LEARNING -> B -> LEARNING -> A (loop)

    La rueda es la fuente de verdad, actualizada por eventos de boost/unboost.
    No depende de calcular dinámicamente qué palabras están activas.
    """
    __tablename__: str = "round_robin_wheel"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Usuario propietario de esta rueda
    user_id: int = Field(index=True)

    # Tipo de contenido
    content_type: ContentType = Field(index=True)

    # La palabra boosteada en esta posición (NULL si es un slot de learning path)
    word_id: Optional[int] = Field(default=None, index=True)

    # Indica si este nodo es un slot de contenido learning path (no boosteado)
    is_learning_slot: bool = Field(default=False, index=True)

    # ID del siguiente nodo en la rueda (apunta a otro row de RoundRobinWheel)
    # NULL si es el único nodo (form el loop a sí mismo)
    next_wheel_id: Optional[int] = Field(default=None)

    # Orden en la rueda (para debugging/auditoría)
    order: int = Field(default=0)

    # Estado del nodo en el round-robin
    # INITIAL → GENERATING → READY | EXHAUSTED
    status: RoundRobinWheelNodeStatus = Field(
        default=RoundRobinWheelNodeStatus.INITIAL,
        index=True
    )

    # Timestamp
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Última actualización del status
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True
    )


class RoundRobinNeedle(SQLModel, table=True):
    """
    La aguja que apunta a la posición actual en la rueda.

    Representa por dónde va la rotación actualmente. Avanza circularmente
    cada vez que se consume contenido de una palabra boosteada.
    """
    __tablename__: str = "round_robin_needle"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Usuario
    user_id: int = Field(index=True)

    # Tipo de contenido
    content_type: ContentType = Field(index=True)

    # ID del nodo actual en la rueda (FK a RoundRobinWheel.id)
    current_wheel_id: int = Field(index=True)

    # Última actualización
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )