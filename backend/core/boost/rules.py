# src/core/boost/rules.py
from datetime import datetime, timezone
from typing import Optional

from core.boost.exceptions import (
    BoostSlotLimitReachedException,
    BoostCooldownActiveException,
    WordNotEligibleForBoostException,
)

# Constantes del dominio (pueden venir de un archivo de config global si prefieres)
DEFAULT_MAX_BOOST_SLOTS = 5
BOOST_TOGGLE_COOLDOWN_SECONDS = 5


def validate_max_boost_slots(
    current_active_count: int, 
    max_allowed: int = DEFAULT_MAX_BOOST_SLOTS
) -> None:
    """
    Valida que el usuario no supere el límite permitido de palabras boosteadas en paralelo.
    
    :param current_active_count: Cantidad actual de palabras con boost activo del usuario.
    :param max_allowed: Límite máximo (ej: 4, 5 o 6 según el plan del usuario).
    """
    if current_active_count >= max_allowed:
        raise BoostSlotLimitReachedException(
            f"Has alcanzado el límite máximo de {max_allowed} palabras en modo Boost al mismo tiempo."
        )


def validate_toggle_cooldown(
    last_updated_at: Optional[datetime], 
    cooldown_seconds: int = BOOST_TOGGLE_COOLDOWN_SECONDS
) -> None:
    """
    Evita el 'frenesí de clics' en la UI. Valida que haya transcurrido suficiente 
    tiempo desde la última vez que el usuario cambió el estado de esta palabra.
    """
    if last_updated_at is None:
        return

    now = datetime.now(timezone.utc)
    
    # Asegurar que last_updated_at sea tz-aware para la resta
    if last_updated_at.tzinfo is None:
        last_updated_at = last_updated_at.replace(tzinfo=timezone.utc)

    elapsed_seconds = (now - last_updated_at).total_seconds()

    if elapsed_seconds < cooldown_seconds:
        remaining = int(cooldown_seconds - elapsed_seconds)
        raise BoostCooldownActiveException(
            f"Por favor espera {remaining} segundo(s) antes de volver a cambiar el estado de esta palabra."
        )


def validate_word_eligibility_for_boost(is_archived: bool, is_blacklisted: bool = False) -> None:
    """
    Valida si la palabra reúne las condiciones de negocio para ser boosteada.
    """
    if is_archived:
        raise WordNotEligibleForBoostException("No puedes aplicar Boost a una palabra archivada.")
    
    if is_blacklisted:
        raise WordNotEligibleForBoostException("Esta palabra no está disponible para práctica intensiva.")