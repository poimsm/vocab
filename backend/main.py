from fastapi import FastAPI
from logging_client import logger

from fastapi.middleware.cors import CORSMiddleware

from db import engine
import models

from examples import example_routes as examples
from words import word_routes as words
from best_options import best_options_routes as best_options
from auth import routes as auth
from learning_path import routes as learning_path

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
app.include_router(best_options.router, prefix="/best-options", tags=["best_options"])
app.include_router(learning_path.router, prefix="/learning-path", tags=["learning_path"])

@app.on_event("startup")
def startup():
    logger.info("Vocab backend started successfully!")