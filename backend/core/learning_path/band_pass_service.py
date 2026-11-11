"""
Service for managing band-pass filtering configuration and state.

Handles:
- Creating and updating band-pass configs
- Initializing default configs for new users
- Applying band-pass penalties to word priorities
"""

from sqlmodel import Session, select
from logging_client import logger
from core.enums import ContentType
from core.learning_path.models import BandPassConfig, RecentWordHistory


class BandPassService:
    """Service for managing band-pass filtering in learning paths."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_config(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> BandPassConfig:
        """
        Get existing band-pass config or create default one.

        Args:
            user_id: User ID
            content_type: Content type (EXAMPLE, BEST_OPTIONS, etc.)

        Returns:
            BandPassConfig with default or existing settings
        """
        config = self.db.exec(
            select(BandPassConfig).where(
                (BandPassConfig.user_id == user_id) &
                (BandPassConfig.type == content_type)
            )
        ).first()

        if not config:
            # Create default config
            config = BandPassConfig(
                user_id=user_id,
                type=content_type,
                window_size=3,  # Track last 3 words
                inflation_factor=0.2,  # 20% priority penalty
            )
            self.db.add(config)
            self.db.commit()
            logger.info(
                f"[BandPassService.get_or_create_config] Created default config for "
                f"user {user_id}, type={content_type}"
            )

        return config

    def update_config(
        self,
        user_id: int,
        content_type: ContentType,
        window_size: int = None,
        inflation_factor: float = None,
    ) -> BandPassConfig:
        """
        Update band-pass configuration for a user.

        Args:
            user_id: User ID
            content_type: Content type
            window_size: New window size (1-10)
            inflation_factor: New inflation factor (0.0-1.0)

        Returns:
            Updated BandPassConfig
        """
        config = self.get_or_create_config(user_id, content_type)

        if window_size is not None:
            if not (1 <= window_size <= 10):
                raise ValueError("window_size must be between 1 and 10")
            config.window_size = window_size

        if inflation_factor is not None:
            if not (0.0 <= inflation_factor <= 1.0):
                raise ValueError("inflation_factor must be between 0.0 and 1.0")
            config.inflation_factor = inflation_factor

        self.db.add(config)
        self.db.commit()

        logger.info(
            f"[BandPassService.update_config] Updated config for user {user_id}, "
            f"type={content_type}, window_size={config.window_size}, "
            f"inflation_factor={config.inflation_factor}"
        )

        return config

    def reset_history(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> None:
        """
        Clear all recent word history for a user/content_type.
        Useful for starting fresh or testing.

        Args:
            user_id: User ID
            content_type: Content type
        """
        histories = self.db.exec(
            select(RecentWordHistory).where(
                (RecentWordHistory.user_id == user_id) &
                (RecentWordHistory.type == content_type)
            )
        ).all()

        if histories:
            for history in histories:
                self.db.delete(history)
            self.db.commit()
            logger.info(
                f"[BandPassService.reset_history] Cleared {len(histories)} history records for "
                f"user {user_id}, type={content_type}"
            )

    def get_recent_words(
        self,
        user_id: int,
        content_type: ContentType,
        limit: int = None,
    ) -> list[int]:
        """
        Get the recent word IDs in descending order (most recent first).

        Args:
            user_id: User ID
            content_type: Content type
            limit: Maximum number of words to return (default: uses config window_size)

        Returns:
            List of word IDs, most recent first
        """
        if limit is None:
            config = self.get_or_create_config(user_id, content_type)
            limit = config.window_size

        records = self.db.exec(
            select(RecentWordHistory).where(
                (RecentWordHistory.user_id == user_id) &
                (RecentWordHistory.type == content_type)
            )
            .order_by(RecentWordHistory.created_at.desc())
            .limit(limit)
        ).all()

        return [record.word_id for record in records]
