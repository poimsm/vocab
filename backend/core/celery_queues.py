"""
Configuración centralizada de colas Celery.

Define todas las colas disponibles como constantes para evitar strings hardcodeados.
Se usa en los decoradores @celery_app.task(queue=...) y @subscribe_to(queue_name=...)
"""


# Constantes de colas - Usar directamente en decoradores
QUEUE_AI = "ai_queue"
QUEUE_BACKGROUND = "background_queue"


class CeleryQueue:
    """Contenedor de constantes de colas Celery."""

    # Cola para tareas que requieren IA (procesamiento secuencial, alta carga computacional)
    AI = QUEUE_AI

    # Cola para tareas generales de background (procesamiento en segundo plano)
    BACKGROUND = QUEUE_BACKGROUND
