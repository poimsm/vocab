from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import joinedload
from sqlmodel import Session, func, or_, select
from logging_client import logger
from models import ContentQueue, ContentQueueStatus

import random
from models import (
    Example,
    ExampleWord,
    WordStatistics,
    ContentType,
    ExampleType,
    Word,
)


class ExampleRepository:
    """
    Repository para la gestión de Examples.
    """

    def __init__(self, session: Session):
        self.session = session

    def get_available_content_for_path(self, user_id: int) -> List[int]:
        """
        Obtiene IDs de examples pristine que no están en ContentQueue.

        Estos examples pueden ser reutilizados en lugar de generar nuevos.
        """

        # Obtener IDs de examples ya encolados
        enqueued_ids = self.session.exec(
            select(ContentQueue.content_id)
            .where(
                ContentQueue.user_id == user_id,
                ContentQueue.type == ContentType.EXAMPLE,
                ContentQueue.status == ContentQueueStatus.PENDING,
            )
        ).all()

        enqueued_ids = set(enqueued_ids)

        # Obtener examples pristine que no estén encolados
        examples = self.session.exec(
            select(Example.id)
            .where(
                Example.id.notin_(enqueued_ids) if enqueued_ids else True,
            )
        ).all()

        return examples

    def get_available_content_for_word(self, word_id: int) -> Optional[int]:
        """
        Obtiene el próximo example disponible para una palabra específica.

        Un example está disponible si:
        - Contiene la palabra (a través de ExampleWord)
        - Es de tipo EXPLORER
        - No ha sido encolado aún (enqueued=False)
        - No está en ContentQueue (PENDING)

        Retorna el example con la secuencia más baja (el más antiguo).
        """

        example_id = self.session.exec(
            select(Example.id)
            .join(ExampleWord, Example.id == ExampleWord.example_id)
            .where(
                ExampleWord.word_id == word_id,
                Example.type == ExampleType.EXPLORE,
                Example.enqueued == False
            )
            .order_by(Example.sequence.asc())
        ).first()

        return example_id

    def get_word_ids(self, example_id: int) -> List[int]:
        """
        Obtiene los IDs de las palabras asociadas a un example.
        """
        word_ids = self.session.exec(
            select(ExampleWord.word_id)
            .where(ExampleWord.example_id == example_id)
        ).all()

        return word_ids

    def save(self, example: Example) -> Example:
        """
        Guarda un example en la base de datos.
        """
        self.session.add(example)
        self.session.commit()
        self.session.refresh(example)
        return example

    def segment_example_text(self, example: Example) -> List[Dict[str, Any]]:
        """
        Segmenta el texto de un ejemplo en chunks, marcando qué parts contienen target words.

        Retorna una lista de diccionarios con:
        - text: str
        - is_highlighted: bool
        - target_word: Optional[Dict] con id, main, type, meaning, level, is_boosted, batch_id
        """
        # Obtener las palabras asociadas al ejemplo
        example_words = self.session.exec(
            select(ExampleWord, Word)
            .join(Word, ExampleWord.word_id == Word.id)
            .where(ExampleWord.example_id == example.id)
        ).all()

        if not example_words:
            # Si no hay palabras, retornar el texto completo sin resaltar
            return [
                {
                    "text": example.text,
                    "is_highlighted": False,
                    "target_word": None,
                }
            ]

        # Crear un mapa de texto_form -> Word para búsqueda rápida
        word_map = {}
        for example_word, word in example_words:
            text_form = example_word.text_form
            word_map[text_form.lower()] = {
                "id": word.id,
                "main": word.main,
                "type": "word",
                "meaning": word.meaning,
                "level": word.level,
                "is_boosted": word.is_boosted,
            }

        # Buscar todas las ocurrencias de palabras en el texto
        text = example.text
        segments = []
        current_pos = 0

        # Encontrar todas las palabras en orden de aparición
        words_found = []
        for word_form in word_map.keys():
            # Buscar todas las ocurrencias de esta palabra (case-insensitive)
            start_pos = 0
            while True:
                pos = text.lower().find(word_form, start_pos)
                if pos == -1:
                    break
                words_found.append(
                    {
                        "start": pos,
                        "end": pos + len(word_form),
                        "word_form": word_form,
                        "actual_text": text[pos : pos + len(word_form)],
                    }
                )
                start_pos = pos + 1

        # Ordenar por posición de inicio
        words_found.sort(key=lambda x: x["start"])

        # Segmentar el texto
        current_pos = 0
        for word_found in words_found:
            start = word_found["start"]
            end = word_found["end"]
            word_form = word_found["word_form"]
            actual_text = word_found["actual_text"]

            # Agregar texto antes de la palabra
            if current_pos < start:
                segments.append(
                    {
                        "text": text[current_pos:start],
                        "is_highlighted": False,
                        "target_word": None,
                    }
                )

            # Agregar la palabra resaltada
            segments.append(
                {
                    "text": actual_text,
                    "is_highlighted": True,
                    "target_word": word_map[word_form],
                }
            )

            current_pos = end

        # Agregar texto restante después de la última palabra
        if current_pos < len(text):
            segments.append(
                {
                    "text": text[current_pos:],
                    "is_highlighted": False,
                    "target_word": None,
                }
            )

        return segments

