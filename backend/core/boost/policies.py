# src/core/boost/policies.py

class BoostLearningPolicy:
    """
    Política que rige el comportamiento pedagógico y de progreso 
    de una palabra cuando tiene el Boost activado.
    """

    @staticmethod
    def should_freeze_learning_state(is_boosted: bool) -> bool:
        """
        Determina si se debe bloquear la transición de estado formal de la palabra
        (NEW -> LEARNING -> REINFORCING -> LEARNED).
        
        Si está boosteada, retorna True para indicar a los evaluadores que 
        NO modifiquen la curva de progreso oficial.
        """
        return is_boosted

    @staticmethod
    def allows_infinite_generation(is_boosted: bool) -> bool:
        """
        Determina si la palabra puede ignorar las cuotas o límites habituales 
        de generación de contenido por unidad/nivel.
        """
        return is_boosted

    @staticmethod
    def should_bypass_spaced_repetition(is_boosted: bool) -> bool:
        """
        Indica si las tareas de repaso agendado (Spaced Repetition) deben 
        pausarse mientras la palabra esté siendo 'forzada' mediante Boost.
        """
        return is_boosted