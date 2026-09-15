"""
Script para crear perfiles faltantes de usuarios

Busca todos los usuarios que no tienen perfil creado
y crea sus perfiles con estadísticas correctas desde la BD.

Uso:
    python manage.py seed-missing-user-profiles
"""
from sqlmodel import Session, select
from models import User, UserProfile
from config.user_profile import UserProfileManager
from logging_client import logger


def seed_missing_user_profiles(session: Session) -> None:
    """
    Busca usuarios sin perfil y crea sus perfiles automáticamente.

    Para cada usuario sin perfil:
    1. Crea el UserProfile
    2. Reconstruye las estadísticas desde la BD
    """
    try:
        # Obtener todos los usuarios
        all_users = session.exec(select(User)).all()

        if not all_users:
            logger.info("[seed_missing_user_profiles] No hay usuarios en la base de datos")
            return

        # Obtener usuarios que YA tienen perfil
        existing_profiles = session.exec(select(UserProfile)).all()
        existing_user_ids = {profile.user_id for profile in existing_profiles}

        # Encontrar usuarios sin perfil
        missing_users = [u for u in all_users if u.id not in existing_user_ids]

        if not missing_users:
            logger.info("[seed_missing_user_profiles] Todos los usuarios ya tienen perfil")
            return

        logger.info(f"[seed_missing_user_profiles] Encontrados {len(missing_users)} usuario(s) sin perfil")
        created_count = 0

        for user in missing_users:
            try:
                # Crear perfil
                profile = UserProfileManager.get_or_create_profile(session, user.id)
                logger.debug(f"[seed_missing_user_profiles] Perfil creado para usuario {user.id}")

                # Reconstruir estadísticas desde BD
                profile = UserProfileManager.rebuild_from_db(session, user.id)
                logger.info(
                    f"[seed_missing_user_profiles] Perfil inicializado para usuario {user.id}: "
                    f"words={profile.total_words}, examples={profile.total_examples}, "
                    f"best_options={profile.total_best_options}, "
                    f"collocations={profile.total_collocations}, "
                    f"quick_writes={profile.total_quick_writes}"
                )
                created_count += 1

            except Exception as e:
                logger.error(
                    f"[seed_missing_user_profiles] Error creando perfil para usuario {user.id}: {e}"
                )
                continue

        logger.info(f"[seed_missing_user_profiles] {created_count} perfil(es) creado(s) exitosamente")

    except Exception as e:
        logger.error(f"[seed_missing_user_profiles] Error al crear perfiles faltantes: {e}")
        session.rollback()
        raise


if __name__ == "__main__":
    from db import engine

    with Session(engine) as session:
        seed_missing_user_profiles(session)
