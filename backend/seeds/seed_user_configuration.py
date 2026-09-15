"""
Script de carga de configuración de usuario

Crea la configuración (UserConfiguration) de un usuario específico.
La configuración permite establecer límites específicos por usuario.
Si no se especifican, el usuario usa los límites globales.

Uso:
    python manage.py load-user-configuration 5
"""
from sqlmodel import Session, select
from models import User
from config.user_config import UserConfigManager
from logging_client import logger

# Configuración por defecto para usuario (None = usar límites globales)
# Si deseas establecer límites específicos, modifica estos valores
config = {
    "max_words": 50,
    "max_examples": 500,
    "max_best_options": 150,
    "max_collocations": 150,
    "max_quick_writes": 60,
}


def seed_user_configuration(session: Session, user_id: int) -> None:
    """
    Crea o actualiza la configuración de un usuario específico con los valores de config.

    Args:
        session: SQLModel session
        user_id: ID del usuario a procesar (requerido)
    """
    try:
        # Verificar que el usuario existe
        user = session.exec(select(User).where(User.id == user_id)).first()
        if not user:
            logger.warning(f"[seed_user_configuration] Usuario {user_id} no encontrado")
            return

        logger.info(f"[seed_user_configuration] Cargando configuración para usuario {user_id}...")

        # Crear o obtener configuración
        user_config = UserConfigManager.get_or_create_user_config(session, user_id)
        logger.debug(f"[seed_user_configuration] Configuración creada/obtenida para usuario {user_id}")

        # Establecer los valores del config
        user_config.max_words = config["max_words"]
        user_config.max_examples = config["max_examples"]
        user_config.max_best_options = config["max_best_options"]
        user_config.max_collocations = config["max_collocations"]
        user_config.max_quick_writes = config["max_quick_writes"]

        session.add(user_config)
        session.commit()
        session.refresh(user_config)

        logger.info(
            f"[seed_user_configuration] Configuración de usuario {user_id} establecida: "
            f"words={user_config.max_words}, "
            f"examples={user_config.max_examples}, "
            f"best_options={user_config.max_best_options}, "
            f"collocations={user_config.max_collocations}, "
            f"quick_writes={user_config.max_quick_writes}"
        )

        logger.info(f"[seed_user_configuration] Configuración de usuario {user_id} cargada exitosamente")

    except Exception as e:
        logger.error(f"[seed_user_configuration] Error al cargar configuración de usuario {user_id}: {e}")
        session.rollback()
        raise


if __name__ == "__main__":
    import sys
    from db import engine

    # Validar que se proporcione user_id
    if len(sys.argv) < 2:
        print("❌ Error: Se requiere USER_ID como argumento")
        print("Uso: python seeds/seed_user_configuration.py <USER_ID>")
        print("Ejemplo: python seeds/seed_user_configuration.py 5")
        sys.exit(1)

    try:
        user_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Error: '{sys.argv[1]}' no es un número válido")
        sys.exit(1)

    with Session(engine) as session:
        seed_user_configuration(session, user_id=user_id)
