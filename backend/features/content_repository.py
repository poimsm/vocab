"""
Implementación unificada de ContentRepository para todos los tipos de contenido.
Maneja examples, best_options y otros tipos de contenido.
"""
from typing import Optional
from sqlmodel import Session, func, select
from logging_client import logger
from features.examples.models import Example
from features.best_options.models import BestOption
from features.words.models import WordStatistics, Word
from core.enums import ContentType
from core.learning_path.models import LearningState
from features.examples.repository import ExampleRepository
from features.best_options.repository import BestOptionRepository


class UnifiedContentRepository:
    """
    Repositorio único que implementa ContentRepository Protocol.
    Maneja múltiples tipos de contenido delegando a los repositorios específicos.
    """

    def __init__(self, db: Session):
        self.db = db
        self.example_repo = ExampleRepository(db)
        self.best_option_repo = BestOptionRepository(db)

    def count_available_for_word(self, word_id: int, content_type: ContentType) -> int:
        """Cuenta contenido disponible para una palabra según el tipo"""
        if content_type == ContentType.EXAMPLE:
            # Chequear si la palabra ya está LEARNED
            word_stats = self.db.exec(
                select(WordStatistics)
                .where(
                    WordStatistics.word_id == word_id,
                    WordStatistics.type == ContentType.EXAMPLE
                )
            ).first()

            if word_stats and word_stats.learning_state == LearningState.LEARNED:
                return 0

            # Contar ejemplos que enseñan esta palabra
            count = self.db.exec(
                select(func.count(Example.id))
                .where(Example.word_id == word_id)
            ).first() or 0
            return count

        elif content_type == ContentType.BEST_OPTIONS:
            # Delegar a BestOptionRepository
            return self.best_option_repo.count_available_best_options_for_word(word_id)

        return 0

    def get_available_content_for_word(
        self, word_id: int, content_type: ContentType
    ) -> Optional[int]:
        """Obtiene el próximo contenido disponible para una palabra según el tipo"""
        if content_type == ContentType.EXAMPLE:
            # Chequear si la palabra ya está LEARNED
            word_stats = self.db.exec(
                select(WordStatistics)
                .where(
                    WordStatistics.word_id == word_id,
                    WordStatistics.type == ContentType.EXAMPLE
                )
            ).first()

            if word_stats and word_stats.learning_state == LearningState.LEARNED:
                return None

            # Buscar example que enseñe la palabra
            example_id = self.db.exec(
                select(Example.id)
                .where(Example.word_id == word_id)
                .order_by(Example.created_at.asc())
                .limit(1)
            ).first()
            return example_id

        elif content_type == ContentType.BEST_OPTIONS:
            # Delegar a BestOptionRepository
            return self.best_option_repo.get_available_content_for_word(word_id)

        return None

    def get_word_id(self, content_id: int, content_type: ContentType) -> Optional[int]:
        """Obtiene el word_id de un contenido según el tipo"""
        if content_type == ContentType.EXAMPLE:
            # Obtener palabra target del example
            example = self.db.get(Example, content_id)
            if example:
                return example.word_id
            return None

        elif content_type == ContentType.BEST_OPTIONS:
            # Delegar a BestOptionRepository
            return self.best_option_repo.get_word_id(content_id)

        return None

    def get_target_word_ids(self, content_id: int, content_type: ContentType) -> list:
        """Obtiene todas las palabras target de un contenido"""
        from features.best_options.models import BestOption

        if content_type == ContentType.EXAMPLE:
            # Obtener la palabra del example (solo una)
            example = self.db.get(Example, content_id)
            if example and example.word_id:
                return [example.word_id]
            return []

        elif content_type == ContentType.BEST_OPTIONS:
            # Para best_option, solo la palabra asociada
            best_option = self.db.get(BestOption, content_id)
            return [best_option.word_id] if best_option else []

        return []

    def is_content_learned(
        self, content_id: int, content_type: ContentType, user_id: int
    ) -> bool:
        """
        Chequea si todas las palabras target de un contenido están en estado LEARNED.
        Retorna True si el contenido es inservible (todas las palabras LEARNED).
        """
        from features.words.models import Word

        target_word_ids = self.get_target_word_ids(content_id, content_type)

        if not target_word_ids:
            # Si no hay palabras, considerar el contenido como inservible
            return True

        # Contar cuántas palabras están en estado LEARNED
        learned_count = self.db.exec(
            select(func.count(WordStatistics.id))
            .join(Word, WordStatistics.word_id == Word.id)
            .where(
                WordStatistics.word_id.in_(target_word_ids),
                WordStatistics.type == content_type,
                WordStatistics.learning_state == LearningState.LEARNED,
                Word.user_id == user_id,
            )
        ).first() or 0

        # Si TODAS las palabras están LEARNED, el contenido es inservible
        return learned_count == len(target_word_ids)

    def mark_as_enqueued(self, content_id: int, content_type: ContentType) -> None:
        """Marca un contenido como encolado"""
        if content_type == ContentType.EXAMPLE:
            example = self.db.get(Example, content_id)
            if example:
                example.enqueued = True
                self.db.add(example)
                self.db.commit()

        elif content_type == ContentType.BEST_OPTIONS:
            best_option = self.db.get(BestOption, content_id)
            if best_option:
                best_option.enqueued = True
                self.db.add(best_option)
                self.db.commit()

