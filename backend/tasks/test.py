# backend/tasks.py
import time
from celery_app import celery_app
from logging_config import logger

@celery_app.task(name="tasks.test.procesar_palabra")
def procesar_tarea_pesada(parametro: str):
    logger.info(f"Starting heavy task with parameter: {parametro}")
    # Simula un trabajo pesado (e.g. llamada a la API de IA o procesamiento de datos)
    time.sleep(5)
    logger.info(f"Heavy task completed with parameter: {parametro}")
    return {"status": "SUCCESS", "data": parametro}