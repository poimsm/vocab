#!/usr/bin/env python
"""
Gestor de tareas administrativas del backend

Comandos disponibles:
  - load-global-config              Cargar configuración global
  - show-config                     Ver todas las configuraciones
  - set-config                      Actualizar configuración específica
  - reload-cache                    Recargar caché de configuraciones
  - load-user-configuration         Cargar configuración de usuario específico
  - seed-missing-user-profiles      Crear perfiles para usuarios sin perfil
  - clone-user                      Clonar un usuario (todos sus datos)
  - help                            Mostrar ayuda

Ejemplos:
  python manage.py load-global-config
  python manage.py show-config
  python manage.py set-config MAX_USERS 5000
  python manage.py load-user-configuration 5        # Cargar configuración de usuario (ID=5)
  python manage.py seed-missing-user-profiles       # Crear perfiles faltantes
  python manage.py clone-user 5 10                  # Clonar usuario 5 a usuario 10
"""
import sys
import traceback
from config.cli import (
    load_global_config,
    show_config,
    set_config,
    reload_cache,
    print_help
)


def load_user_configuration(user_id: int):
    """Carga la configuración de un usuario específico desde la BD.

    Args:
        user_id: ID de usuario (requerido)
    """
    from seeds.seed_user_configuration import seed_user_configuration
    from db import engine
    from sqlmodel import Session
    from logging_client import logger

    with Session(engine) as session:
        try:
            seed_user_configuration(session, user_id=user_id)
            print(f"✅ Configuración de usuario {user_id} cargada exitosamente")
            return True
        except Exception as e:
            print(f"❌ Error cargando configuración de usuario: {e}")
            logger.error(f"Error en load_user_configuration: {e}")
            return False


def seed_missing_profiles():
    """Crea perfiles para usuarios que aún no tienen perfil."""
    from seeds.seed_missing_user_profiles import seed_missing_user_profiles
    from db import engine
    from sqlmodel import Session
    from logging_client import logger

    with Session(engine) as session:
        try:
            seed_missing_user_profiles(session)
            print("✅ Perfiles faltantes creados exitosamente")
            return True
        except Exception as e:
            print(f"❌ Error creando perfiles faltantes: {e}")
            logger.error(f"Error en seed_missing_profiles: {e}")
            return False


def clone_user(source_user_id: int, target_user_id: int, clean: bool = False):
    """Clona un usuario con todos sus datos.

    Args:
        source_user_id: ID del usuario a clonar
        target_user_id: ID del usuario destino
        clean: Si es True, limpia todos los datos del usuario destino primero
    """
    from seeds.seed_clone_user import seed_clone_user
    from db import engine
    from sqlmodel import Session
    from logging_client import logger

    with Session(engine) as session:
        try:
            seed_clone_user(session, source_user_id, target_user_id, clean=clean)
            print(f"✅ Usuario {source_user_id} clonado exitosamente a {target_user_id}")
            return True
        except Exception as e:
            print(f"❌ Error clonando usuario: {e}")
            logger.error(f"Error en clone_user: {e} - {traceback.format_exc()}")
            return False


def main():
    """Punto de entrada principal."""
    if len(sys.argv) < 2:
        print(__doc__)
        print_help()
        return

    command = sys.argv[1].lower()

    if command == "load-global-config":
        load_global_config()

    elif command == "show-config":
        show_config()

    elif command == "set-config":
        if len(sys.argv) < 4:
            print("❌ Uso: python manage.py set-config <KEY> <VALUE>")
            print("Ejemplo: python manage.py set-config MAX_USERS 5000")
            return
        key = sys.argv[2]
        value = sys.argv[3]
        set_config(key, value)

    elif command == "reload-cache":
        reload_cache()

    elif command == "load-user-configuration":
        if len(sys.argv) < 3:
            print("❌ Uso: python manage.py load-user-configuration <USER_ID>")
            print("Ejemplo: python manage.py load-user-configuration 5")
            return
        try:
            user_id = int(sys.argv[2])
        except ValueError:
            print(f"❌ Error: '{sys.argv[2]}' no es un número válido")
            return
        load_user_configuration(user_id=user_id)

    elif command == "seed-missing-user-profiles":
        seed_missing_profiles()

    elif command == "clone-user":
        if len(sys.argv) < 4:
            print("❌ Uso: python manage.py clone-user <SOURCE_USER_ID> <TARGET_USER_ID>")
            print("Ejemplo: python manage.py clone-user 5 10")
            return
        try:
            source_user_id = int(sys.argv[2])
            target_user_id = int(sys.argv[3])
        except ValueError:
            print("❌ Error: Los IDs deben ser números válidos")
            return
        clone_user(source_user_id, target_user_id, clean=True)

    elif command in ["-h", "--help", "help"]:
        print(__doc__)
        print_help()

    else:
        print(f"❌ Comando desconocido: {command}\n")
        print(__doc__)
        print_help()


if __name__ == "__main__":
    main()
