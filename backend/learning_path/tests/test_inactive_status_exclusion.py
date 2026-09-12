"""
Tests to detect if inactive words are being counted/considered in generation logic.

Problem: Word 27 (ship) is is_active=FALSE but learning_state=NEW.
Hypothesis: Inactive words are being counted somewhere, causing:
- has_non_learned_words() to return True (even though all active words are learned)
- System thinks it needs to generate content
- But can't because words are inactive
- Result: Endpoint always returns "generating" but never actually generates
"""

import pytest
from sqlmodel import Session, select

from learning_path.content_planner import ContentPlanner
from models import (
    ContentType, LearningState, Word, WordStatistics
)


class TestInactiveWordsExclusion:
    """Verify that inactive words are completely excluded from generation logic."""

    def test_has_non_learned_words_excludes_inactive_words(
        self, db_session, content_planner, test_user, test_words, test_word_statistics
    ):
        """
        has_non_learned_words should return False if:
        - All ACTIVE words are LEARNED
        - Even if there are INACTIVE words with NEW/LEARNING state
        """
        # Mark all active words as LEARNED
        stats = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).all()
        for stat in stats:
            stat.learning_state = LearningState.LEARNED
        db_session.commit()

        # Now deactivate word 1 and set it to NEW
        word_1 = db_session.exec(
            select(Word).where(Word.id == test_words[0].id)
        ).first()
        word_1.is_active = False
        db_session.add(word_1)
        db_session.commit()

        # Set its stats to NEW
        stat_1 = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.word_id == test_words[0].id,
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).first()
        if stat_1:
            stat_1.learning_state = LearningState.NEW
            db_session.add(stat_1)
            db_session.commit()

        # Now check: should return False because all ACTIVE words are LEARNED
        result = content_planner.has_non_learned_words(
            test_user.id, ContentType.EXAMPLE
        )

        assert result is False, (
            "has_non_learned_words should return False when all ACTIVE words are LEARNED, "
            "even if inactive words are NEW. "
            f"Got True, meaning inactive words are being counted."
        )

    def test_get_candidate_words_excludes_inactive_words(
        self, db_session, content_planner, test_user, test_words
    ):
        """
        get_candidate_words should exclude inactive words completely.
        """
        # Make word 1 inactive
        word_1 = db_session.exec(
            select(Word).where(Word.id == test_words[0].id)
        ).first()
        word_1.is_active = False
        db_session.add(word_1)
        db_session.commit()

        # Get candidates
        candidates = content_planner.get_candidate_words(
            test_user.id, ContentType.EXAMPLE
        )

        candidate_ids = [w.id for w in candidates]

        assert test_words[0].id not in candidate_ids, (
            f"Inactive word {test_words[0].id} should NOT be in candidates. "
            f"Got candidates: {candidate_ids}"
        )

        # Should have 9 instead of 10
        assert len(candidates) == 9, (
            f"Should have 9 candidates (10 - 1 inactive), got {len(candidates)}"
        )

    def test_score_candidates_excludes_inactive_words(
        self, db_session, content_planner, test_user, test_words, test_word_statistics
    ):
        """
        score_candidates should exclude inactive words even if passed as candidates.
        """
        # Make word 1 inactive
        word_1 = db_session.exec(
            select(Word).where(Word.id == test_words[0].id)
        ).first()
        word_1.is_active = False
        db_session.add(word_1)
        db_session.commit()

        # Try to score all words including inactive
        candidates = test_words[:5]
        scored = content_planner.score_candidates(
            test_user.id, candidates, ContentType.EXAMPLE
        )

        scored_ids = [word.id for word, _ in scored]

        assert test_words[0].id not in scored_ids, (
            f"Inactive word {test_words[0].id} should NOT be scored. "
            f"Got: {scored_ids}"
        )

    def test_get_generation_words_excludes_inactive_words(
        self, db_session, content_planner, test_user, test_words, test_word_statistics, test_learning_path
    ):
        """
        get_generation_words should exclude inactive words completely.
        """
        # Make word 1 inactive
        word_1 = db_session.exec(
            select(Word).where(Word.id == test_words[0].id)
        ).first()
        word_1.is_active = False
        db_session.add(word_1)
        db_session.commit()

        # Get generation words
        gen_words = content_planner.get_generation_words(
            test_user.id, ContentType.EXAMPLE
        )

        gen_ids = [w.id for w in gen_words]

        assert test_words[0].id not in gen_ids, (
            f"Inactive word {test_words[0].id} should NOT be in generation_words. "
            f"Got: {gen_ids}"
        )


class TestInactiveWordsProblemScenario:
    """
    Reproduce the exact scenario from production:
    - Word 27 (ship) is inactive
    - Word 27 has learning_state = NEW
    - System thinks it has non-learned words
    - But can't actually generate because word is inactive
    - Result: endpoint returns "generating" forever
    """

    def test_inactive_new_word_causes_false_generation_availability(
        self, db_session, content_planner, test_user, test_words, test_word_statistics
    ):
        """
        Scenario: All active words are LEARNED, but one inactive word is NEW.
        Expected: System should recognize NO non-learned words to generate.
        Actual (buggy): System thinks there ARE words to generate (counting inactive).
        """
        # Mark all words as LEARNED
        stats = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).all()
        for stat in stats:
            stat.learning_state = LearningState.LEARNED
        db_session.commit()

        # Create one NEW word that is inactive (like word 27 in production)
        problem_word = Word(
            id=999,
            main="ship",
            type="noun",
            meaning="a large boat",
            level=1,
            user_id=test_user.id,
            is_active=False,  # ← INACTIVE
            is_boosted=False,
            batch_id=None,
        )
        db_session.add(problem_word)
        db_session.commit()

        # Add its statistics with NEW state
        problem_stat = WordStatistics(
            word_id=problem_word.id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.NEW,  # ← NEW but INACTIVE
            times_seen=0,
            current_cycle_seen=0,
        )
        db_session.add(problem_stat)
        db_session.commit()

        # Now check: should return False because the only NEW word is inactive
        result = content_planner.has_non_learned_words(
            test_user.id, ContentType.EXAMPLE
        )

        assert result is False, (
            "ALERT: System thinks there are non-learned words to generate! "
            "But the only NEW word is INACTIVE. "
            "This is why endpoint returns 'generating' forever. "
            f"has_non_learned_words returned: {result} (should be False)"
        )

    def test_all_candidates_filtered_when_only_inactive_words_exist(
        self, db_session, content_planner, test_user, test_words, test_word_statistics
    ):
        """
        When scoring candidates:
        - All words are candidates
        - But all are either LEARNED or INACTIVE
        - Result should be empty scored list
        """
        # Mark all words INACTIVE
        for word in test_words[:10]:
            w = db_session.exec(select(Word).where(Word.id == word.id)).first()
            w.is_active = False
            db_session.add(w)
        db_session.commit()

        # Try to score them
        candidates = test_words[:10]
        scored = content_planner.score_candidates(
            test_user.id, candidates, ContentType.EXAMPLE
        )

        assert len(scored) == 0, (
            f"Scoring inactive words should return empty list, got {len(scored)} words. "
            f"This means inactive words are NOT being filtered out!"
        )

    def test_ensure_ready_with_only_inactive_new_words(
        self, db_session, content_planner, test_user, test_words, test_word_statistics
    ):
        """
        When ensure_ready is called:
        - All active words are LEARNED
        - One inactive word is NEW
        - System should recognize NO work to do
        - Should NOT trigger generation
        """
        # Mark all as LEARNED
        stats = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).all()
        for stat in stats:
            stat.learning_state = LearningState.LEARNED
        db_session.commit()

        # Deactivate one word and set to NEW
        word_1 = db_session.exec(
            select(Word).where(Word.id == test_words[0].id)
        ).first()
        word_1.is_active = False
        db_session.add(word_1)

        stat_1 = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.word_id == test_words[0].id,
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).first()
        stat_1.learning_state = LearningState.NEW
        db_session.add(stat_1)
        db_session.commit()

        # Check: has_non_learned_words should return False
        # Because all ACTIVE words are LEARNED (only NEW word is INACTIVE)
        has_non_learned = content_planner.has_non_learned_words(
            test_user.id, ContentType.EXAMPLE
        )

        assert has_non_learned is False, (
            f"Should have NO non-learned ACTIVE words, but has_non_learned_words={has_non_learned}. "
            f"The only NEW word is INACTIVE so system should recognize no work to do."
        )

    def test_inactive_new_word_detailed_breakdown(
        self, db_session, content_planner, test_user, test_words, test_word_statistics
    ):
        """
        Detailed check showing exactly what's happening:
        - Total words
        - Active words count
        - Inactive words count
        - New words count
        - Non-learned active words count
        """
        # Mark all as LEARNED
        stats = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).all()
        for stat in stats:
            stat.learning_state = LearningState.LEARNED
        db_session.commit()

        # Deactivate word 1
        word_1 = db_session.exec(
            select(Word).where(Word.id == test_words[0].id)
        ).first()
        word_1.is_active = False
        db_session.add(word_1)

        stat_1 = db_session.exec(
            select(WordStatistics).where(
                WordStatistics.word_id == test_words[0].id,
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).first()
        stat_1.learning_state = LearningState.NEW
        db_session.add(stat_1)
        db_session.commit()

        # Count different categories
        total_words = db_session.exec(
            select(Word).where(Word.user_id == test_user.id)
        ).all()

        active_words = db_session.exec(
            select(Word).where(
                Word.user_id == test_user.id,
                Word.is_active == True
            )
        ).all()

        inactive_words = db_session.exec(
            select(Word).where(
                Word.user_id == test_user.id,
                Word.is_active == False
            )
        ).all()

        new_words = db_session.exec(
            select(Word)
            .join(WordStatistics, Word.id == WordStatistics.word_id)
            .where(
                Word.user_id == test_user.id,
                WordStatistics.type == ContentType.EXAMPLE,
                WordStatistics.learning_state == LearningState.NEW
            )
        ).all()

        active_non_learned = db_session.exec(
            select(Word)
            .join(WordStatistics, Word.id == WordStatistics.word_id)
            .where(
                Word.user_id == test_user.id,
                Word.is_active == True,
                WordStatistics.type == ContentType.EXAMPLE,
                WordStatistics.learning_state != LearningState.LEARNED
            )
        ).all()

        print("\n=== BREAKDOWN ===")
        print(f"Total words: {len(total_words)}")
        print(f"Active words: {len(active_words)}")
        print(f"Inactive words: {len(inactive_words)}")
        print(f"NEW words (all): {len(new_words)}")
        print(f"Active non-learned words: {len(active_non_learned)}")

        # The test
        has_non_learned = content_planner.has_non_learned_words(
            test_user.id, ContentType.EXAMPLE
        )

        print(f"has_non_learned_words result: {has_non_learned}")
        print(f"Expected: False (only inactive words are NEW)")
        print(f"If True: PROBLEM DETECTED - Inactive words are being counted!\n")

        assert has_non_learned is False, (
            f"PROBLEM: has_non_learned_words={has_non_learned} but should be False. "
            f"Breakdown: {len(active_non_learned)} active non-learned, "
            f"{len(inactive_words)} inactive words, {len(new_words)} NEW total. "
            f"Inactive NEW words are being counted as 'available'!"
        )
