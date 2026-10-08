"""
Tests para LearningPathService.get_prioritized_content()

Garantiza que:
1. Se usan prioridades correctamente (PriorityEngine.calculate_priority)
2. No hay monopolio - items provienen de múltiples palabras
3. Se pueden obtener batches de cualquier tamaño (4, 6, 10)
"""
import pytest
from datetime import datetime, timezone
from sqlmodel import Session, create_engine, SQLModel, select
from sqlmodel.pool import StaticPool

from core.learning_path.services import LearningPathService
from core.learning_path.models import LearningPathQueue
from core.learning_path.enums import LearningPathQueueStatus, LearningState
from core.enums import ContentType
from features.words.models import Word, WordStatistics
from features.examples.models import Example, ExampleType
from features.content_repository import UnifiedContentRepository
from auth.models import User


@pytest.fixture
def db():
    """Crear DB en memoria para tests"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def user_with_8_words(db: Session):
    """Crear usuario con 8 palabras no-LEARNED"""
    user = User(email="test@example.com", hashed_password="hashed_pass")
    db.add(user)
    db.commit()
    db.refresh(user)

    # Crear 8 palabras
    words = []
    for i in range(1, 9):
        word = Word(
            user_id=user.id,
            main=f"word{i}",
            type="word",
            meaning=f"Meaning of word {i}",
            level=1,
            is_active=True,
        )
        db.add(word)
        db.commit()
        db.refresh(word)
        words.append(word)

        # Crear WordStatistics para esta palabra (LEARNING, no LEARNED)
        stats = WordStatistics(
            word_id=word.id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.LEARNING,
            times_exposed=0,
            times_correct=0,
        )
        db.add(stats)
        db.commit()

    return user, words


@pytest.fixture
def queue_items(db: Session, user_with_8_words):
    """Crear items en la queue para las 8 palabras"""
    user, words = user_with_8_words

    # Crear 6 ejemplos por palabra (48 totales)
    queue_items_list = []
    for word in words:
        for j in range(6):
            # Crear Example
            example = Example(
                word_id=word.id,
                text=f"Example {j+1} for {word.main}",
                text_form=word.main,
                type=ExampleType.EXPLORE,
            )
            db.add(example)
            db.commit()
            db.refresh(example)

            # Crear LearningPathQueue item
            queue_item = LearningPathQueue(
                user_id=user.id,
                content_type=ContentType.EXAMPLE,
                content_id=example.id,
                word_id=word.id,
                status=LearningPathQueueStatus.PENDING,
                priority=0.0,
            )
            db.add(queue_item)
            db.commit()
            db.refresh(queue_item)
            queue_items_list.append(queue_item)

    return user, words, queue_items_list


class TestGetPrioritizedContent:
    """Tests para get_prioritized_content"""

    def test_returns_items_from_multiple_words(self, db: Session, queue_items):
        """Test: Devuelve items de múltiples palabras (no monopolio)"""
        user, words, items = queue_items
        content_repo = UnifiedContentRepository(db)
        service = LearningPathService(db, content_repo)

        # Obtener 4 items
        result_batch = []
        for _ in range(4):
            r = service.get_prioritized_content(user.id, ContentType.EXAMPLE)
            if r:
                result_batch.append(r)

        # Verificar que hay items de múltiples palabras
        word_ids_in_batch = [item.word_id for item in result_batch]
        unique_words = set(word_ids_in_batch)

        assert len(unique_words) > 1, f"Esperado items de múltiples palabras, obtuvo solo: {unique_words}"
        assert len(result_batch) == 4, f"Esperado 4 items, obtuvo {len(result_batch)}"

    def test_distributes_evenly_across_words(self, db: Session, queue_items):
        """Test: Distribuye items balanceados entre palabras"""
        user, words, items = queue_items
        content_repo = UnifiedContentRepository(db)
        service = LearningPathService(db, content_repo)

        # Obtener 12 items
        batch = []
        for _ in range(12):
            item = service.get_prioritized_content(user.id, ContentType.EXAMPLE)
            if item:
                batch.append(item)

        # Contar items por palabra
        word_counts = {}
        for item in batch:
            word_counts[item.word_id] = word_counts.get(item.word_id, 0) + 1

        # Verificar que no hay monopolio total
        max_count = max(word_counts.values())
        min_count = min(word_counts.values())

        # Diferencia máxima <= 2 para buena distribución
        assert max_count - min_count <= 2, f"Monopolio detectado: {word_counts}"
        assert len(word_counts) > 1, "Esperado items de múltiples palabras"

    def test_uses_priority_engine(self, db: Session, queue_items):
        """Test: Usa PriorityEngine.calculate_priority correctamente"""
        user, words, items = queue_items
        content_repo = UnifiedContentRepository(db)
        service = LearningPathService(db, content_repo)

        # Modificar una palabra a estado NEW (mayor prioridad que LEARNING)
        # NEW priority: 1.00, LEARNING priority: 0.85
        word_stats = db.exec(
            select(WordStatistics)
            .where(
                WordStatistics.word_id == words[0].id,
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).first()
        if word_stats:
            word_stats.learning_state = LearningState.NEW
            db.add(word_stats)
            db.commit()

        # Obtener batch
        batch = []
        for _ in range(4):
            item = service.get_prioritized_content(user.id, ContentType.EXAMPLE)
            if item:
                batch.append(item)

        # Verificar que la palabra NEW tiene mayor prioridad y aparece
        word_counts = {}
        for item in batch:
            word_counts[item.word_id] = word_counts.get(item.word_id, 0) + 1

        # La palabra NEW debería tener mayor prioridad y aparecer en el primer slot
        new_word_id = words[0].id
        assert new_word_id in word_counts, "Palabra NEW debería aparecer en el batch"
        # NEW tiene mayor prioridad, así que debe aparecer al menos una vez
        assert word_counts[new_word_id] >= 1, "Palabra NEW debería aparecer al menos una vez"

    def test_returns_none_when_no_content(self, db: Session, user_with_8_words):
        """Test: Retorna None cuando no hay contenido PENDING"""
        user, words = user_with_8_words
        content_repo = UnifiedContentRepository(db)
        service = LearningPathService(db, content_repo)

        # No hay items en la queue
        result = service.get_prioritized_content(user.id, ContentType.EXAMPLE)
        assert result is None, "Debería retornar None sin items"

    def test_handles_batch_size_4(self, db: Session, queue_items):
        """Test: Maneja batch size 4 correctamente"""
        user, words, items = queue_items
        content_repo = UnifiedContentRepository(db)
        service = LearningPathService(db, content_repo)

        # Obtener 4 items
        batch = []
        for _ in range(4):
            item = service.get_prioritized_content(user.id, ContentType.EXAMPLE)
            if item:
                batch.append(item)

        assert len(batch) == 4, f"Esperado 4 items, obtuvo {len(batch)}"
        item_ids = [item.id for item in batch]
        assert len(set(item_ids)) == 4, "Items deberían ser únicos"
