# backend/tasks.py
import time
from celery_app import celery_app

@celery_app.task(name="tasks.test.procesar_palabra")
def procesar_tarea_pesada(parametro: str):
    # Simula un trabajo pesado (e.g. llamada a la API de IA o procesamiento de datos)
    time.sleep(5) 
    print(f"Tarea completada con el parámetro: {parametro}")
    return {"status": "SUCCESS", "data": parametro}