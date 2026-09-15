"""
Custom exceptions for configuration limits validation
"""
from fastapi import HTTPException, status


class QuotaExceededException(HTTPException):
    """Quota limit exceeded"""

    def __init__(self, resource: str, current: int, limit: int):
        self.resource = resource
        self.current = current
        self.limit = limit
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "quota_exceeded",
                "message": f"Quota limit exceeded for {resource}",
                "resource": resource,
                "current": current,
                "limit": limit
            }
        )


class MaxUsersExceededException(QuotaExceededException):
    """Maximum number of users exceeded"""

    def __init__(self, current: int, limit: int):
        super().__init__("users", current, limit)


class MaxWordsPerUserExceededException(QuotaExceededException):
    """Maximum words per user exceeded"""

    def __init__(self, current: int, limit: int):
        super().__init__("words per user", current, limit)


class MaxExamplesPerUserExceededException(QuotaExceededException):
    """Maximum examples per user exceeded"""

    def __init__(self, current: int, limit: int):
        super().__init__("examples per user", current, limit)


class MaxBestOptionsPerUserExceededException(QuotaExceededException):
    """Maximum best options per user exceeded"""

    def __init__(self, current: int, limit: int):
        super().__init__("best options per user", current, limit)


class MaxCollocationsPerUserExceededException(QuotaExceededException):
    """Maximum collocations per user exceeded"""

    def __init__(self, current: int, limit: int):
        super().__init__("collocations per user", current, limit)


class MaxQuickWritesPerUserExceededException(QuotaExceededException):
    """Maximum quick writes per user exceeded"""

    def __init__(self, current: int, limit: int):
        super().__init__("quick writes per user", current, limit)
