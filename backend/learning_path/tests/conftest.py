"""Pytest configuration and fixtures for learning_path tests."""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone

from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

# Add parent directories to path for imports
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from models import (
    User, Word, Example, ExampleWord, WordStatistics,
    ContentType, LearningState, ExampleType, LearningPath, LearningPathCursor
)
from examples.example_repository import ExampleRepository
from best_options.best_options_repository import BestOptionRepository
from words.word_repository import WordRepository
from learning_path.content_queue import ContentQueue


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
def db_session(db_engine) -> Session:
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
def test_words(db_session: Session, test_user: User) -> list[Word]:
    """Create 10 test words with different learning states."""
    words = []
    for i in range(1, 11):
        word = Word(
            id=i,
            main=f"word{i}",
            type="noun",
            meaning=f"meaning {i}",
            level=1,
            user_id=test_user.id,
            is_active=True,
            is_boosted=False,
            batch_id=None,
        )
        words.append(word)
        db_session.add(word)
    db_session.commit()
    return words


@pytest.fixture
def test_word_statistics(db_session: Session, test_words: list[Word]):
    """Create word statistics with different learning states."""
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
def test_examples(db_session: Session, test_words: list[Word]) -> list[Example]:
    """Create test examples."""
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
    example_words = []
    for i in range(1, 16):
        word_idx = ((i - 1) % 10) + 1  # Cycle through words 1-10
        ew = ExampleWord(
            example_id=i,
            word_id=word_idx,
            text_form=f"word{word_idx}",
        )
        example_words.append(ew)
        db_session.add(ew)

    db_session.commit()
    return examples


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


@pytest.fixture
def test_learning_path(db_session: Session, test_user: User, test_words: list[Word]):
    """Create test learning path with initial cursor and 10 path items."""
    cursor = LearningPathCursor(
        user_id=test_user.id,
        type=ContentType.EXAMPLE,
        current_segment=0,
        current_position=0,
    )
    db_session.add(cursor)
    db_session.commit()

    # Add 10 path items (one for each test word)
    for i in range(1, 11):
        path_item = LearningPath(
            user_id=test_user.id,
            word_id=test_words[i-1].id,
            type=ContentType.EXAMPLE,
            segment=0,
            position=i-1,
        )
        db_session.add(path_item)
    db_session.commit()

    return cursor


@pytest.fixture
def word_repository(db_session: Session):
    """Create a WordRepository for testing."""
    return WordRepository(db_session)


@pytest.fixture
def example_repository(db_session: Session):
    """Create an ExampleRepository for testing."""
    return ExampleRepository(db_session)


@pytest.fixture
def best_option_repository(db_session: Session):
    """Create a BestOptionRepository for testing."""
    return BestOptionRepository(db_session)


@pytest.fixture
def content_queue_repo(db_session: Session):
    """Create a ContentQueue for testing."""
    return ContentQueue(db_session)


@pytest.fixture
def priority_engine():
    """Create a PriorityEngine for testing."""
    from learning_path.priority_engine import PriorityEngine
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
    from learning_path.content_planner import ContentPlanner
    return ContentPlanner(
        session=db_session,
        priority_engine=priority_engine,
        content_queue=content_queue_repo,
        word_repository=word_repository,
        example_repository=example_repository,
        best_option_repository=best_option_repository,
    )
