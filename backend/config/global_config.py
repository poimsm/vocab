"""
Global Configuration Manager

Manages reading and writing global configurations in the database.
Includes in-memory cache to avoid frequent queries.
"""
from typing import Optional, Dict
from datetime import datetime, timezone
from sqlmodel import Session, select
from models import GlobalConfiguration
from logging_client import logger


class GlobalConfigManager:
    """Global configuration manager with in-memory cache"""

    # Default configurations
    DEFAULT_CONFIGS = {
        "MAX_USERS": "1000",
        "MAX_WORDS_PER_USER": "500",
        "MAX_EXAMPLES_PER_USER": "5000",
        "MAX_BEST_OPTIONS_PER_USER": "1000",
    }

    # In-memory cache (loaded once per process)
    _cache: Dict[str, str] = {}
    _cache_loaded = False

    @classmethod
    def load_cache(cls, session: Session) -> None:
        """Loads all configurations from DB to cache"""
        if cls._cache_loaded:
            return

        try:
            statement = select(GlobalConfiguration)
            configs = session.exec(statement).all()
            cls._cache = {config.key: config.value for config in configs}
            cls._cache_loaded = True
            logger.info(f"[GlobalConfigManager] Cache loaded with {len(cls._cache)} configurations")
        except Exception as e:
            logger.error(f"[GlobalConfigManager] Error loading cache: {e}")
            cls._cache_loaded = True

    @classmethod
    def get(cls, session: Session, key: str, default: Optional[str] = None) -> str:
        """
        Gets a configuration by key.

        First tries from cache, if not found loads from DB.

        Args:
            session: Database session
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value
        """
        # Ensure cache is loaded
        if not cls._cache_loaded:
            cls.load_cache(session)

        # Try from cache
        if key in cls._cache:
            return cls._cache[key]

        # Try from DB (in case it was added after loading cache)
        try:
            statement = select(GlobalConfiguration).where(GlobalConfiguration.key == key)
            config = session.exec(statement).first()
            if config:
                cls._cache[key] = config.value
                return config.value
        except Exception as e:
            logger.error(f"[GlobalConfigManager] Error getting {key}: {e}")

        # Return default or default value
        if default is not None:
            return default
        return cls.DEFAULT_CONFIGS.get(key, "")

    @classmethod
    def get_int(cls, session: Session, key: str, default: int = 0) -> int:
        """Gets a configuration as integer"""
        value = cls.get(session, key)
        try:
            return int(value) if value else default
        except ValueError:
            logger.warning(f"[GlobalConfigManager] Non-numeric value for {key}: {value}")
            return default

    @classmethod
    def set(cls, session: Session, key: str, value: str, description: str = None) -> GlobalConfiguration:
        """
        Sets a configuration in the DB.

        Args:
            session: Database session
            key: Configuration key
            value: Value to set
            description: Optional description

        Returns:
            Updated or created configuration
        """
        try:
            statement = select(GlobalConfiguration).where(GlobalConfiguration.key == key)
            config = session.exec(statement).first()

            if config:
                config.value = value
                if description:
                    config.description = description
                config.updated_at = datetime.now(timezone.utc)
            else:
                config = GlobalConfiguration(
                    key=key,
                    value=value,
                    description=description or f"Configuration: {key}"
                )
                session.add(config)

            session.commit()
            session.refresh(config)

            # Update cache
            cls._cache[key] = value

            logger.info(f"[GlobalConfigManager] Configuration updated: {key}={value}")
            return config

        except Exception as e:
            logger.error(f"[GlobalConfigManager] Error saving {key}: {e}")
            session.rollback()
            raise

    @classmethod
    def get_all(cls, session: Session) -> Dict[str, str]:
        """Gets all configurations as dictionary"""
        if not cls._cache_loaded:
            cls.load_cache(session)
        return cls._cache.copy()

    @classmethod
    def clear_cache(cls) -> None:
        """Clears in-memory cache (useful for tests)"""
        cls._cache = {}
        cls._cache_loaded = False
        logger.info("[GlobalConfigManager] Cache cleared")
