from fastapi import FastAPI
from logging_client import logger

from fastapi.middleware.cors import CORSMiddleware

# ✅ Inicializar Celery PRIMERO para registrar todos los suscriptores de eventos
from celery_app import celery_app  # noqa

# ✅ RealtimeEventBus (Redis pub/sub para eventos en tiempo real)
from core.realtime_event_bus import get_realtime_bus  # noqa

# ✅ Importar todos los tasks para registrar sus suscriptores de eventos
from core.boost import tasks as boost_tasks  # noqa
from core.delivery import tasks as delivery_tasks  # noqa
from core.generation_ai import tasks as generation_ai_tasks  # noqa
from core.learning_path import tasks as learning_path_tasks  # noqa
from core.central_queue import tasks as central_queue_tasks  # noqa
from features.examples import tasks as examples_tasks  # noqa
from features.best_options import tasks as best_options_tasks  # noqa
from features.words import tasks as words_tasks  # noqa

from db import engine

# MODELS - Import all models to register them with SQLAlchemy
from auth.models import User, UserProfile
from features.words.models import Word, WordLevel, WordStatistics
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

    # Verificar Redis para RealtimeEventBus
    try:
        bus = get_realtime_bus()
        if bus.health_check():
            logger.info("✅ Redis conectado - RealtimeEventBus listo para eventos en tiempo real")
            # Suscribirse a TODOS los eventos con patrón wildcard
            # Esto permite que callbacks se registren dinámicamente después del startup
            def global_callback(channel: str, data: dict):
                """Callback global que dispara handlers registrados dinámicamente"""
                logger.debug(f"[RealtimeEventBus] Event on channel: {channel}")
                pass  # Los handlers específicos se registran via subscribe()

            bus.subscribe("*", global_callback)
            # Iniciar listener global en background thread (non-blocking)
            bus.listen_async()
            logger.info("✅ RealtimeEventBus global listener iniciado (suscrito a *)")
        else:
            logger.warning("⚠️ Redis no disponible - RealtimeEventBus deshabilitado")
    except Exception as e:
        logger.warning(f"⚠️ Error al conectar con Redis: {e}")