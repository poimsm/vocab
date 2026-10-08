from typing import List
from core.boost.dtos import SkillDemand

class BoostDemandStrategy:
    """
    Define las recetas de contenido que se solicitarán a la cola de generación
    según la necesidad del negocio.
    """

    @staticmethod
    def get_refill_pack() -> List[SkillDemand]:
        """
        Receta única de reposición: Lo que se solicita cuando se booste una palabra.

        quantity = cantidad exacta de ejercicios a generar
        (se calcula automáticamente cuántas tareas de IA se necesitan)
        """
        return [
            SkillDemand(skill_type="example", quantity=10, process_event='generation.content_requested'),
            SkillDemand(skill_type="best_options", quantity=10, process_event='generation.content_requested'),
        ]