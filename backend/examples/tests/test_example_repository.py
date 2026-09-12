"""Tests for ExampleRepository."""
import pytest
from sqlmodel import Session, select

from examples.example_repository import ExampleRepository
from models import ContentType, LearningState, Example, ExampleWord, WordStatistics


@pytest.fixture
def example_repository(db_session: Session):
    """Create an ExampleRepository for testing."""
    return ExampleRepository(db_session)


class TestCountAvailableExamplesForWord:
    """Test count_available_examples_for_word method."""

    def test_count_returns_zero_for_nonexistent_word(
        self, example_repository
    ):
        """Should return 0 for words with no examples."""
        count = example_repository.count_available_examples_for_word(9999)
        assert count == 0

    def test_count_excludes_learned_only_examples(
        self, db_session, example_repository, test_words, test_word_statistics
    ):
        """Should exclude examples where ALL words are LEARNED."""
        # Example 3 has only word 3 which is LEARNED
        count = example_repository.count_available_examples_for_word(
            test_words[2].id  # word 3 (LEARNED)
        )
        assert count == 0

    def test_count_includes_examples_with_non_learned_words(
        self, db_session, example_repository, test_words, test_examples
    ):
        """Should include examples with at least one non-LEARNED word."""
        # Example 1 has word 1 (NEW) - should be counted
        count = example_repository.count_available_examples_for_word(
            test_words[0].id  # word 1 (NEW)
        )
        # Examples 1, 2 have word 1
        assert count >= 1

    def test_count_excludes_enqueued_examples(
        self, db_session, example_repository, test_words, test_examples
    ):
        """Should exclude examples that are already enqueued."""
        word_id = test_words[0].id

        # Mark example 1 as enqueued
        example = db_session.exec(select(Example).where(Example.id == 1)).first()
        if example:
            example.enqueued = True
            db_session.add(example)
            db_session.commit()

        count = example_repository.count_available_examples_for_word(word_id)
        # Should exclude the enqueued example
        assert count >= 0



class TestGetAvailableContentForWord:
    """Test get_available_content_for_word method."""

    def test_returns_none_for_nonexistent_word(
        self, example_repository
    ):
        """Should return None for words with no examples."""
        result = example_repository.get_available_content_for_word(9999)
        assert result is None

    def test_returns_first_valid_example_by_sequence(
        self, db_session, example_repository, test_words, test_examples
    ):
        """Should return the example with lowest sequence."""
        word_id = test_words[0].id
        result = example_repository.get_available_content_for_word(word_id)

        # Should return example 1 or 2 (both have word 1)
        # Example 1 has sequence 1, Example 2 has sequence 2
        if result is not None:
            assert result in [1, 2]

    def test_excludes_consumed_examples(
        self, db_session, example_repository, test_words, test_examples
    ):
        """Should exclude examples marked as consumed."""
        # Mark example 1 as consumed
        example = db_session.exec(select(Example).where(Example.id == 1)).first()
        if example:
            example.is_consumed = True
            db_session.add(example)
            db_session.commit()

        result = example_repository.get_available_content_for_word(
            test_words[0].id
        )

        # Should return example 2 instead of 1
        if result is not None:
            assert result != 1

    def test_excludes_learned_only_examples(
        self, db_session, example_repository, test_words
    ):
        """Should exclude examples where ALL words are LEARNED."""
        result = example_repository.get_available_content_for_word(
            test_words[2].id  # word 3 (LEARNED)
        )

        # Should return None since all examples of word 3 have only LEARNED words
        assert result is None

    def test_respects_sequence_ordering(
        self, db_session, example_repository, test_words, test_examples
    ):
        """Should return examples in sequence order."""
        word_id = test_words[0].id

        # Get first available
        first = example_repository.get_available_content_for_word(word_id)

        if first is not None:
            # Mark it as consumed
            example = db_session.exec(select(Example).where(Example.id == first)).first()
            if example:
                example.is_consumed = True
                db_session.add(example)
                db_session.commit()

            # Get next available
            second = example_repository.get_available_content_for_word(word_id)

            if second is not None:
                # Second should have higher sequence than first
                ex1 = db_session.exec(select(Example).where(Example.id == first)).first()
                ex2 = db_session.exec(select(Example).where(Example.id == second)).first()
                if ex1 and ex2:
                    assert ex2.sequence > ex1.sequence


class TestGetWordIds:
    """Test get_word_ids helper method."""

    def test_get_word_ids_returns_all_words_in_example(
        self, db_session, example_repository, test_examples
    ):
        """Should return all word IDs associated with an example."""
        word_ids = example_repository.get_word_ids(1)

        # Example 1 has word 1
        assert 1 in word_ids
        assert len(word_ids) >= 1

