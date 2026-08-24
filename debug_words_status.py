#!/usr/bin/env python3
"""Debug script para verificar el estado de las palabras en BD"""

from sqlmodel import Session, select
from db import engine
from models import Word, WordStatistics, LearningState, ContentType, Example, ExampleWord

with Session(engine) as db:
    # Obtener todas las palabras activas del usuario 2
    words = db.exec(
        select(Word).where(Word.user_id == 2, Word.is_active == True)
    ).all()

    print(f"\n=== TOTAL DE PALABRAS ACTIVAS: {len(words)} ===\n")

    for word in words[:20]:  # Mostrar solo las primeras 20
        print(f"\nWord ID {word.id}: '{word.main}'")

        # Obtener estadísticas
        stats = db.exec(
            select(WordStatistics).where(
                WordStatistics.word_id == word.id,
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).first()

        if stats:
            print(f"  EXAMPLE stats: {stats.learning_state} (times_seen={stats.times_seen})")
        else:
            print(f"  EXAMPLE stats: NO STATISTICS")

        # Contar ejemplos asociados
        example_count = db.exec(
            select(Example).join(ExampleWord).where(
                ExampleWord.word_id == word.id,
                Example.type == "explore"
            )
        ).all()

        print(f"  EXPLORE examples associated: {len(example_count)}")
        for ex in example_count[:3]:
            print(f"    - Example {ex.id}: enqueued={ex.enqueued}")

    print("\n=== RESUMEN DE LEARNING STATES ===")
    all_stats = db.exec(
        select(WordStatistics).where(
            WordStatistics.type == ContentType.EXAMPLE
        )
    ).all()

    state_counts = {}
    for stat in all_stats:
        state = stat.learning_state
        state_counts[state] = state_counts.get(state, 0) + 1

    for state, count in sorted(state_counts.items()):
        print(f"  {state}: {count}")

    print("\n=== CONTENT QUEUE PENDING ===")
    from models import ContentQueue
    pending = db.exec(
        select(ContentQueue).where(
            ContentQueue.user_id == 2,
            ContentQueue.type == ContentType.EXAMPLE,
            ContentQueue.status == "pending"
        )
    ).all()

    print(f"Total pending items: {len(pending)}")
    for item in pending[:10]:
        ex = db.get(Example, item.content_id)
        if ex:
            word_ids = db.exec(
                select(ExampleWord.word_id).where(
                    ExampleWord.example_id == ex.id
                )
            ).all()
            print(f"  Queue Item {item.id}: Example {ex.id}, words: {word_ids}")
