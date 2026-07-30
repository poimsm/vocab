import os
from sqlmodel import create_engine, Session
from logging_config import logger

DATABASE_URL = os.getenv("DATABASE_URL")

logger.info("Initializing database connection")
engine = create_engine(DATABASE_URL, echo=False)
logger.info("Database engine created successfully")

def get_db():
    logger.debug("Getting database session")
    with Session(engine) as session:
        yield session