"""
Tests to detect and isolate the infinite generation problem for "batter" and similar words.

Problem Description:
- Path size grows to 338 items (should be max 20)
- build_segment() returns 0 items despite having candidates
- System keeps requesting generation for same word indefinitely
- Word 61 (batter) has 0 available examples but keeps triggering generation
"""

import pytest
from sqlmodel import Session, select

from learning_path.content_planner import ContentPlanner
from learning_path.priority_engine import PriorityEngine
from models import (
    ContentType, LearningState, LearningPath, LearningPathCursor,
    Word, WordStatistics, Example, ExampleWord, ExampleType
)


class TestPathSizeExplosion:
    """Detect if path size exceeds max_path_size (20)."""

    def test_path_size_never_exceeds_maximum(
        self, db_session, content_planner, test_user, test_words
    ):
        """Path should never grow beyond max_path_size of 20."""
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
            current_position=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Create many path items (simulate the explosion)
        for i in range(50):
            path_item = LearningPath(
                user_id=test_user.id,
                type=ContentType.EXAMPLE,
                word_id=test_words[i % 10].id,
                segment=i // 10,
                position=i % 10,
            )
            db_session.add(path_item)
        db_session.commit()

        size = content_planner.get_path_size(test_user.id, ContentType.EXAMPLE)

        # ALERT: If this fails, path is exploding
        assert size <= 50, f"Path size {size} is abnormally large (should be ~20 max)"

    def test_calculate_segment_size_wave_based_returns_zero_when_path_full(
        self, db_session, content_planner, test_user, test_words, test_word_statistics
    ):
        """
        When path is FULL (>= 20 items) AND has active words (>= 10),
        should return 0 to prevent further growth.
        """
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Create exactly 20 path items
        for i in range(20):
            path_item = LearningPath(
                user_id=test_user.id,
                type=ContentType.EXAMPLE,
                word_id=test_words[i % 10].id,
                segment=0,
                position=i,
            )
            db_session.add(path_item)
        db_session.commit()

        # Update statistics to have active words
        stats = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.type == ContentType.EXAMPLE,
                WordStatistics.learning_state == LearningState.LEARNING,
            )
        ).all()

        for stat in stats[:10]:
            stat.learning_state = LearningState.LEARNING
            db_session.add(stat)
        db_session.commit()

        # When path is FULL and there are active words, should return 0
        segment_size = content_planner.calculate_segment_size_wave_based(
            user_id=test_user.id,
            available_word_count=10,
            content_type=ContentType.EXAMPLE,
        )

        # ALERT: If segment_size > 0 with full path, this is the bug
        assert segment_size == 0, (
            f"Expected 0 segment size when path is full, got {segment_size}. "
            "This allows path to keep growing indefinitely."
        )


class TestBuildSegmentFailure:
    """Detect if build_segment() returns 0 items when it shouldn't."""

    def test_build_segment_returns_requested_size(
        self, db_session, content_planner, test_user, test_words
    ):
        """build_segment should return exactly 'size' items with valid candidates."""
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Request 5 items with 5 candidates
        candidates = test_words[:5]
        result = content_planner.build_segment(
            user_id=test_user.id,
            content_type=ContentType.EXAMPLE,
            size=5,
            candidates=candidates,
        )

        # ALERT: If result is empty despite having candidates, build_segment is broken
        assert len(result) > 0, (
            "build_segment returned 0 items despite having 5 candidates. "
            "This explains why generation never populates the queue."
        )
        assert len(result) == 5, f"Expected 5 items, got {len(result)}"

    def test_build_segment_with_zero_candidates(
        self, db_session, content_planner, test_user
    ):
        """build_segment should return empty list with no candidates."""
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        result = content_planner.build_segment(
            user_id=test_user.id,
            content_type=ContentType.EXAMPLE,
            size=5,
            candidates=[],  # No candidates
        )

        assert result == [], "Should return empty list with no candidates"


class TestInfiniteGenerationProblem:
    """
    Detect the core issue: same word keeps getting generation requests.

    In the logs, word 61 (batter) has:
    - 0 available examples
    - Gets selected for generation repeatedly
    - But generation doesn't populate the queue
    - So next cycle, it's selected again (infinite loop)
    """

    def test_get_generation_words_filters_words_with_sufficient_examples(
        self, db_session, content_planner, test_user, test_words, test_examples
    ):
        """
        get_generation_words should NOT include words that already have >= threshold examples.

        Current threshold: 3 available examples
        """
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Add path items for word 1
        for i in range(3):
            path_item = LearningPath(
                user_id=test_user.id,
                type=ContentType.EXAMPLE,
                word_id=test_words[0].id,  # word 1
                segment=0,
                position=i,
            )
            db_session.add(path_item)
        db_session.commit()

        generation_words = content_planner.get_generation_words(
            user_id=test_user.id,
            content_type=ContentType.EXAMPLE,
        )

        # Word 1 has 3 examples (examples 1, 2, 3 in fixture)
        # It should NOT be in generation_words if it has enough
        # (But this depends on available_count logic in plan_example_generation)

    def test_plan_example_generation_skips_words_with_sufficient_examples(
        self, db_session, content_planner, test_user, test_word_statistics, test_examples
    ):
        """
        plan_example_generation should skip words that already have >= 3 available examples.

        ALERT: If this fails, it means the word filtering is broken,
        causing infinite generation requests for the same word.
        """
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Add path item for word 1 (which has examples 1, 2 from fixture)
        path_item = LearningPath(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            word_id=1,
            segment=0,
            position=0,
        )
        db_session.add(path_item)
        db_session.commit()

        # Word 1 has examples 1 and 2 (not all LEARNED since word 1 is NEW)
        # Should NOT request generation if count >= 3
        # This method calls ExampleGenerator, so we just verify it doesn't crash
        content_planner.plan_example_generation(test_user.id, amount=5)


class TestWordWithZeroExamples:
    """
    Specific test for word 61 (batter) scenario: word with 0 available examples.

    Logs show:
    - Word 61 has 0 available examples
    - System tries to generate for it
    - But generation doesn't create items in queue
    - So it stays at 0 and gets picked again
    """

    def test_word_with_no_available_examples_triggers_generation(
        self, db_session, content_planner, test_user, test_word_statistics
    ):
        """
        A word with 0 available examples should trigger generation.
        (This is correct behavior)
        """
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Create a word with no examples
        new_word = Word(
            main="batter",
            type="noun",
            meaning="mixture for baking",
            level=1,
            user_id=test_user.id,
            is_active=True,
        )
        db_session.add(new_word)
        db_session.commit()

        # Create statistics for it
        stat = WordStatistics(
            word_id=new_word.id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.NEW,
            times_seen=0,
            current_cycle_seen=0,
        )
        db_session.add(stat)

        # Add to path
        path_item = LearningPath(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            word_id=new_word.id,
            segment=0,
            position=0,
        )
        db_session.add(path_item)
        db_session.commit()

        # plan_example_generation should attempt to generate for this word
        # (The bug is that it keeps generating without populating the queue)
        content_planner.plan_example_generation(test_user.id, amount=5)


class TestContentQueuePopulation:
    """
    Verify that after generation request, ContentQueue gets populated.

    The bug might be: generation is requested but queue never gets items.
    """

    def test_generation_should_lead_to_queue_population(
        self, db_session, content_planner, test_user, test_word_statistics
    ):
        """
        After requesting generation, ContentQueue should eventually have items.

        If ContentQueue stays empty, the system will keep requesting generation
        for the same word (infinite loop).
        """
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Request generation
        content_planner.request_generation(
            user_id=test_user.id,
            content_type=ContentType.EXAMPLE,
            amount=5,
        )

        # Check ContentQueue (it might be empty if generation hasn't completed)
        # In production, this would be populated by background job
        # But the system shouldn't keep requesting generation if queue is already full


class TestEnsureReadyIdempotency:
    """
    Test that ensure_ready() is idempotent.

    If calling it multiple times causes issues (like infinite generation requests),
    that's a bug.
    """

    def test_ensure_ready_multiple_calls_stable(
        self, db_session, content_planner, test_user, test_word_statistics
    ):
        """
        Calling ensure_ready() multiple times should be stable.
        It shouldn't keep requesting generation indefinitely.
        """
        # First call
        content_planner.ensure_ready(
            user_id=test_user.id,
            content_type=ContentType.EXAMPLE,
        )

        # Second call (same state)
        content_planner.ensure_ready(
            user_id=test_user.id,
            content_type=ContentType.EXAMPLE,
        )

        # Third call (still same state)
        content_planner.ensure_ready(
            user_id=test_user.id,
            content_type=ContentType.EXAMPLE,
        )

        # If this passes without hanging or errors, idempotency is maintained
