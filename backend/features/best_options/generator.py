"""
Wrapper para lanzar tareas de generación de best options.

Las tareas reales están en features.best_options.tasks.
"""

from typing import List


class BestOptionGenerator:
    """Interfaz para solicitar generación de best options."""

    @staticmethod
    def generate(user_id: int, word_ids: List[int]):
        """
        Solicita la generación de ejercicios best_option para una lista de palabras.

        La tarea se ejecuta en background en el worker_ai.
        """
        from features.best_options.tasks import generate_best_options_task
        return generate_best_options_task.delay(user_id, word_ids)
