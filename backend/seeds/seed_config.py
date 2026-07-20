import sys
from sqlmodel import Session, select
from db import engine
from models import ExploreConfiguration

def seed_explore_configurations():
    print("Cargando configuracion explore...")
    
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
            for config in existing_configs:
                db.delete(config)
            db.flush()

            for config in configs_to_load:
                db.add(config)
                
            db.commit()
            print("✅ Configuracion cargada con exito.")
        except Exception as e:
            db.rollback()
            print(f"❌ Error inesperado: {e}")
            sys.exit(1)

if __name__ == "__main__":
    seed_explore_configurations()