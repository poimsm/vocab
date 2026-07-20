# backend/routes/celery.py
from fastapi import APIRouter
from pydantic import BaseModel
from tasks.test import procesar_tarea_pesada
from celery.result import AsyncResult

router = APIRouter()

# Schema Pydantic para validar el body en JSON
class TareaRequest(BaseModel):
    dato: str

@router.post("/procesar")
def disparar_tarea(body: TareaRequest):
    task = procesar_tarea_pesada.delay(body.dato)
    
    return {
        "message": "Tarea enviada al worker correctamente",
        "task_id": task.id
    }

@router.get("/tarea/{task_id}")
def obtener_estado_tarea(task_id: str):    
    result = AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None
    }