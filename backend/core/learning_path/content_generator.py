"""
Interfaz para generadores de contenido.
Maneja generación de ejemplos, best_options, etc.
"""
from typing import Protocol, List, Optional
from core.enums import ContentType
from features.words.models import Word


class ContentGenerator(Protocol):
    """
    Contrato único para generar contenido de cualquier tipo.
    Usado por ContentPlanner para solicitar generación de contenido.

    El generador puede manejar ejemplos, best_options, collocations, etc.
    El tipo se especifica mediante content_type.
    """

    def generate(
        self,
        user_id: int,
        word_ids: List[int],
        content_type: ContentType,
        amount: Optional[int] = None,
        session=None,
    ) -> None:
        """
        Genera contenido para las palabras especificadas.

        Args:
            user_id: ID del usuario
            word_ids: Lista de word_ids para generar contenido
            content_type: Tipo de contenido (EXAMPLE, BEST_OPTIONS, etc)
            amount: Cantidad de contenido a generar (opcional, depende del tipo)
            session: Sesión de base de datos (opcional, si es necesaria)
        """
        ...
