# backend/celery_app.py
import os
import pkgutil
import tasks
from celery import Celery
from celery.schedules import crontab
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

# Configure Celery
celery_app.conf.update(
    worker_log_format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    worker_task_log_format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
)

# 1. Escaneamos dinámicamente todos los subarchivos .py dentro del paquete tasks/
task_modules = [
    f"tasks.{name}"
    for _, name, ispkg in pkgutil.iter_modules(tasks.__path__)
    if not ispkg
]

# 2. Registramos los módulos automáticamente en la configuración de Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=1,  # Procesa estrictamente una tarea por vez
    imports=task_modules,  # Carga automática de todos los subarchivos en tasks/
    # Celery Beat: Tareas programadas
    beat_schedule={
        "spaced-repetition-daily": {
            "task": "tasks.examples.spaced_repetition_daily",
            "schedule": crontab(hour=2, minute=0),  # Ejecutar diariamente a las 2 AM UTC
        },
    },
)
