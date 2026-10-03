# src/core/boost/exceptions.py


class BoostException(Exception):
    """Base exception for boost domain."""
    pass


class BoostSlotLimitReachedException(BoostException):
    """Raised when user reaches max concurrent boosted words."""
    pass


class BoostCooldownActiveException(BoostException):
    """Raised when toggle cooldown is still active."""
    pass


class WordNotEligibleForBoostException(BoostException):
    """Raised when word cannot be boosted (archived, blacklisted, etc)."""
    pass


class BoostNotFound(BoostException):
    """Raised when boost record is not found."""
    pass
