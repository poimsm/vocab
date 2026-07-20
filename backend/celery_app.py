# backend/celery_app.py
import os
import pkgutil
import tasks
from celery import Celery

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")

celery_app = Celery(
    "worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
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
    imports=task_modules  # Carga automática de todos los subarchivos en tasks/
)
