"""
Wrapper para lanzar tareas de generación de palabras.

Las tareas reales están en features.words.tasks (Celery autodiscover las encuentra).
Este módulo proporciona una interfaz conveniente para lanzar las tareas.
"""

from typing import List
from logging_client import logger


class WordGenerator:
    """Interfaz para solicitar generación de palabras desde el backend."""

    @staticmethod
    def create_single(user_id: int, text: str, target_word: str = None):
        """
        Solicita la creación de una palabra individual desde texto.

        La tarea se ejecuta en background en el worker_ai.
        """
        from features.words.tasks import create_single_task
        return create_single_task.delay(user_id, text, target_word)

    @staticmethod
    def create_bulk(user_id: int, texts: List[str]):
        """
        Solicita la creación de múltiples palabras desde una lista de textos.

        Las tareas se ejecutan en background en el worker_ai, procesando en chunks.
        """
        from features.words.tasks import create_bulk_task
        return create_bulk_task.delay(user_id, texts)

    @staticmethod
    def generate_boost_examples(user_id: int, word_id: int):
        """
        Solicita la generación de ejemplos adicionales para una palabra boosteada.

        La tarea se ejecuta en background en el worker_ai.
        """
        from features.words.tasks import generate_boost_examples
        return generate_boost_examples.delay(user_id, word_id)
