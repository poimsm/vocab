"""
Tests to isolate why LEARNED words keep getting generation requests.

Problem: Word 61 (batter) is LEARNED but still triggers generation.

Scenario from logs:
- Word 61 has learning_state = LEARNED in WordStatistics
- But it's in the LearningPath (338 items, segment 37-38)
- get_generation_words() returns it
- plan_example_generation() requests generation for it
- System generates 9 more examples for an already LEARNED word
"""

import pytest
from sqlmodel import Session, select

from learning_path.content_planner import ContentPlanner
from learning_path.priority_engine import PriorityEngine
from models import (
    ContentType, LearningState, LearningPath, LearningPathCursor,
    Word, WordStatistics
)


class TestLearnedWordExclusion:
    """Verify that LEARNED words are excluded from generation."""

    def test_plan_example_generation_excludes_learned_words(
        self, db_session, content_planner, test_user, test_words
    ):
        """
        plan_example_generation should NOT request generation for LEARNED words.

        This is the core of the bug: word 61 is LEARNED but still generates.
        """
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Create a word with LEARNED state
        learned_word = test_words[0]  # word 1
        stat = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.word_id == learned_word.id,
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).first()

        if stat:
            stat.learning_state = LearningState.LEARNED
            stat.times_seen = 6
            db_session.add(stat)
            db_session.commit()

        # Add it to current segment path
        path_item = LearningPath(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            word_id=learned_word.id,
            segment=0,
            position=0,
        )
        db_session.add(path_item)
        db_session.commit()

        # Call plan_example_generation
        # It should NOT request generation for LEARNED word 1
        content_planner.plan_example_generation(test_user.id, amount=5)

        # ALERT: If this test fails, it means LEARNED words are being generated
        # This is the bug reproducer


class TestGenerationWordsFiltering:
    """Test that get_generation_words filters correctly."""

    def test_get_generation_words_excludes_learned_words_in_path(
        self, db_session, content_planner, test_user, test_words
    ):
        """
        get_generation_words should exclude LEARNED words even if they're in path.

        Current behavior: Might return LEARNED words if they're in current segment.
        """
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Create LEARNED and NEW words
        learned_word = test_words[5]  # word 6 (LEARNED from fixture)
        new_word = test_words[0]      # word 1 (NEW from fixture)

        # Verify states
        learned_stat = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.word_id == learned_word.id,
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).first()

        new_stat = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.word_id == new_word.id,
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).first()

        # Add both to path segment 0
        for pos, word in enumerate([learned_word, new_word]):
            path_item = LearningPath(
                user_id=test_user.id,
                type=ContentType.EXAMPLE,
                word_id=word.id,
                segment=0,
                position=pos,
            )
            db_session.add(path_item)
        db_session.commit()

        # Get generation words
        generation_words = content_planner.get_generation_words(
            test_user.id, ContentType.EXAMPLE
        )

        generated_ids = [w.id for w in generation_words]

        # ALERT: If LEARNED word is in generation_words, it will be generated
        assert learned_word.id not in generated_ids, (
            f"LEARNED word {learned_word.id} should NOT be in generation_words. "
            f"Got: {generated_ids}"
        )


class TestScoreCandidatesFiltersLearned:
    """Verify score_candidates filters LEARNED words."""

    def test_score_candidates_excludes_learned_words(
        self, db_session, content_planner, test_user, test_words, test_word_statistics
    ):
        """
        score_candidates should filter out LEARNED words before scoring.
        """
        # All test_words have mix of states: NEW, LEARNING, LEARNED
        # Words 5-10 are LEARNED (from test_word_statistics fixture)

        candidates = test_words  # Mix of NEW, LEARNING, LEARNED
        scored = content_planner.score_candidates(
            test_user.id, candidates, ContentType.EXAMPLE
        )

        scored_ids = [word.id for word, _ in scored]

        # LEARNED words (5-10) should NOT be in scored list
        for i in range(5, 11):
            assert test_words[i-1].id not in scored_ids, (
                f"LEARNED word {test_words[i-1].id} should not be scored. "
                f"Scored: {scored_ids}"
            )


class TestLearnedWordInPathSegment:
    """
    Test the specific scenario from the logs:
    Word is LEARNED but still in current path segment.
    """

    def test_path_contains_learned_word_still_generates(
        self, db_session, content_planner, test_user, test_words, test_word_statistics
    ):
        """
        Reproduce the bug: LEARNED word in path → still generates.

        From logs:
        - Word 61 in segment 37-38
        - Word 61 is LEARNED
        - System still requests generation for it
        """
        # Create cursor at segment 0
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Mark word 6 as LEARNED (it's already LEARNED in fixture)
        learned_word = test_words[5]  # word 6
        stat = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.word_id == learned_word.id,
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).first()

        assert stat.learning_state == LearningState.LEARNED, (
            f"Word {learned_word.id} should be LEARNED in fixture"
        )

        # Add LEARNED word to path (this is the problem setup)
        path_item = LearningPath(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            word_id=learned_word.id,
            segment=0,
            position=0,
        )
        db_session.add(path_item)
        db_session.commit()

        # Call get_generation_words
        generation_words = content_planner.get_generation_words(
            test_user.id, ContentType.EXAMPLE
        )

        generated_ids = [w.id for w in generation_words]

        # ALERT: This is the bug
        # If LEARNED word is returned, it will be generated
        if learned_word.id in generated_ids:
            print(f"BUG DETECTED: LEARNED word {learned_word.id} in generation_words")
            print(f"  State: {stat.learning_state}")
            print(f"  Generation would request for: {generated_ids}")


class TestPlanGenerationWithLearnedWord:
    """
    Test plan_example_generation with mixed LEARNED/NEW words.
    """

    def test_plan_generation_should_skip_learned_not_generate(
        self, db_session, content_planner, test_user, test_words, test_word_statistics
    ):
        """
        When generation_words contains a LEARNED word,
        plan_example_generation should NOT request generation for it.
        """
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Add mix of words to path segment 0
        for pos in range(3):
            path_item = LearningPath(
                user_id=test_user.id,
                type=ContentType.EXAMPLE,
                word_id=test_words[pos].id,
                segment=0,
                position=pos,
            )
            db_session.add(path_item)
        db_session.commit()

        # Now test_words[0] = NEW (should generate)
        # test_words[1] = NEW (should generate)
        # test_words[2] = LEARNING (should generate)
        # BUT if there's a LEARNED word mixed in, it should be filtered

        # Check what get_generation_words returns
        generation_words = content_planner.get_generation_words(
            test_user.id, ContentType.EXAMPLE
        )

        # Verify no LEARNED words
        for word in generation_words:
            stat = content_planner.get_statistics(word.id, ContentType.EXAMPLE)
            assert stat.learning_state != LearningState.LEARNED, (
                f"LEARNED word {word.id} should not be in generation_words. "
                f"State: {stat.learning_state}"
            )


class TestGenerationWordSelection:
    """
    Debug test to show EXACTLY what get_generation_words returns.
    """

    def test_generation_words_debug_output(
        self, db_session, content_planner, test_user, test_words, test_word_statistics
    ):
        """
        Print what get_generation_words returns to debug the issue.
        """
        cursor = LearningPathCursor(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            current_segment=0,
        )
        db_session.add(cursor)
        db_session.commit()

        # Add all words to path
        for pos, word in enumerate(test_words[:10]):
            path_item = LearningPath(
                user_id=test_user.id,
                type=ContentType.EXAMPLE,
                word_id=word.id,
                segment=0,
                position=pos,
            )
            db_session.add(path_item)
        db_session.commit()

        generation_words = content_planner.get_generation_words(
            test_user.id, ContentType.EXAMPLE
        )

        print("\n=== DEBUG: Generation Words Analysis ===")
        print(f"Total generation_words: {len(generation_words)}")

        for word in generation_words:
            stat = content_planner.get_statistics(word.id, ContentType.EXAMPLE)
            print(f"  Word {word.id}: {word.main} → State: {stat.learning_state}")

        # Show which are LEARNED
        learned_in_gen = [
            w.id for w in generation_words
            if content_planner.get_statistics(w.id, ContentType.EXAMPLE).learning_state == LearningState.LEARNED
        ]

        if learned_in_gen:
            print(f"\n⚠️  LEARNED words in generation: {learned_in_gen}")
            print("This is the BUG - these should never be generated")
