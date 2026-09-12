"""Pytest configuration and fixtures for examples tests."""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone
from typing import Generator

from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

# Add parent directories to path for imports
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from models import User, Word, Example, ExampleWord, ContentQueue, WordStatistics, ContentType, LearningState, ExampleType


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    """Get a test database session."""
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def current_user(test_user: User) -> User:
    """Alias for test_user for backwards compatibility."""
    return test_user


@pytest.fixture
def test_words(db_session: Session, current_user: User) -> list[Word]:
    """Create test words with different learning states."""
    words = []
    for i in range(1, 11):
        word = Word(
            id=i,
            main=f"word{i}",
            type="noun",
            meaning=f"meaning {i}",
            level=1,
            user_id=current_user.id,
            is_active=True,
            is_boosted=False,
            batch_id=None,
        )
        words.append(word)
        db_session.add(word)
    db_session.commit()
    return words


@pytest.fixture
def test_examples(db_session: Session, test_words: list[Word]) -> list[Example]:
    """Create test examples with properties needed for tests."""
    examples = []
    for i in range(1, 16):
        example = Example(
            id=i,
            type=ExampleType.EXPLORE,
            text=f"Example text {i}",
            is_favorite=False,
            is_marked=False,
            enqueued=False,
            is_consumed=False,
            sequence=i,
        )
        examples.append(example)
        db_session.add(example)
    db_session.commit()

    # Link words to examples: each example has 1 word
    for i in range(1, 16):
        word_idx = ((i - 1) % 10) + 1  # Cycle through words 1-10
        ew = ExampleWord(
            example_id=i,
            word_id=word_idx,
            text_form=f"word{word_idx}",
        )
        db_session.add(ew)

    db_session.commit()
    return examples


@pytest.fixture
def test_word_statistics(db_session: Session, current_user: User, test_words: list[Word]):
    """Create test word statistics with different learning states."""
    stats = []

    # Words 1-2: NEW
    for i in range(1, 3):
        stat = WordStatistics(
            word_id=test_words[i-1].id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.NEW,
            times_seen=0,
            current_cycle_seen=0,
        )
        stats.append(stat)
        db_session.add(stat)

    # Words 3-4: LEARNING
    for i in range(3, 5):
        stat = WordStatistics(
            word_id=test_words[i-1].id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.LEARNING,
            times_seen=1,
            current_cycle_seen=1,
        )
        stats.append(stat)
        db_session.add(stat)

    # Words 5-10: LEARNED
    for i in range(5, 11):
        stat = WordStatistics(
            word_id=test_words[i-1].id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.LEARNED,
            times_seen=6,
            current_cycle_seen=1,
        )
        stats.append(stat)
        db_session.add(stat)

    db_session.commit()
    return stats


@pytest.fixture
def test_content_queue(db_session: Session, test_user: User, test_examples: list[Example]):
    """Create test content queue items."""
    queue_items = []
    for i in range(1, 4):
        item = ContentQueue(
            user_id=test_user.id,
            type=ContentType.EXAMPLE,
            content_id=test_examples[i-1].id,
            status="pending",
        )
        queue_items.append(item)
        db_session.add(item)
    db_session.commit()
    return queue_items
