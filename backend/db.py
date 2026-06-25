import os
from sqlmodel import create_engine, Session

DATABASE_URL = os.getenv("DATABASE_URL")

# Asegúrate de usar el create_engine de SQLModel
engine = create_engine(DATABASE_URL, echo=False)

def get_db():
    # 🔥 CORRECCIÓN: Generamos la sesión nativa usando el bloque with de SQLModel
    with Session(engine) as session:
        yield session