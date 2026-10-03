from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from core.delivery.enums import DeliveryStatus
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

    # Opcional: ID de la palabra asociada (clave para purgar si se desactiva un boost)
    word_id: Optional[int] = Field(default=None, index=True)

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