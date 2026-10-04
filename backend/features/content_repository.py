"""
Implementación unificada de ContentRepository para todos los tipos de contenido.
Maneja examples, best_options y otros tipos de contenido.
"""
from typing import Optional
from sqlmodel import Session, func, select
from logging_client import logger
from features.examples.models import Example
from features.best_options.models import BestOption
from features.words.models import WordStatistics, ExampleWord, Word
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
            # Examples disponibles con la palabra
            count = self.db.exec(
                select(func.count(Example.id))
                .join(
                    WordStatistics,
                    (WordStatistics.word_id == word_id)
                    & (WordStatistics.type == ContentType.EXAMPLE),
                )
                .where(
                    WordStatistics.learning_state != LearningState.LEARNED,
                )
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
            # Buscar example que contenga la palabra
            example_id = self.db.exec(
                select(Example.id)
                .join(
                    WordStatistics,
                    (WordStatistics.word_id == word_id)
                    & (WordStatistics.type == ContentType.EXAMPLE),
                )
                .where(
                    WordStatistics.learning_state != LearningState.LEARNED,
                )
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
            # Obtener primera palabra target del example
            return self.example_repo.get_first_target_word_id(content_id)

        elif content_type == ContentType.BEST_OPTIONS:
            # Delegar a BestOptionRepository
            return self.best_option_repo.get_word_id(content_id)

        return None

    def get_target_word_ids(self, content_id: int, content_type: ContentType) -> list:
        """Obtiene todas las palabras target de un contenido"""
        from features.words.models import ExampleWord
        from features.best_options.models import BestOption

        if content_type == ContentType.EXAMPLE:
            # Obtener todas las palabras del example
            example_words = self.db.exec(
                select(ExampleWord).where(ExampleWord.example_id == content_id)
            ).all()
            return [ew.word_id for ew in example_words]

        elif content_type == ContentType.BEST_OPTIONS:
            # Para best_option, solo la palabra asociada
            best_option = self.db.exec(
                select(BestOption).where(BestOption.id == content_id)
            ).first()
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

