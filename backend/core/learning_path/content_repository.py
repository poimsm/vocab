"""
Interfaz para repositorios de contenido.
Maneja múltiples tipos de contenido (examples, best_options, etc).
"""
from typing import Protocol, Optional
from core.enums import ContentType


class ContentRepository(Protocol):
    """
    Contrato único para acceder a cualquier tipo de contenido.
    Usado por LearningPathService y ContentPlanner para preparar y gestionar contenido.

    El repositorio puede manejar examples, best_options, collocations, etc.
    El tipo se especifica mediante content_type.
    """

    def count_available_for_word(self, word_id: int, content_type: ContentType) -> int:
        """
        Cuenta cuánto contenido disponible hay para una palabra.

        Disponible = activo, no encolado, no consumido.

        Args:
            word_id: ID de la palabra
            content_type: Tipo de contenido (EXAMPLE, BEST_OPTIONS, etc)

        Returns:
            Número de items disponibles
        """
        ...

    def get_available_content_for_word(
        self, word_id: int, content_type: ContentType
    ) -> Optional[int]:
        """
        Obtiene el próximo contenido disponible para una palabra.

        Args:
            word_id: ID de la palabra
            content_type: Tipo de contenido (EXAMPLE, BEST_OPTIONS, etc)

        Returns:
            ID del contenido o None si no hay disponible
        """
        ...

    def get_word_id(self, content_id: int, content_type: ContentType) -> Optional[int]:
        """
        Obtiene el word_id asociado a un contenido.

        Args:
            content_id: ID del contenido
            content_type: Tipo de contenido (EXAMPLE, BEST_OPTIONS, etc)

        Returns:
            ID de la palabra o None
        """
        ...

    def get_target_word_ids(self, content_id: int, content_type: ContentType) -> list:
        """
        Obtiene todas las palabras target de un contenido.

        Para Examples: retorna todas las palabras del ejemplo
        Para BestOptions: retorna la palabra de la pregunta

        Args:
            content_id: ID del contenido
            content_type: Tipo de contenido (EXAMPLE, BEST_OPTIONS, etc)

        Returns:
            Lista de word_ids
        """
        ...

    def is_content_learned(
        self, content_id: int, content_type: ContentType, user_id: int
    ) -> bool:
        """
        Chequea si un contenido tiene todas sus palabras target en estado LEARNED.

        Retorna True si el contenido NO es válido (todas las palabras están aprendidas).
        Retorna False si el contenido es válido (hay al menos una palabra no aprendida).

        Args:
            content_id: ID del contenido
            content_type: Tipo de contenido (EXAMPLE, BEST_OPTIONS, etc)
            user_id: ID del usuario

        Returns:
            True si todas las palabras están LEARNED (contenido inservible)
            False si hay palabras no LEARNED (contenido válido)
        """
        ...

    def mark_as_enqueued(self, content_id: int, content_type: ContentType) -> None:
        """
        Marca un contenido como encolado (enqueued=True).

        Diferentes tipos de contenido usan este flag de manera similar:
        - Examples: marca que el ejemplo fue encolado
        - BestOptions: marca que la pregunta fue encolada

        Args:
            content_id: ID del contenido
            content_type: Tipo de contenido (EXAMPLE, BEST_OPTIONS, etc)
        """
        ...

    def mark_as_consumed(self, content_id: int, content_type: ContentType) -> None:
        """
        Marca un contenido como consumido (is_consumed=True).

        El contenido consumido no debe volver a aparecer en la queue.

        Args:
            content_id: ID del contenido
            content_type: Tipo de contenido (EXAMPLE, BEST_OPTIONS, etc)
        """
        ...
