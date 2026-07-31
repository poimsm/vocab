from fastapi import FastAPI
from logging_config import logger

from fastapi.middleware.cors import CORSMiddleware

from sqlmodel import SQLModel
from db import engine
import models

from db import engine
from routes import (
    words,
    examples,
    auth,
    celery,
    best_options,
)

app = FastAPI(redirect_slashes=False)

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

# Rutas
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(words.router, prefix="/words", tags=["words"])
app.include_router(examples.router, prefix="/examples", tags=["examples"])
app.include_router(celery.router, prefix="/celery", tags=["celery"])
app.include_router(best_options.router, prefix="/best-options", tags=["best_options"])

@app.on_event("startup")
def startup():
    SQLModel.metadata.create_all(engine)
    logger.info("Vocab backend started successfully!")