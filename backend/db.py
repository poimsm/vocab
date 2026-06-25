import os
from sqlmodel import create_engine, Session

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, echo=False)

def get_db():
    with Session(engine) as session:
        yield session