#!/usr/bin/env python
"""
Test para verificar que get_prioritized_content() encuentra los items de BEST_OPTIONS
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import Session, create_engine, select
from sqlmodel import SQLModel
from auth.models import User
from features.words.models import Word, WordStatistics
from features.examples.models import Example
from features.best_options.models import BestOption
from core.learning_path.models import LearningPath, LearningPathQueue, LearningPathCursor
from core.enums import ContentType
from core.learning_path.enums import LearningState, LearningPathQueueStatus
from core.learning_path.services import LearningPathService
import json

# Crear BD de test
sqlite_url = "sqlite:///:memory:"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)


def create_test_data():
    """Crea datos de test en la BD"""
    db = Session(engine)

    # Crear usuario
    user = User(email="test@example.com", hashed_password="hashed")
    db.add(user)
    db.commit()
    db.refresh(user)

    user_id = user.id

    # Cargar datos
    data_file = Path(__file__).parent / "backend" / "data" / "new_user_data.json"
    with open(data_file, 'r', encoding='utf-8') as f:
        user_data_list = json.load(f)

    # Crear las 3 primeras palabras
    for word_idx, word_data in enumerate(user_data_list[:3]):
        word = Word(
            main=word_data.get("word", {}).get("main"),
            meaning=word_data.get("word", {}).get("meaning"),
            synonyms=word_data.get("word", {}).get("synonyms"),
            type=word_data.get("word", {}).get("type"),
            frequency=word_data.get("word", {}).get("frequency"),
            level=word_data.get("word", {}).get("level", 1),
            context=word_data.get("word", {}).get("context"),
            user_id=user_id
        )
        db.add(word)
        db.flush()

        word_id = word.id

        # Crear WordStatistics
        for ct in [ContentType.EXAMPLE, ContentType.BEST_OPTIONS]:
            ws = WordStatistics(
                word_id=word_id,
                type=ct,
                learning_state=LearningState.NEW,
                times_seen=0,
                current_cycle_seen=0
            )
            db.add(ws)
        db.flush()

        # Crear LearningPath entries
        for ct in [ContentType.EXAMPLE, ContentType.BEST_OPTIONS]:
            lp = LearningPath(
                type=ct,
                word_id=word_id,
                user_id=user_id,
                segment=1,
                position=word_idx,
            )
            db.add(lp)
        db.flush()

        # Crear Examples + LearningPathQueue
        for idx, example_data in enumerate(word_data.get("examples", [])):
            example_text = example_data.get("text", "")
            text_form = example_data.get("text_form", "")

            example = Example(
                type="INITIAL" if idx < 3 else "EXPLORE",
                text=example_text,
                text_form=text_form,
                word_id=word_id
            )
            db.add(example)
            db.flush()

            queue_item = LearningPathQueue(
                content_id=example.id,
                content_type=ContentType.EXAMPLE,
                word_id=word_id,
                user_id=user_id,
                status=LearningPathQueueStatus.PENDING,
            )
            db.add(queue_item)
            db.flush()

        # Crear BestOptions + LearningPathQueue
        for idx, bo_data in enumerate(word_data.get("best_options", []), start=1):
            options_list = bo_data.get("options", [])
            options_str = ";".join(options_list) if isinstance(options_list, list) else options_list

            best_option = BestOption(
                word_id=word_id,
                question=bo_data.get("question", f"Question {idx}"),
                options=options_str,
                correct_option=bo_data.get("correct_option", 0),
                sequence=idx,
                enqueued=False,
            )
            db.add(best_option)
            db.flush()

            queue_item = LearningPathQueue(
                content_id=best_option.id,
                content_type=ContentType.BEST_OPTIONS,
                word_id=word_id,
                user_id=user_id,
                status=LearningPathQueueStatus.PENDING,
            )
            db.add(queue_item)
            db.flush()

    db.commit()
    db.close()

    return user_id


def test_get_prioritized_content_examples():
    """Test que get_prioritized_content() encuentra items de EXAMPLE"""
    user_id = create_test_data()
    db = Session(engine)

    service = LearningPathService(db)

    item = service.get_prioritized_content(user_id, ContentType.EXAMPLE)

    assert item is not None, "get_prioritized_content() returned None for EXAMPLE"
    print(f"[OK] get_prioritized_content(EXAMPLE) found item: word_id={item.word_id}, content_id={item.content_id}")

    db.close()


def test_get_prioritized_content_best_options():
    """Test que get_prioritized_content() encuentra items de BEST_OPTIONS"""
    user_id = create_test_data()
    db = Session(engine)

    service = LearningPathService(db)

    item = service.get_prioritized_content(user_id, ContentType.BEST_OPTIONS)

    assert item is not None, "get_prioritized_content() returned None for BEST_OPTIONS"
    print(f"[OK] get_prioritized_content(BEST_OPTIONS) found item: word_id={item.word_id}, content_id={item.content_id}")

    db.close()


def test_learning_path_queue_count():
    """Verificar que los items están en la BD"""
    user_id = create_test_data()
    db = Session(engine)

    example_items = db.exec(
        select(LearningPathQueue).where(
            LearningPathQueue.content_type == ContentType.EXAMPLE,
            LearningPathQueue.user_id == user_id
        )
    ).all()

    bo_items = db.exec(
        select(LearningPathQueue).where(
            LearningPathQueue.content_type == ContentType.BEST_OPTIONS,
            LearningPathQueue.user_id == user_id
        )
    ).all()

    print(f"[OK] EXAMPLE items in DB: {len(example_items)}")
    print(f"[OK] BEST_OPTIONS items in DB: {len(bo_items)}")

    assert len(example_items) == 30, f"Expected 30 EXAMPLE items (3*10), got {len(example_items)}"
    assert len(bo_items) == 30, f"Expected 30 BEST_OPTIONS items (3*10), got {len(bo_items)}"

    db.close()


if __name__ == "__main__":
    try:
        print("=" * 80)
        print("TEST 1: LearningPathQueue Item Count")
        print("=" * 80)
        test_learning_path_queue_count()
        print()

        print("=" * 80)
        print("TEST 2: get_prioritized_content() for EXAMPLE")
        print("=" * 80)
        test_get_prioritized_content_examples()
        print()

        print("=" * 80)
        print("TEST 3: get_prioritized_content() for BEST_OPTIONS")
        print("=" * 80)
        test_get_prioritized_content_best_options()
        print()

        print("=" * 80)
        print("[OK] ALL TESTS PASSED!")
        print("=" * 80)
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
