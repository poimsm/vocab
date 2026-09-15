"""
Quota and configuration limits validator

Provides functions to validate if a user/system has reached their limits
according to configuration (first user-specific, then global).

Uses UserProfileManager to obtain current counters efficiently.
"""
from sqlmodel import Session, func, select
from models import User
from config.global_config import GlobalConfigManager
from config.user_config import UserConfigManager
from config.user_profile import UserProfileManager
from config.exceptions import (
    MaxUsersExceededException,
    MaxWordsPerUserExceededException,
    MaxExamplesPerUserExceededException,
    MaxBestOptionsPerUserExceededException,
    MaxCollocationsPerUserExceededException,
    MaxQuickWritesPerUserExceededException,
)
from logging_client import logger


class QuotaValidator:
    """Quota and limits validator"""

    @staticmethod
    def validate_max_users(session: Session) -> None:
        """
        Valida que no se haya alcanzado el máximo de usuarios permitidos.

        Lanza MaxUsersExceededException si se excede el límite.
        """
        max_users = GlobalConfigManager.get_int(session, "MAX_USERS", 1000)

        statement = select(func.count(User.id))
        current_users = session.exec(statement).one()

        if current_users >= max_users:
            logger.warning(
                f"[QuotaValidator] User limit reached: {current_users}/{max_users}"
            )
            raise MaxUsersExceededException(current_users, max_users)

    @staticmethod
    def validate_max_words_per_user(session: Session, user_id: int) -> None:
        """
        Valida que el usuario no haya excedido su límite de palabras.

        Usa el límite específico del usuario si existe, sino el global.
        Obtiene conteo desde UserProfile (más rápido que COUNT(*)).
        Lanza MaxWordsPerUserExceededException si se excede el límite.
        """
        max_words = UserConfigManager.get_max_words(session, user_id)
        current_words = UserProfileManager.get_total_words(session, user_id)

        if current_words >= max_words:
            logger.warning(
                f"[QuotaValidator] Words limit for user {user_id} reached: {current_words}/{max_words}"
            )
            raise MaxWordsPerUserExceededException(current_words, max_words)

    @staticmethod
    def validate_max_examples_per_user(session: Session, user_id: int) -> None:
        """
        Valida que el usuario no haya excedido su límite de ejemplos.

        Los ejemplos son contados por palabra del usuario.
        Usa el límite específico del usuario si existe, sino el global.
        Obtiene conteo desde UserProfile (más rápido que COUNT(*)).
        Lanza MaxExamplesPerUserExceededException si se excede el límite.
        """
        max_examples = UserConfigManager.get_max_examples(session, user_id)
        current_examples = UserProfileManager.get_total_examples(session, user_id)

        if current_examples >= max_examples:
            logger.warning(
                f"[QuotaValidator] Examples limit for user {user_id} reached: {current_examples}/{max_examples}"
            )
            raise MaxExamplesPerUserExceededException(current_examples, max_examples)

    @staticmethod
    def validate_max_best_options_per_user(session: Session, user_id: int) -> None:
        """
        Valida que el usuario no haya excedido su límite de best_options.

        Los best_options son contados por palabra del usuario.
        Usa el límite específico del usuario si existe, sino el global.
        Obtiene conteo desde UserProfile (más rápido que COUNT(*)).
        Lanza MaxBestOptionsPerUserExceededException si se excede el límite.
        """
        max_best_options = UserConfigManager.get_max_best_options(session, user_id)
        current_best_options = UserProfileManager.get_total_best_options(session, user_id)

        if current_best_options >= max_best_options:
            logger.warning(
                f"[QuotaValidator] Best options limit for user {user_id} reached: {current_best_options}/{max_best_options}"
            )
            raise MaxBestOptionsPerUserExceededException(current_best_options, max_best_options)

    @staticmethod
    def validate_max_collocations_per_user(session: Session, user_id: int) -> None:
        """
        Valida que el usuario no haya excedido su límite de colocaciones.

        Usa el límite específico del usuario si existe, sino el global.
        Obtiene conteo desde UserProfile (más rápido que COUNT(*)).
        Lanza MaxCollocationsPerUserExceededException si se excede el límite.
        """
        max_collocations = UserConfigManager.get_max_collocations(session, user_id)
        current_collocations = UserProfileManager.get_total_collocations(session, user_id)

        if current_collocations >= max_collocations:
            logger.warning(
                f"[QuotaValidator] Collocations limit for user {user_id} reached: {current_collocations}/{max_collocations}"
            )
            raise MaxCollocationsPerUserExceededException(current_collocations, max_collocations)

    @staticmethod
    def validate_max_quick_writes_per_user(session: Session, user_id: int) -> None:
        """
        Valida que el usuario no haya excedido su límite de quick_writes.

        Usa el límite específico del usuario si existe, sino el global.
        Obtiene conteo desde UserProfile (más rápido que COUNT(*)).
        Lanza MaxQuickWritesPerUserExceededException si se excede el límite.
        """
        max_quick_writes = UserConfigManager.get_max_quick_writes(session, user_id)
        current_quick_writes = UserProfileManager.get_total_quick_writes(session, user_id)

        if current_quick_writes >= max_quick_writes:
            logger.warning(
                f"[QuotaValidator] Quick writes limit for user {user_id} reached: {current_quick_writes}/{max_quick_writes}"
            )
            raise MaxQuickWritesPerUserExceededException(current_quick_writes, max_quick_writes)
