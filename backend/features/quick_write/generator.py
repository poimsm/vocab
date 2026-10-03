"""
Wrapper para lanzar tareas de generación de quick write exercises.

Las tareas reales están en features.quick_write.tasks.
"""

from typing import List


class QuickWriteGenerator:
    """Interfaz para solicitar generación de quick write exercises."""

    @staticmethod
    def generate(user_id: int, word_ids: List[int], amount: int = 10):
        """
        Solicita la generación de ejercicios quick write para una lista de palabras.

        La tarea se ejecuta en background en el worker_ai.
        """
        from features.quick_write.tasks import generate_quick_write_exercises_task
        return generate_quick_write_exercises_task.delay(user_id, word_ids, amount)
