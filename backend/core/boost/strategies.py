from typing import List
from core.boost.dtos import SkillDemand

class BoostDemandStrategy:
    """
    Define las recetas de contenido que se solicitarán a la cola de generación
    según la necesidad del negocio.
    """

    @staticmethod
    def get_initial_boost_pack() -> List[SkillDemand]:
        """
        Receta inicial: Lo que se envía a generar en el instante
        en que el usuario presiona 'Boostear' por primera vez.
        """
        return [
            SkillDemand(skill_type="examples", quantity=7, process_event='event.generation.content_requested'),
            # SkillDemand(skill_type="best_options", quantity=2, process_event=''),
        ]

    @staticmethod
    def get_refill_pack() -> List[SkillDemand]:
        """
        Receta de reposición: Lo que se solicita para mantener la generación 
        infinita a medida que el usuario va consumiendo ejercicios en el buffer.
        """
        return [
            SkillDemand(skill_type="examples", quantity=5, process_event='event.generation.content_requested'),
            # SkillDemand(skill_type="best_options", quantity=1, process_event=''),
        ]