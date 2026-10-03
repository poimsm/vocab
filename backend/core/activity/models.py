import enum
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel


class ActivityType(str, enum.Enum):
    """Tipos de actividades que puede realizar el usuario."""
    BUTTON_CLICK = "button_click"
    ENDPOINT_VISIT = "endpoint_visit"
    PAGE_VIEW = "page_view"
    FEATURE_INTERACTION = "feature_interaction"


class UserActivity(SQLModel, table=True):
    """
    Rastreo de actividades del usuario.
    Registra clicks de botones, visitas a endpoints, vistas de páginas, etc.
    Útil para analytics, debugging y entender el comportamiento del usuario.
    """
    __tablename__: str = "user_activities"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    activity_type: str = Field(index=True, nullable=False)
    activity_name: str = Field(max_length=255, nullable=False)  # ej: "click_learn_button", "GET_/examples/next"
    details: Optional[str] = Field(default=None)  # JSON con datos adicionales (parámetros, respuesta, etc)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
