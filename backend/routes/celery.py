# backend/routes/celery.py
from fastapi import APIRouter
from pydantic import BaseModel
from tasks.test import procesar_tarea_pesada
from celery.result import AsyncResult
from logging_client import logger
from decorators import log_endpoint

router = APIRouter()

# Schema Pydantic para validar el body en JSON
class TareaRequest(BaseModel):
    dato: str

@router.post("/procesar")
@log_endpoint
def disparar_tarea(body: TareaRequest):
    logger.info(f"Starting Celery task with data: {body.dato}")
    task = procesar_tarea_pesada.delay(body.dato)
    logger.info(f"Task queued with ID: {task.id}")

    return {
        "message": "Tarea enviada al worker correctamente",
        "task_id": task.id
    }

@router.get("/tarea/{task_id}")
@log_endpoint
def obtener_estado_tarea(task_id: str):
    logger.debug(f"Checking status for task ID: {task_id}")
    result = AsyncResult(task_id)
    logger.debug(f"Task {task_id} status: {result.status}")
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None
    }