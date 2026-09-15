"""
User Profile Manager

Manages user profile including resource accounting.
Keeps counters updated for words, examples, best_options, etc.
"""
from datetime import datetime, timezone
from sqlmodel import Session, select
from models import UserProfile
from logging_client import logger


class UserProfileManager:
    """User profile manager with resource accounting"""

    @classmethod
    def get_or_create_profile(cls, session: Session, user_id: int) -> UserProfile:
        """
        Gets or creates the user profile.

        If the user has no profile, creates a new one with counters set to 0.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            User profile
        """
        try:
            statement = select(UserProfile).where(UserProfile.user_id == user_id)
            profile = session.exec(statement).first()

            if profile:
                return profile

            # Create new profile
            profile = UserProfile(user_id=user_id)
            session.add(profile)
            session.commit()
            session.refresh(profile)

            logger.info(f"[UserProfileManager] New profile created for user {user_id}")
            return profile

        except Exception as e:
            logger.error(f"[UserProfileManager] Error creating profile for user {user_id}: {e}")
            session.rollback()
            raise

    @classmethod
    def increment_words(cls, session: Session, user_id: int, amount: int = 1) -> UserProfile:
        """
        Increments the words counter.

        Args:
            session: Database session
            user_id: User ID
            amount: Amount to increment (default: 1)

        Returns:
            Updated profile
        """
        return cls._increment_counter(session, user_id, "total_words", amount)

    @classmethod
    def decrement_words(cls, session: Session, user_id: int, amount: int = 1) -> UserProfile:
        """
        Decrements the words counter.

        Args:
            session: Database session
            user_id: User ID
            amount: Amount to decrement (default: 1)

        Returns:
            Updated profile
        """
        return cls._increment_counter(session, user_id, "total_words", -amount)

    @classmethod
    def increment_examples(cls, session: Session, user_id: int, amount: int = 1) -> UserProfile:
        """Increments the examples counter."""
        return cls._increment_counter(session, user_id, "total_examples", amount)

    @classmethod
    def decrement_examples(cls, session: Session, user_id: int, amount: int = 1) -> UserProfile:
        """Decrements the examples counter."""
        return cls._increment_counter(session, user_id, "total_examples", -amount)

    @classmethod
    def increment_best_options(cls, session: Session, user_id: int, amount: int = 1) -> UserProfile:
        """Increments the best options counter."""
        return cls._increment_counter(session, user_id, "total_best_options", amount)

    @classmethod
    def decrement_best_options(cls, session: Session, user_id: int, amount: int = 1) -> UserProfile:
        """Decrements the best options counter."""
        return cls._increment_counter(session, user_id, "total_best_options", -amount)

    @classmethod
    def increment_collocations(cls, session: Session, user_id: int, amount: int = 1) -> UserProfile:
        """Increments the collocations counter."""
        return cls._increment_counter(session, user_id, "total_collocations", amount)

    @classmethod
    def decrement_collocations(cls, session: Session, user_id: int, amount: int = 1) -> UserProfile:
        """Decrements the collocations counter."""
        return cls._increment_counter(session, user_id, "total_collocations", -amount)

    @classmethod
    def increment_quick_writes(cls, session: Session, user_id: int, amount: int = 1) -> UserProfile:
        """Increments the quick writes counter."""
        return cls._increment_counter(session, user_id, "total_quick_writes", amount)

    @classmethod
    def decrement_quick_writes(cls, session: Session, user_id: int, amount: int = 1) -> UserProfile:
        """Decrements the quick writes counter."""
        return cls._increment_counter(session, user_id, "total_quick_writes", -amount)

    @classmethod
    def _increment_counter(
        cls, session: Session, user_id: int, field_name: str, amount: int
    ) -> UserProfile:
        """
        Increments or decrements a generic counter.

        Args:
            session: Database session
            user_id: User ID
            field_name: Field name to increment (e.g. 'total_words')
            amount: Amount to increment (can be negative to decrement)

        Returns:
            Updated profile
        """
        try:
            profile = cls.get_or_create_profile(session, user_id)

            # Get current value
            current_value = getattr(profile, field_name, 0)

            # Increment
            new_value = max(0, current_value + amount)  # Do not allow negative values
            setattr(profile, field_name, new_value)

            # Update timestamp
            profile.updated_at = datetime.now(timezone.utc)

            session.add(profile)
            session.commit()
            session.refresh(profile)

            logger.debug(
                f"[UserProfileManager] User {user_id}: {field_name} {current_value} → {new_value}"
            )

            return profile

        except Exception as e:
            logger.error(
                f"[UserProfileManager] Error incrementing {field_name} for user {user_id}: {e}"
            )
            session.rollback()
            raise

    @classmethod
    def get_profile(cls, session: Session, user_id: int) -> UserProfile:
        """
        Gets the user profile (or creates if not exists).

        Args:
            session: Database session
            user_id: User ID

        Returns:
            User profile
        """
        return cls.get_or_create_profile(session, user_id)

    @classmethod
    def get_total_words(cls, session: Session, user_id: int) -> int:
        """Gets the total words for the user."""
        profile = cls.get_or_create_profile(session, user_id)
        return profile.total_words

    @classmethod
    def get_total_examples(cls, session: Session, user_id: int) -> int:
        """Gets the total examples for the user."""
        profile = cls.get_or_create_profile(session, user_id)
        return profile.total_examples

    @classmethod
    def get_total_best_options(cls, session: Session, user_id: int) -> int:
        """Gets the total best options for the user."""
        profile = cls.get_or_create_profile(session, user_id)
        return profile.total_best_options

    @classmethod
    def get_total_collocations(cls, session: Session, user_id: int) -> int:
        """Gets the total collocations for the user."""
        profile = cls.get_or_create_profile(session, user_id)
        return profile.total_collocations

    @classmethod
    def get_total_quick_writes(cls, session: Session, user_id: int) -> int:
        """Gets the total quick writes for the user."""
        profile = cls.get_or_create_profile(session, user_id)
        return profile.total_quick_writes

    @classmethod
    def get_all_totals(cls, session: Session, user_id: int) -> dict:
        """
        Gets all totals for the user.

        Returns:
            Dictionary with all counters
        """
        profile = cls.get_or_create_profile(session, user_id)
        return {
            "total_words": profile.total_words,
            "total_examples": profile.total_examples,
            "total_best_options": profile.total_best_options,
            "total_collocations": profile.total_collocations,
            "total_quick_writes": profile.total_quick_writes,
        }

    @classmethod
    def rebuild_from_db(cls, session: Session, user_id: int) -> UserProfile:
        """
        Rebuilds the counters from the database.

        Useful if the counters got out of sync.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            Updated profile
        """
        from models import Word, ExampleWord, BestOption, Collocation, QuickWrite
        from sqlmodel import func, select

        try:
            profile = cls.get_or_create_profile(session, user_id)

            # Count from DB
            total_words = session.exec(
                select(func.count(Word.id)).where(Word.user_id == user_id)
            ).one() or 0

            total_examples = session.exec(
                select(func.count(ExampleWord.example_id)).join(
                    Word, Word.id == ExampleWord.word_id
                ).where(Word.user_id == user_id)
            ).one() or 0

            total_best_options = session.exec(
                select(func.count(BestOption.id)).join(
                    Word, Word.id == BestOption.word_id
                ).where(Word.user_id == user_id)
            ).one() or 0

            total_collocations = session.exec(
                select(func.count(Collocation.id)).where(Collocation.user_id == user_id)
            ).one() or 0

            total_quick_writes = session.exec(
                select(func.count(QuickWrite.id)).where(QuickWrite.user_id == user_id)
            ).one() or 0

            # Update profile
            profile.total_words = total_words
            profile.total_examples = total_examples
            profile.total_best_options = total_best_options
            profile.total_collocations = total_collocations
            profile.total_quick_writes = total_quick_writes
            profile.updated_at = datetime.now(timezone.utc)

            session.add(profile)
            session.commit()
            session.refresh(profile)

            logger.info(
                f"[UserProfileManager] Profile rebuilt for user {user_id}: "
                f"words={total_words}, examples={total_examples}, "
                f"best_options={total_best_options}, collocations={total_collocations}, "
                f"quick_writes={total_quick_writes}"
            )

            return profile

        except Exception as e:
            logger.error(f"[UserProfileManager] Error rebuilding profile for user {user_id}: {e}")
            session.rollback()
            raise
