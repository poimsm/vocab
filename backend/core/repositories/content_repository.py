"""
Interfaces para repositorios de contenido.
Define contratos que features implementa sin dependencia explícita de core.
"""
from typing import Protocol, Optional


class ContentRepository(Protocol):
    """Interfaz genérica para repositorios de contenido (examples, best_options, etc)"""

    def count_available_for_word(self, word_id: int) -> int:
        """Cuenta contenido disponible para una palabra"""
        ...

    def get_available_content_for_word(self, word_id: int) -> Optional[int]:
        """Obtiene el próximo contenido disponible para una palabra"""
        ...

    def get_word_id(self, content_id: int) -> Optional[int]:
        """Obtiene el word_id asociado a un contenido"""
        ...
