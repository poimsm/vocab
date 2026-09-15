"""
User Configuration Manager
"""
from sqlmodel import Session, select
from models import UserConfiguration
from logging_client import logger
from config.global_config import GlobalConfigManager


class UserConfigManager:
    """User configuration manager with fallback to global configuration""" 

    @classmethod
    def get_or_create_user_config(cls, session: Session, user_id: int) -> UserConfiguration:
        """
        Gets or creates user configuration.

        If the user has no configuration, creates a new one with all values set to None
        (which means use global configurations as fallback).

        Args:
            session: Database session
            user_id: User ID

        Returns:
            User configuration
        """
        try:
            statement = select(UserConfiguration).where(UserConfiguration.user_id == user_id)
            config = session.exec(statement).first()

            if config:
                return config

            # Create new configuration with None values (fallback to global)
            config = UserConfiguration(user_id=user_id)
            session.add(config)
            session.commit()
            session.refresh(config)

            logger.info(f"[UserConfigManager] New configuration created for user {user_id}")
            return config

        except Exception as e:
            logger.error(f"[UserConfigManager] Error creating config for user {user_id}: {e}")
            session.rollback()
            raise

    @classmethod
    def get_limit(
        cls,
        session: Session,
        user_id: int,
        field_name: str,
        global_key: str
    ) -> int:
        """
        Gets the limit for a user.

        First searches in user configuration, if None uses global configuration.

        Args:
            session: Database session
            user_id: User ID
            field_name: Field name in UserConfiguration (e.g. 'max_words')
            global_key: Key in GlobalConfiguration (e.g. 'MAX_WORDS_PER_USER')

        Returns:
            Limit to use (int)
        """
        try:
            # Get user configuration
            statement = select(UserConfiguration).where(UserConfiguration.user_id == user_id)
            user_config = session.exec(statement).first()

            # If has specific configuration and field is not None, use it
            if user_config and getattr(user_config, field_name, None) is not None:
                value = getattr(user_config, field_name)
                logger.debug(
                    f"[UserConfigManager] User {user_id}: using specific limit {field_name}={value}"
                )
                return value

            # Fallback to global configuration
            global_value = GlobalConfigManager.get_int(session, global_key)
            logger.debug(
                f"[UserConfigManager] User {user_id}: using global limit {global_key}={global_value}"
            )
            return global_value

        except Exception as e:
            logger.error(
                f"[UserConfigManager] Error getting limit for user {user_id}: {e}"
            )
            # Fallback a global si hay error
            return GlobalConfigManager.get_int(session, global_key)

    @classmethod
    def get_max_words(cls, session: Session, user_id: int) -> int:
        """Gets the words limit for a user"""
        return cls.get_limit(session, user_id, "max_words", "MAX_WORDS_PER_USER")

    @classmethod
    def get_max_examples(cls, session: Session, user_id: int) -> int:
        """Gets the examples limit for a user"""
        return cls.get_limit(session, user_id, "max_examples", "MAX_EXAMPLES_PER_USER")

    @classmethod
    def get_max_best_options(cls, session: Session, user_id: int) -> int:
        """Gets the best options limit for a user"""
        return cls.get_limit(session, user_id, "max_best_options", "MAX_BEST_OPTIONS_PER_USER")

    @classmethod
    def get_max_collocations(cls, session: Session, user_id: int) -> int:
        """Gets the collocations limit for a user"""
        return cls.get_limit(session, user_id, "max_collocations", "MAX_COLLOCATIONS_PER_USER")

    @classmethod
    def get_max_quick_writes(cls, session: Session, user_id: int) -> int:
        """Gets the quick writes limit for a user"""
        return cls.get_limit(session, user_id, "max_quick_writes", "MAX_QUICK_WRITES_PER_USER")