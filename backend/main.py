from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlmodel import SQLModel
from db import engine
import models

# CORRECCIÓN: Eliminamos el prefijo 'app.' porque están al mismo nivel que main.py
from db import engine
from routes import (
    words,
    examples,
)

app = FastAPI()

# Como Nginx ahora está en el medio gestionando el puerto 80, 
# permitimos todos los orígenes para no tener problemas de CORS en desarrollo.
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 👇 Tus rutas configuradas correctamente
app.include_router(words.router, prefix="/words", tags=["words"])
app.include_router(examples.router, prefix="/examples", tags=["examples"])


@app.on_event("startup")
def startup():
    SQLModel.metadata.create_all(engine)