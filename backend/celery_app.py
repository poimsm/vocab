# backend/celery_app.py
import os
from celery import Celery
from kombu import Exchange, Queue
from logging_client import logger

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")

logger.info("Initializing Celery application")
celery_app = Celery(
    "worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)
logger.info("Celery application created successfully")

# 1. Descubrir y registrar todas las tareas (para que se ejecuten los decoradores @subscribe_to)
# Celery busca automáticamente módulos llamados 'tasks.py' en los paquetes listados
celery_app.autodiscover_tasks([
    "features.examples",
    "features.best_options",
    "features.words",
    "features.quick_write",
    "core.boost",
    "core.central_queue",
    "core.delivery",
    "core.generation_ai",
    "core.learning_path",
])

# Importar explícitamente para asegurar que los decoradores @subscribe_to se ejecuten
# Esto garantiza que los eventos encuentren sus suscriptores antes de ser publicados
try:
    import core.learning_path.tasks  # noqa
    import core.generation_ai.tasks  # noqa
    import core.boost.tasks  # noqa
    import features.examples.tasks  # noqa
    logger.info("[Celery] Tareas cargadas explícitamente")
except ImportError as e:
    logger.warning(f"[Celery] Error importando algunas tareas: {e}")

# 2. Colas estáticas con patrones para AI y Background
app_events_exchange = Exchange('app_events', type='topic', durable=True)
default_queues = [
    Queue(
        "ai_queue",
        exchange=app_events_exchange,
        routing_key="ai.#",  # ← Todos los eventos que empiezan con "ai."
        durable=True
    ),
    Queue(
        "background_queue",
        exchange=app_events_exchange,
        routing_key="background.#",  # ← Todos los eventos que empiezan con "background."
        durable=True
    ),
]

# 3. Configuración principal de Celery con todas las colas
celery_app.conf.update(
    worker_log_format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    worker_task_log_format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',

    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=1,

    # Usa SOLO las colas estáticas con patrones claros
    task_queues=default_queues,
)
