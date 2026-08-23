import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import joinedload
from sqlmodel import Session, func, or_, select

from logging_client import logger
from utils.paginator import paginate_query

from models import (
    ContentType,
    ExampleType,
    Word,
    WordStatistics,
    ExampleWord,
    Example,
    WordLevel,
    LearningState,
)


class WordRepository:
    """Repository para gestión de palabras"""

    def __init__(self, session: Session):
        self.session = session

    def get_words(
        self,
        user_id: int,
        sort: str = "newest",
        page: int = 1,
        limit: int = 15,
        learning_state: str = None,
    ) -> Dict[str, Any]:
        """
        Obtiene palabras del usuario con paginación.

        Retorna palabras junto con conteo de ejemplos EXPLORE.

        learning_state: Filter by learning state category
          - new: Only NEW words
          - learning: LEARNING + REINFORCING + SPACING + ALMOST_LEARNED
          - mastered: LEARNED + REVIEW
        """
        # Obtener palabras del usuario
        statement = (
            select(Word)
            .where(Word.user_id == user_id, Word.is_active == True)
        )

        # Filtrar por learning_state si se proporciona
        if learning_state:
            # Map user-friendly categories to internal states
            state_map = {
                'new': LearningState.NEW,
                'learning': [LearningState.LEARNING, LearningState.REINFORCING, LearningState.SPACING, LearningState.ALMOST_LEARNED],
                'mastered': [LearningState.LEARNED, LearningState.REVIEW],
            }

            states = state_map.get(learning_state)
            if states:
                if not isinstance(states, list):
                    states = [states]
                # Use subquery to get distinct word IDs to avoid duplicates from multiple WordStatistics rows
                # Filter by EXAMPLE type to be consistent with what users see in examples feed
                subquery = (
                    select(func.distinct(Word.id))
                    .join(WordStatistics)
                    .where(
                        Word.user_id == user_id,
                        Word.is_active == True,
                        WordStatistics.type == ContentType.EXAMPLE,
                        WordStatistics.learning_state.in_(states)
                    )
                )
                statement = statement.where(Word.id.in_(subquery))

        # Aplicar ordenamiento
        if sort == "newest":
            statement = statement.order_by(Word.created_at.desc())
        elif sort == "oldest":
            statement = statement.order_by(Word.created_at.asc())
        elif sort == "alphabetical":
            statement = statement.order_by(Word.main.asc())

        # Obtener total de palabras (con filtro si aplica)
        count_statement = (
            select(func.count()).select_from(Word).where(
                Word.user_id == user_id, Word.is_active == True
            )
        )

        if learning_state:
            # Map user-friendly categories to internal states
            state_map = {
                'new': LearningState.NEW,
                'learning': [LearningState.LEARNING, LearningState.REINFORCING, LearningState.SPACING, LearningState.ALMOST_LEARNED],
                'mastered': [LearningState.LEARNED, LearningState.REVIEW],
            }

            states = state_map.get(learning_state)
            if states:
                if not isinstance(states, list):
                    states = [states]
                count_statement = (
                    select(func.count(func.distinct(Word.id)))
                    .select_from(Word)
                    .join(WordStatistics)
                    .where(
                        Word.user_id == user_id,
                        Word.is_active == True,
                        WordStatistics.type == ContentType.EXAMPLE,
                        WordStatistics.learning_state.in_(states)
                    )
                )

        total_count = self.session.exec(count_statement).one()

        # Aplicar paginación
        offset = (page - 1) * limit
        statement = statement.offset(offset).limit(limit)

        # Ejecutar query
        words = self.session.exec(statement).all()

        # Agregar conteo de ejemplos para cada palabra
        words_with_count = []
        for word in words:
            total_examples = self.get_explore_examples_count(word.id)
            words_with_count.append((word, total_examples))

        # Retornar estructura paginada
        return {
            "items": words_with_count,
            "total": total_count,
            "page": page,
            "limit": limit,
            "pages": (total_count + limit - 1) // limit,
        }

    def get(self, db: Session, word_id: int) -> Optional[Word]:
        """Obtiene una palabra por ID con relaciones cargadas"""
        return db.exec(
            select(Word)
            .where(Word.id == word_id)
            .options(joinedload(Word.statistics))
        ).first()

    def get_explore_examples_count(self, word_id: int) -> int:
        """Cuenta ejemplos EXPLORE para una palabra"""
        return self.session.exec(
            select(func.count(ExampleWord.example_id))
            .select_from(ExampleWord)
            .join(Example, ExampleWord.example_id == Example.id)
            .where(
                (ExampleWord.word_id == word_id)
                & (Example.type == ExampleType.EXPLORE)
            )
        ).first() or 0

    def get_initial_examples(self, word_id: int) -> List[str]:
        """Obtiene textos de ejemplos INITIAL para una palabra"""
        example_words = self.session.exec(
            select(ExampleWord)
            .where(ExampleWord.word_id == word_id)
            .options(joinedload(ExampleWord.example))
        ).all()

        return [
            ew.example.text
            for ew in example_words
            if ew.example.type == ExampleType.INITIAL
        ]

    def is_learned(self, word_id: int, content_type: ContentType) -> bool:
        """Verifica si una palabra está aprendida para un tipo de contenido"""
        stat = self.session.exec(
            select(WordStatistics).where(
                WordStatistics.word_id == word_id,
                WordStatistics.type == content_type,
            )
        ).first()

        if not stat:
            return False

        return stat.learning_state.value == "learned"

    def create(self, user_id: int, word_data: Dict[str, Any]) -> Word:
        """Crea una nueva palabra"""
        word = Word(
            user_id=user_id,
            main=word_data.get("main", ""),
            meaning=word_data.get("meaning"),
            synonyms=word_data.get("synonyms"),
            type=word_data.get("type"),
            frequency=word_data.get("frequency"),
            level=word_data.get("level", WordLevel.INTERMEDIATE),
            context=word_data.get("context"),
            source_text=word_data.get("source_text"),
            normalized=word_data.get("main", "").lower() if word_data.get("main") else None,
            created_at=datetime.now(timezone.utc),
        )

        self.session.add(word)
        self.session.commit()
        self.session.refresh(word)

        return word

    def update(self, word_id: int, word_data: Dict[str, Any]) -> Optional[Word]:
        """Actualiza una palabra"""
        word = self.session.get(Word, word_id)

        if not word:
            return None

        for key, value in word_data.items():
            if key not in ["id", "user_id", "created_at"]:
                setattr(word, key, value)

        self.session.add(word)
        self.session.commit()
        self.session.refresh(word)

        return word

    def toggle_favorite(self, word_id: int) -> Optional[Word]:
        """Activa/desactiva favorito de una palabra"""
        word = self.session.get(Word, word_id)

        if not word:
            return None

        word.is_favorite = not word.is_favorite
        self.session.add(word)
        self.session.commit()
        self.session.refresh(word)

        return word

    def delete(self, word_id: int) -> bool:
        """Marca una palabra como inactiva (soft delete)"""
        word = self.session.get(Word, word_id)

        if not word:
            return False

        word.is_active = False
        self.session.add(word)
        self.session.commit()

        return True

    def mark_as_learned(self, word_id: int) -> bool:
        """Marca todas las estadísticas de una palabra como LEARNED"""
        statistics = self.session.exec(
            select(WordStatistics).where(WordStatistics.word_id == word_id)
        ).all()

        if not statistics:
            return False

        for stat in statistics:
            stat.learning_state = LearningState.LEARNED
            self.session.add(stat)

        self.session.commit()
        return True
