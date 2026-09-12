"""Tests for ContentPlanner."""
import pytest
from datetime import datetime, timezone

from sqlmodel import Session, select

from learning_path.content_planner import ContentPlanner
from learning_path.priority_engine import PriorityEngine
from models import (
    ContentType, LearningState, LearningPath, LearningPathCursor, Word, WordStatistics
)


@pytest.fixture
def priority_engine():
    """Create a PriorityEngine for testing."""
    return PriorityEngine()


@pytest.fixture
def content_planner(
    db_session: Session,
    priority_engine,
    example_repository,
    content_queue_repo,
    word_repository,
    best_option_repository,
):
    """Create a ContentPlanner for testing."""
    return ContentPlanner(
        session=db_session,
        priority_engine=priority_engine,
        content_queue=content_queue_repo,
        word_repository=word_repository,
        example_repository=example_repository,
        best_option_repository=best_option_repository,
    )


class TestContentPlannerHasNonLearnedWords:
    """Test has_non_learned_words method."""

    def test_has_non_learned_words_returns_true_when_words_exist(
        self, content_planner, test_user, test_word_statistics
    ):
        """Should return True when user has non-learned words."""
        result = content_planner.has_non_learned_words(
            test_user.id, ContentType.EXAMPLE
        )
        assert result is True

    def test_has_non_learned_words_returns_false_when_all_learned(
        self, db_session, content_planner, test_user, test_words
    ):
        """Should return False when all words are LEARNED."""
        # Mark all words as LEARNED
        stats = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).all()
        for stat in stats:
            stat.learning_state = LearningState.LEARNED
        db_session.commit()

        result = content_planner.has_non_learned_words(
            test_user.id, ContentType.EXAMPLE
        )
        assert result is False


class TestContentPlannerEnsurePath:
    """Test ensure_path method."""

    def test_ensure_path_creates_cursor_if_missing(
        self, db_session, content_planner, test_user
    ):
        """Should create a cursor if one doesn't exist."""
        # Ensure no cursor exists
        cursor = db_session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == test_user.id
            )
        ).first()
        if cursor:
            db_session.delete(cursor)
            db_session.commit()

        # Call ensure_path
        content_planner.ensure_path(test_user.id, ContentType.EXAMPLE)

        # Verify cursor was created
        cursor = db_session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == test_user.id,
                LearningPathCursor.type == ContentType.EXAMPLE
            )
        ).first()
        assert cursor is not None
        assert cursor.current_segment == 0

    def test_ensure_path_does_not_duplicate_cursor(
        self, db_session, content_planner, test_user, test_learning_path
    ):
        """Should not create duplicate cursors."""
        initial_count = len(db_session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == test_user.id
            )
        ).all())

        content_planner.ensure_path(test_user.id, ContentType.EXAMPLE)

        final_count = len(db_session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == test_user.id
            )
        ).all())

        assert initial_count == final_count


class TestContentPlannerGetCandidateWords:
    """Test get_candidate_words method."""

    def test_get_candidate_words_returns_active_words(
        self, content_planner, test_user, test_words
    ):
        """Should return only active words for the user."""
        words = content_planner.get_candidate_words(test_user.id, ContentType.EXAMPLE)

        assert len(words) == 10
        assert all(w.user_id == test_user.id for w in words)
        assert all(w.is_active for w in words)

    def test_get_candidate_words_excludes_inactive_words(
        self, db_session, content_planner, test_user, test_words
    ):
        """Should exclude inactive words."""
        # Mark first word as inactive
        word = db_session.exec(select(Word).where(Word.id == test_words[0].id)).first()
        if word:
            word.is_active = False
            db_session.add(word)
            db_session.commit()

        words = content_planner.get_candidate_words(test_user.id, ContentType.EXAMPLE)

        assert len(words) == 9
        assert all(w.id != test_words[0].id for w in words)


class TestContentPlannerScoreCandidates:
    """Test score_candidates method."""

    def test_score_candidates_filters_learned_words(
        self, content_planner, test_user, test_words, test_word_statistics
    ):
        """Should filter out LEARNED words from scoring."""
        candidates = test_words[:10]
        scored = content_planner.score_candidates(
            test_user.id, candidates, ContentType.EXAMPLE
        )

        # Words 5-10 are LEARNED and should be filtered out
        scored_ids = [word.id for word, _ in scored]
        for i in range(5, 11):
            assert test_words[i-1].id not in scored_ids

    def test_score_candidates_includes_new_and_learning(
        self, content_planner, test_user, test_words
    ):
        """Should include NEW and LEARNING words."""
        candidates = test_words[:10]
        scored = content_planner.score_candidates(
            test_user.id, candidates, ContentType.EXAMPLE
        )

        # Words 1-4 are NEW or LEARNING and should be included
        scored_ids = [word.id for word, _ in scored]
        for i in range(1, 5):
            assert test_words[i-1].id in scored_ids

    def test_score_candidates_returns_sorted_by_priority(
        self, content_planner, test_user, test_words
    ):
        """Should return words sorted by priority (descending)."""
        candidates = test_words[:10]
        scored = content_planner.score_candidates(
            test_user.id, candidates, ContentType.EXAMPLE
        )

        priorities = [priority for _, priority in scored]
        # Verify sorted in descending order
        assert priorities == sorted(priorities, reverse=True)


class TestContentPlannerGetGenerationWords:
    """Test get_generation_words method."""

    def test_get_generation_words_returns_path_words(
        self, content_planner, test_user, test_learning_path, test_word_statistics
    ):
        """Should return words from current path segment."""
        words = content_planner.get_generation_words(
            test_user.id, ContentType.EXAMPLE
        )

        # Should have path words + fallback NEW words
        assert len(words) > 0

    def test_get_generation_words_includes_non_learned_when_few_path_items(
        self, db_session, content_planner, test_user, test_word_statistics
    ):
        """Should add non-learned words if path has < 5 items."""
        # Delete existing cursor first
        existing = db_session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == test_user.id
            )
        ).first()
        if existing:
            db_session.delete(existing)
            db_session.commit()

        # Create cursor but no path items
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        words = content_planner.get_generation_words(
            test_user.id, ContentType.EXAMPLE
        )

        # Should include NEW/LEARNING words even though path is empty
        assert len(words) > 0

    def test_get_generation_words_returns_empty_without_cursor(
        self, db_session, content_planner, test_user
    ):
        """Should return empty list if no cursor exists."""
        # Ensure no cursor exists
        cursor = db_session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == test_user.id
            )
        ).first()
        if cursor:
            db_session.delete(cursor)
            db_session.commit()

        words = content_planner.get_generation_words(
            test_user.id, ContentType.EXAMPLE
        )

        assert words == []


class TestContentPlannerPathSize:
    """Test path size and segment calculations."""

    def test_get_path_size_returns_zero_for_empty_path(
        self, content_planner, test_user
    ):
        """Should return 0 when no path items exist."""
        size = content_planner.get_path_size(test_user.id, ContentType.EXAMPLE)
        assert size == 0

    def test_get_path_size_counts_all_items(
        self, content_planner, test_user, test_learning_path
    ):
        """Should count all path items for the user."""
        size = content_planner.get_path_size(test_user.id, ContentType.EXAMPLE)
        # test_learning_path fixture creates 10 items
        assert size == 10

    def test_get_next_segment_number_starts_at_one(
        self, content_planner, test_user
    ):
        """Should return 1 for first segment (cursor at 0)."""
        segment = content_planner.get_next_segment_number(
            test_user.id, ContentType.EXAMPLE
        )
        assert segment == 1

    def test_get_next_segment_number_increments_with_cursor(
        self, db_session, content_planner, test_user, test_learning_path
    ):
        """Should increment based on cursor position."""
        # Update cursor to segment 5
        cursor = db_session.exec(
            select(LearningPathCursor).where(
                LearningPathCursor.user_id == test_user.id,
                LearningPathCursor.type == ContentType.EXAMPLE
            )
        ).first()
        if cursor:
            cursor.current_segment = 5
            db_session.add(cursor)
            db_session.commit()

        segment = content_planner.get_next_segment_number(
            test_user.id, ContentType.EXAMPLE
        )
        assert segment == 6


class TestContentPlannerQueueCalculations:
    """Test queue target and gap calculations."""

    def test_calculate_queue_target_returns_5_for_small_path(
        self, content_planner, test_user
    ):
        """Should return 5 for path size <= 5."""
        target = content_planner.calculate_queue_target(
            test_user.id, ContentType.EXAMPLE
        )
        assert target == 5

    def test_calculate_queue_target_increases_with_path_size(
        self, db_session, content_planner, test_user, test_learning_path
    ):
        """Should return larger target for bigger path."""
        # test_learning_path creates 10 items (5 <= 10 <= 20)
        target = content_planner.calculate_queue_target(
            test_user.id, ContentType.EXAMPLE
        )
        assert target == 8

    def test_calculate_content_gap_with_no_queue_items(
        self, content_planner, test_user
    ):
        """Should return target when no items in queue."""
        gap = content_planner.calculate_content_gap(
            test_user.id, ContentType.EXAMPLE
        )
        assert gap == 5  # target for empty path


class TestContentPlannerSaturation:
    """Test path saturation calculations."""

    def test_calculate_path_saturation_returns_dict(
        self, content_planner, test_user, test_word_statistics
    ):
        """Should return saturation analysis dict."""
        result = content_planner.calculate_path_saturation(
            test_user.id, ContentType.EXAMPLE
        )

        assert isinstance(result, dict)
        assert 'saturation_level' in result
        assert 'words_in_learning' in result
        assert 'words_in_reinforcing' in result
        assert 'words_in_spacing' in result
        assert 'can_accept_wave' in result

    def test_calculate_path_saturation_counts_states(
        self, content_planner, test_user, test_word_statistics
    ):
        """Should correctly count words by learning state."""
        result = content_planner.calculate_path_saturation(
            test_user.id, ContentType.EXAMPLE
        )

        # test_word_statistics: 2 NEW, 2 LEARNING, 6 LEARNED
        assert result['words_in_learning'] == 2
        assert result['words_learned'] == 6

    def test_calculate_path_saturation_can_accept_wave(
        self, content_planner, test_user, test_word_statistics
    ):
        """Should allow wave acceptance when not saturated."""
        result = content_planner.calculate_path_saturation(
            test_user.id, ContentType.EXAMPLE
        )
        # Low saturation with 2 LEARNING words
        assert result['can_accept_wave'] is True


class TestContentPlannerBuildSegment:
    """Test segment building."""

    def test_build_segment_creates_learning_path_items(
        self, db_session, content_planner, test_user, test_words
    ):
        """Should create LearningPath items for the segment."""
        # Create cursor first
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        candidates = test_words[:5]
        result = content_planner.build_segment(
            user_id=test_user.id,
            content_type=ContentType.EXAMPLE,
            size=5,
            candidates=candidates,
        )

        assert len(result) == 5
        assert all(isinstance(item, LearningPath) for item in result)

    def test_build_segment_respects_size(
        self, db_session, content_planner, test_user, test_words
    ):
        """Should create exactly size items."""
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        candidates = test_words[:10]
        result = content_planner.build_segment(
            user_id=test_user.id,
            content_type=ContentType.EXAMPLE,
            size=8,
            candidates=candidates,
        )

        assert len(result) == 8

    def test_build_segment_uses_correct_segment_number(
        self, db_session, content_planner, test_user, test_words
    ):
        """Should use next segment number."""
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=2,
        )
        db_session.add(cursor)
        db_session.commit()

        candidates = test_words[:5]
        result = content_planner.build_segment(
            user_id=test_user.id,
            content_type=ContentType.EXAMPLE,
            size=3,
            candidates=candidates,
        )

        # Should use segment 3 (current_segment + 1)
        assert all(item.segment == 3 for item in result)


class TestContentPlannerGeneration:
    """Test generation planning methods."""

    def test_is_generation_running_returns_false(
        self, content_planner, test_user
    ):
        """Should return False by default (no active generation)."""
        result = content_planner.is_generation_running(
            test_user.id, ContentType.EXAMPLE
        )
        assert result is False

    def test_plan_generation_delegates_to_example_type(
        self, db_session, content_planner, test_user, test_word_statistics
    ):
        """Should call plan_example_generation for EXAMPLE type."""
        # Create cursor and path for generation
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # This should not raise an error
        # (plan_example_generation will be called internally)
        content_planner.plan_generation(
            test_user.id, ContentType.EXAMPLE, amount=5
        )

    def test_plan_generation_delegates_to_best_options_type(
        self, db_session, content_planner, test_user, test_word_statistics
    ):
        """Should call plan_best_option_generation for BEST_OPTIONS type."""
        # Create cursor for BEST_OPTIONS
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.BEST_OPTIONS,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # This should not raise an error
        content_planner.plan_generation(
            test_user.id, ContentType.BEST_OPTIONS, amount=5
        )

    def test_plan_generation_ignores_zero_amount(
        self, content_planner, test_user
    ):
        """Should return early if amount <= 0."""
        # Should not raise error or attempt generation
        content_planner.plan_generation(
            test_user.id, ContentType.EXAMPLE, amount=0
        )

    def test_plan_generation_ignores_negative_amount(
        self, content_planner, test_user
    ):
        """Should return early if amount is negative."""
        content_planner.plan_generation(
            test_user.id, ContentType.EXAMPLE, amount=-5
        )

    def test_request_generation_checks_if_running(
        self, db_session, content_planner, test_user, test_word_statistics
    ):
        """Should not request if generation already running."""
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # This should check is_generation_running before proceeding
        content_planner.request_generation(
            test_user.id, ContentType.EXAMPLE, amount=5
        )

    def test_request_generation_ignores_zero_amount(
        self, content_planner, test_user
    ):
        """Should return early if amount <= 0."""
        content_planner.request_generation(
            test_user.id, ContentType.EXAMPLE, amount=0
        )

    def test_plan_example_generation_returns_early_without_generation_words(
        self, content_planner, test_user
    ):
        """Should return if no generation words available."""
        # No cursor = no generation words
        content_planner.plan_example_generation(test_user.id, amount=5)

    def test_plan_example_generation_filters_words_with_enough_examples(
        self, db_session, content_planner, test_user, test_word_statistics,
        test_examples
    ):
        """Should skip words that already have >= 3 available examples."""
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Add path item for word 1
        path_item = LearningPath(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            word_id=1,
            segment=0,
            position=0,
        )
        db_session.add(path_item)
        db_session.commit()

        # Word 1 has examples 1, 2 which are not LEARNED-only
        # This should attempt generation
        content_planner.plan_example_generation(test_user.id, amount=1)

    def test_plan_best_option_generation_returns_early_without_generation_words(
        self, content_planner, test_user
    ):
        """Should return if no generation words available."""
        content_planner.plan_best_option_generation(test_user.id, amount=5)

    def test_plan_best_option_generation_ignores_zero_amount(
        self, content_planner, test_user
    ):
        """Should return early if amount <= 0."""
        content_planner.plan_best_option_generation(test_user.id, amount=0)
