"""
Protocolos (interfaces) que define core.explore para sus dependencias.
Las implementaciones concretas están en features.
"""

from typing import Protocol, List, Optional, Any


class ContentRepository(Protocol):
    """
    Protocolo para acceso a contenido (ejemplos, best_options, etc.).
    Las implementaciones concretas están en features.
    """

    def get_content(
        self, content_type: str, content_id: int
    ) -> Optional[Any]:
        """Obtiene un contenido por tipo e ID."""
        ...

    def is_content_learned(
        self, user_id: int, content_type: str, content_id: int
    ) -> bool:
        """Verifica si un contenido ya fue aprendido por el usuario."""
        ...


class ContentValidator(Protocol):
    """
    Protocolo para validar si un contenido fue aprendido.
    Agnóstico al tipo de contenido específico.
    """

    def is_content_learned(self, content_id: int, user_id: int) -> bool:
        """Verifica si un contenido fue aprendido."""
        ...
