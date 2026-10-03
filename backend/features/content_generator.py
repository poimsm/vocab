"""
Implementación unificada de ContentGenerator para todos los tipos de contenido.
Maneja ejemplos, best_options y otros tipos de contenido.
"""
from typing import List, Optional
from core.enums import ContentType


class UnifiedContentGenerator:
    """
    Generador único que implementa ContentGenerator Protocol.
    Maneja múltiples tipos de contenido delegando a los generadores específicos.
    """

    def generate(
        self,
        user_id: int,
        word_ids: List[int],
        content_type: ContentType,
        amount: Optional[int] = None,
        session=None,
    ) -> None:
        """Genera contenido según el tipo"""
        if content_type == ContentType.EXAMPLE:
            self._generate_examples(user_id, word_ids, amount, session)

        elif content_type == ContentType.BEST_OPTIONS:
            self._generate_best_options(user_id, word_ids)

    def _generate_examples(
        self,
        user_id: int,
        word_ids: List[int],
        amount: Optional[int] = None,
        session=None,
    ) -> None:
        """Genera ejemplos para las palabras"""
        from features.examples.generator import ExampleGenerator

        ExampleGenerator.generate_simple(
            user_id=user_id,
            word_ids=word_ids,
            amount=amount or 10,
            session=session,
        )

    def _generate_best_options(
        self,
        user_id: int,
        word_ids: List[int],
    ) -> None:
        """Genera best_options para las palabras"""
        from features.best_options.generator import BestOptionGenerator

        BestOptionGenerator.generate(
            user_id=user_id,
            word_ids=word_ids,
        )
