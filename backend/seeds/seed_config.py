import sys
from sqlmodel import Session, select
from db import engine
from models import ExploreConfiguration, GlobalConfiguration
from logging_config import logger

def seed_explore_configurations():
    logger.info("Loading explore configurations...")

    # Lista de configuraciones correspondientes a tus condiciones
    configs_to_load = [
        ExploreConfiguration(max_examples=15, ai_mixed_generation_amount=3, ai_simple_generation_amount=6, recycled_words_amount=0),
        ExploreConfiguration(max_examples=30, ai_mixed_generation_amount=6, ai_simple_generation_amount=6, recycled_words_amount=0),
        ExploreConfiguration(max_examples=60, ai_mixed_generation_amount=6, ai_simple_generation_amount=6, recycled_words_amount=2),
        ExploreConfiguration(max_examples=120, ai_mixed_generation_amount=6, ai_simple_generation_amount=6, recycled_words_amount=4),
        ExploreConfiguration(max_examples=999999, ai_mixed_generation_amount=6, ai_simple_generation_amount=6, recycled_words_amount=8)
    ]

    with Session(engine) as db:
        try:
            # 1. Limpiamos las configuraciones anteriores para evitar duplicados o IDs corruptos
            existing_configs = db.exec(select(ExploreConfiguration)).all()
            logger.info(f"Removing {len(existing_configs)} existing configurations")
            for config in existing_configs:
                db.delete(config)
            db.flush()

            for config in configs_to_load:
                db.add(config)

            db.commit()
            logger.info("Explore configurations loaded successfully.")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error loading configurations: {e}")
            sys.exit(1)

def seed_global_configurations():
    logger.info("Loading global configurations...")

    # Global configuration values
    configs_to_load = [
        GlobalConfiguration(
            key="TARGET_CYCLE_SEEN",
            value="3",
            description="Number of times a word must be seen in the current cycle to be marked as learned"
        ),
        GlobalConfiguration(
            key="THRESHOLD_FOR_TRANSITION",
            value="4",
            description="Minimum number of unlearned words to trigger transition to next batch"
        ),
        GlobalConfiguration(
            key="CHUNK_SIZE",
            value="15",
            description="Size of chunks for processing bulk word imports"
        ),
        GlobalConfiguration(
            key="BATCH_DEFAULT_CAPACITY",
            value="15",
            description="Default capacity (max words) for new batches"
        ),
        GlobalConfiguration(
            key="DEFAULT_PRIORITY_WORDS_LIMIT",
            value="10",
            description="Default limit for fetching priority words"
        ),
        GlobalConfiguration(
            key="REFILL_QUEUE_EMERGENCY_LIMIT",
            value="8",
            description="Limit for priority words when queue needs emergency refill"
        ),
    ]

    with Session(engine) as db:
        try:
            # 1. Clean existing global configurations to avoid duplicates
            existing_configs = db.exec(select(GlobalConfiguration)).all()
            logger.info(f"Removing {len(existing_configs)} existing global configurations")
            for config in existing_configs:
                db.delete(config)
            db.flush()

            for config in configs_to_load:
                db.add(config)

            db.commit()
            logger.info("Global configurations loaded successfully.")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error loading global configurations: {e}")
            sys.exit(1)


if __name__ == "__main__":
    seed_explore_configurations()
    seed_global_configurations()