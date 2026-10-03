from fastapi import FastAPI
from logging_client import logger

from fastapi.middleware.cors import CORSMiddleware

from db import engine

# MODELS - Import all models to register them with SQLAlchemy
from auth.models import User, UserProfile
from features.words.models import Word, WordLevel, WordStatistics, ExampleWord
from features.examples.models import Example, ExampleType, ExploreConfiguration
from features.best_options.models import BestOption
from features.quick_write.models import QuickWrite
from features.collocations.models import Collocation
from core.learning_path.models import (
    LearningPath, LearningPathHistory, LearningPathCursor,
    LearningPathQueue, LearningPathAnomaly, PathRepairLog, LearningPathGenerationMonitor
)
from core.config.models import GlobalConfiguration, UserConfiguration
from core.activity.models import ActivityType, UserActivity
from core.sync.models import ResolveLock
from core.generation_ai.models import GenerationAIRegistry

# ROUTES - Import directly from route modules to avoid circular imports
from features.examples.routes import router as examples_router
from features.words.routes import router as words_router
from features.best_options.routes import router as best_options_router
from features.quick_write.routes import router as quick_write_router
from features.collocations.routes import router as collocation_router
from auth import routes as auth
from test import routes as test
from activity import activity_routes as activity

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
app.include_router(examples_router, prefix="/examples", tags=["examples"])
app.include_router(words_router, prefix="/words", tags=["words"])
app.include_router(best_options_router, prefix="/best-options", tags=["best_options"])
app.include_router(quick_write_router, prefix="/quick-write", tags=["quick_write"])
app.include_router(collocation_router, prefix="/collocations", tags=["collocations"])
app.include_router(activity.router)
app.include_router(test.router, prefix="/test", tags=["test"])

@app.on_event("startup")
def startup():
    logger.info("Vocab backend started successfully!")