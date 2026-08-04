"""
ConfigManager: Centraliza acceso a configuraciones desde la base de datos.

Proporciona métodos para obtener valores de configuración de forma tipada.
"""

from typing import Any, Optional
from sqlmodel import Session, select
from logging_client import logger

from models import GlobalConfiguration


class ConfigManager:
    """Gestor centralizado de configuraciones globales desde la BD."""

    def __init__(self, db: Session):
        self.db = db

    # ==========================================
    # MÉTODOS GENÉRICOS
    # ==========================================

    def get_value(self, key: str, default_value: Any = None) -> Any:
        """
        Obtiene un valor de configuración como string.

        Args:
            key: Clave de configuración
            default_value: Valor por defecto si no existe

        Returns:
            Valor de configuración o default_value
        """
        try:
            config = self.db.exec(
                select(GlobalConfiguration).where(GlobalConfiguration.key == key)
            ).first()
            if config:
                logger.debug(f"[ConfigManager.get_value] Retrieved config {key}: {config.value}")
                return config.value
            logger.debug(f"[ConfigManager.get_value] Config {key} not found, using default: {default_value}")
            return default_value
        except Exception as e:
            logger.warning(f"[ConfigManager.get_value] Error retrieving config {key}: {str(e)}, using default: {default_value}")
            return default_value

    def get_int(self, key: str, default_value: int) -> int:
        """
        Obtiene un valor de configuración como entero.

        Args:
            key: Clave de configuración
            default_value: Valor por defecto si no existe o no es válido

        Returns:
            Valor de configuración como int o default_value
        """
        value = self.get_value(key, str(default_value))
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"[ConfigManager.get_int] Could not convert config {key} to int: {value}, using default: {default_value}")
            return default_value

    def get_float(self, key: str, default_value: float) -> float:
        """
        Obtiene un valor de configuración como float.

        Args:
            key: Clave de configuración
            default_value: Valor por defecto si no existe o no es válido

        Returns:
            Valor de configuración como float o default_value
        """
        value = self.get_value(key, str(default_value))
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"[ConfigManager.get_float] Could not convert config {key} to float: {value}, using default: {default_value}")
            return default_value

    def get_bool(self, key: str, default_value: bool) -> bool:
        """
        Obtiene un valor de configuración como booleano.

        Args:
            key: Clave de configuración
            default_value: Valor por defecto si no existe

        Returns:
            Valor de configuración como bool o default_value
        """
        value = self.get_value(key, str(default_value).lower())
        if isinstance(value, bool):
            return value
        return value.lower() in ('true', '1', 'yes', 'on')

    # ==========================================
    # CONFIGURACIONES ESPECÍFICAS DEL DOMINIO
    # ==========================================

    def get_target_cycle_seen(self) -> int:
        """
        Obtiene TARGET_CYCLE_SEEN: cuántas veces debe verse una palabra para marcarla como aprendida.

        Default: 1
        """
        return self.get_int("TARGET_CYCLE_SEEN", 1)

    def get_threshold_for_transition(self) -> int:
        """
        Obtiene THRESHOLD_FOR_TRANSITION: mínimo de palabras no aprendidas para no hacer transición de batch.

        Default: 4
        """
        return self.get_int("THRESHOLD_FOR_TRANSITION", 4)

    def get_chunk_size(self) -> int:
        """
        Obtiene CHUNK_SIZE: tamaño de chunks para importación masiva de palabras.

        Default: 15
        """
        return self.get_int("CHUNK_SIZE", 15)

    def get_batch_default_capacity(self) -> int:
        """
        Obtiene BATCH_DEFAULT_CAPACITY: máximo de palabras por batch.

        Default: 15
        """
        return self.get_int("BATCH_DEFAULT_CAPACITY", 15)

    def get_default_priority_words_limit(self) -> int:
        """
        Obtiene DEFAULT_PRIORITY_WORDS_LIMIT: límite de palabras prioritarias.

        Default: 10
        """
        return self.get_int("DEFAULT_PRIORITY_WORDS_LIMIT", 10)

    def get_refill_queue_emergency_limit(self) -> int:
        """
        Obtiene REFILL_QUEUE_EMERGENCY_LIMIT: límite de emergencia para rellenar colas.

        Default: 8
        """
        return self.get_int("REFILL_QUEUE_EMERGENCY_LIMIT", 8)
