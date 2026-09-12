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
def current_user(db_session: Session) -> User:
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
def test_words(db_session: Session, current_user: User) -> list[Word]:
    """Create test words."""
    words = [
        Word(
            id=1,
            main="hello",
            type="noun",
            meaning="greeting",
            level=1,
            user_id=current_user.id,
            is_boosted=False,
            batch_id=None,
        ),
        Word(
            id=2,
            main="world",
            type="noun",
            meaning="earth",
            level=1,
            user_id=current_user.id,
            is_boosted=False,
            batch_id=None,
        ),
        Word(
            id=3,
            main="learned",
            type="noun",
            meaning="already learned",
            level=1,
            user_id=current_user.id,
            is_boosted=False,
            batch_id=None,
        ),
    ]
    for word in words:
        db_session.add(word)
    db_session.commit()
    return words


@pytest.fixture
def test_examples(db_session: Session, test_words: list[Word]) -> list[Example]:
    """Create test examples."""
    examples = [
        Example(
            type=ExampleType.EXPLORE,
            text="Hello world",
            is_favorite=False,
            is_marked=False,
        ),
        Example(
            type=ExampleType.EXPLORE,
            text="Hello there",
            is_favorite=False,
            is_marked=False,
        ),
        Example(
            type=ExampleType.EXPLORE,
            text="Learning is great",
            is_favorite=False,
            is_marked=False,
        ),
    ]
    for example in examples:
        db_session.add(example)
    db_session.commit()

    # Link words to examples
    example_words = [
        ExampleWord(example_id=1, word_id=1, text_form="Hello"),
        ExampleWord(example_id=2, word_id=1, text_form="Hello"),
        ExampleWord(example_id=3, word_id=3, text_form="Learning"),
    ]
    for ew in example_words:
        db_session.add(ew)
    db_session.commit()

    return examples


@pytest.fixture
def test_word_statistics(db_session: Session, current_user: User, test_words: list[Word]):
    """Create test word statistics."""
    stats = [
        WordStatistics(
            word_id=test_words[0].id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.NEW,
            times_seen=0,
            current_cycle_seen=0,
        ),
        WordStatistics(
            word_id=test_words[1].id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.LEARNING,
            times_seen=1,
            current_cycle_seen=1,
        ),
        WordStatistics(
            word_id=test_words[2].id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.LEARNED,
            times_seen=6,
            current_cycle_seen=1,
        ),
    ]
    for stat in stats:
        db_session.add(stat)
    db_session.commit()
    return stats


@pytest.fixture
def test_content_queue(db_session: Session, current_user: User, test_examples: list[Example]):
    """Create test content queue items."""
    queue_items = [
        ContentQueue(
            user_id=current_user.id,
            type=ContentType.EXAMPLE,
            content_id=test_examples[0].id,
            status="pending",
        ),
        ContentQueue(
            user_id=current_user.id,
            type=ContentType.EXAMPLE,
            content_id=test_examples[1].id,
            status="pending",
        ),
        ContentQueue(
            user_id=current_user.id,
            type=ContentType.EXAMPLE,
            content_id=test_examples[2].id,
            status="pending",
        ),
    ]
    for item in queue_items:
        db_session.add(item)
    db_session.commit()
    for item in queue_items:
        db_session.refresh(item)
    return queue_items
