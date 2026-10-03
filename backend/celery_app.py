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

# 2. Generar las colas automáticamente basadas en las suscripciones registradas
from core.event_bus import get_event_queues

event_queues = get_event_queues()

# Colas de propósito general (si quieres colas adicionales que no sean basadas en eventos)
app_events_exchange = Exchange('app_events', type='topic', durable=True)
default_queues = [
    Queue(
        "ai_queue",
        exchange=app_events_exchange,
        routing_key="ai.#",
        durable=True
    ),
    Queue(
        "background_queue",
        exchange=app_events_exchange,
        routing_key="background.#",
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

    # Combina colas de eventos + colas por defecto
    task_queues=event_queues + default_queues,
)
