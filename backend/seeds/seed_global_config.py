"""
Script de carga de configuraciones globales

Carga las configuraciones iniciales en la tabla global_configurations.
Se debe ejecutar una sola vez después de crear las migraciones.

Uso:
    python manage.py load-global-config
"""
from sqlmodel import Session, select
from models import GlobalConfiguration
from datetime import datetime, timezone
from logging_client import logger


def seed_global_config(session: Session) -> None:
    """
    Carga las configuraciones globales iniciales.

    Si las configuraciones ya existen, no las sobrescribe.
    """

    configs = [
        {
            "key": "MAX_USERS",
            "value": "1000",
            "description": "Cantidad máxima de usuarios que se pueden crear en la plataforma"
        },
        {
            "key": "MAX_WORDS_PER_USER",
            "value": "500",
            "description": "Cantidad máxima de palabras que cada usuario puede agregar"
        },
        {
            "key": "MAX_EXAMPLES_PER_USER",
            "value": "5000",
            "description": "Cantidad máxima de ejemplos que cada usuario puede crear"
        },
        {
            "key": "MAX_BEST_OPTIONS_PER_USER",
            "value": "1000",
            "description": "Cantidad máxima de best_options (múltiple opción) que cada usuario puede crear"
        },
        {
            "key": "MAX_COLLOCATIONS_PER_USER",
            "value": "1000",
            "description": "Cantidad máxima de colocaciones que cada usuario puede crear"
        },
        {
            "key": "MAX_QUICK_WRITES_PER_USER",
            "value": "5000",
            "description": "Cantidad máxima de quick writes que cada usuario puede crear"
        },
    ]

    try:
        for config_data in configs:
            # Verificar si la configuración ya existe
            statement = select(GlobalConfiguration).where(
                GlobalConfiguration.key == config_data["key"]
            )
            existing = session.exec(statement).first()

            if existing:
                logger.info(f"[seed_global_config] Configuración {config_data['key']} ya existe, omitiendo...")
                continue

            # Crear nueva configuración
            config = GlobalConfiguration(
                key=config_data["key"],
                value=config_data["value"],
                description=config_data["description"],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            session.add(config)
            logger.info(f"[seed_global_config] Configuración agregada: {config_data['key']} = {config_data['value']}")

        session.commit()
        logger.info("[seed_global_config] Configuraciones globales cargadas exitosamente")

    except Exception as e:
        logger.error(f"[seed_global_config] Error al cargar configuraciones: {e}")
        session.rollback()
        raise


if __name__ == "__main__":
    from db import engine

    with Session(engine) as session:
        seed_global_config(session)
