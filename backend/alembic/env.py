from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from sqlmodel import SQLModel
import os

# Import all models to register them with SQLAlchemy/SQLModel
from auth.models import User, UserProfile
from features.words.models import Word, WordLevel, WordStatistics
from features.examples.models import Example, ExampleType, ExploreConfiguration
from features.best_options.models import BestOption
from features.quick_write.models import QuickWrite
from features.collocations.models import Collocation
from features.vocab_imgs.models import VocabImage, VocabImageWord
from core.learning_path.models import (
    LearningPath, LearningPathHistory, LearningPathCursor,
    LearningPathQueue, LearningPathAnomaly, PathRepairLog, LearningPathGenerationMonitor
)
from core.config.models import GlobalConfiguration, UserConfiguration
from core.activity.models import ActivityType, UserActivity
from core.sync.models import ResolveLock
from core.generation_ai.models import GenerationAIRegistry
from core.boost.models import BoostGenerationMonitor
from core.central_queue.models import CentralLockState, CentralQueue
from core.delivery.models import DeliveryBuffer
from core.explore.models import ExploreSession

from alembic import context
from logging_client import logger

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # 1. Obtener la sección de configuración del alembic.ini
    configuration = config.get_section(config.config_ini_section) or {}
    
    # 2. Reemplazar la URL del .ini por la variable de entorno del contenedor
    configuration["sqlalchemy.url"] = os.getenv("DATABASE_URL")

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
