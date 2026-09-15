"""
Script para clonar un usuario completo

Copia todos los datos de un usuario a otro, incluyendo:
- Words y WordStatistics
- Examples
- BestOptions
- LearningPath, LearningPathHistory, LearningPathCursor
- ContentQueue
- QuickWrites
- Collocations
- UserExampleSession
- UserConfiguration

Uso:
    python manage.py clone-user <SOURCE_USER_ID> <TARGET_USER_ID>
"""
import traceback
from datetime import datetime, timezone
from sqlmodel import Session, select, delete
from models import (
    User, Word, WordStatistics, Example, ExampleWord, BestOption,
    LearningPath, LearningPathHistory, LearningPathCursor,
    ContentQueue, QuickWrite, Collocation, UserExampleSession,
    UserConfiguration
)
from logging_client import logger


def seed_clone_user(session: Session, source_user_id: int, target_user_id: int, clean: bool = False) -> None:
    """
    Clona todos los datos de un usuario a otro.

    Args:
        session: SQLModel session
        source_user_id: ID del usuario a clonar
        target_user_id: ID del usuario destino (requerido)
        clean: Si es True, limpia todos los datos del usuario destino primero
    """
    try:
        # Verificar que ambos usuarios existen
        source_user = session.exec(select(User).where(User.id == source_user_id)).first()
        if not source_user:
            logger.warning(f"[seed_clone_user] Usuario origen {source_user_id} no encontrado")
            return

        target_user = session.exec(select(User).where(User.id == target_user_id)).first()
        if not target_user:
            logger.warning(f"[seed_clone_user] Usuario destino {target_user_id} no encontrado")
            return

        logger.info(f"[seed_clone_user] Iniciando clonación de usuario {source_user_id} a {target_user_id}...")

        # Si clean=True, eliminar todos los datos del usuario destino primero
        if clean:
            logger.info(f"[seed_clone_user] Limpiando datos del usuario destino {target_user_id}...")
            # Eliminar en orden de dependencias (inverso al que los creamos)
            session.exec(delete(ContentQueue).where(ContentQueue.user_id == target_user_id))
            session.exec(delete(QuickWrite).where(QuickWrite.user_id == target_user_id))
            session.exec(delete(Collocation).where(Collocation.user_id == target_user_id))
            session.exec(delete(UserExampleSession).where(UserExampleSession.user_id == target_user_id))
            session.exec(delete(LearningPathCursor).where(LearningPathCursor.user_id == target_user_id))
            session.exec(delete(LearningPathHistory).where(LearningPathHistory.user_id == target_user_id))
            session.exec(delete(LearningPath).where(LearningPath.user_id == target_user_id))
            session.exec(delete(BestOption).where(BestOption.word_id.in_(
                select(Word.id).where(Word.user_id == target_user_id)
            )))
            # Eliminar ExampleWords de palabras del usuario
            session.exec(delete(ExampleWord).where(ExampleWord.word_id.in_(
                select(Word.id).where(Word.user_id == target_user_id)
            )))
            # Eliminar Examples que no tienen ExampleWords (huérfanos)
            session.exec(delete(Example).where(~Example.id.in_(
                select(ExampleWord.example_id)
            )))
            session.exec(delete(WordStatistics).where(
                WordStatistics.word_id.in_(
                    select(Word.id).where(Word.user_id == target_user_id)
                )
            ))
            session.exec(delete(Word).where(Word.user_id == target_user_id))
            session.exec(delete(UserConfiguration).where(UserConfiguration.user_id == target_user_id))
            session.commit()
            logger.info(f"[seed_clone_user] ✓ Datos del usuario {target_user_id} eliminados")

        # Mapeo de IDs old -> new para palabras clonadas
        words_mapping = {}

        # 1. Clonar Words
        source_words = session.exec(select(Word).where(Word.user_id == source_user_id)).all()
        logger.info(f"[seed_clone_user] Clonando {len(source_words)} palabra(s)...")

        for source_word in source_words:

            # Crear nueva palabra para el usuario destino
            new_word = Word(
                main=source_word.main,
                meaning=source_word.meaning,
                synonyms=source_word.synonyms,
                type=source_word.type,
                frequency=source_word.frequency,
                level=source_word.level,
                context=source_word.context,
                source_text=source_word.source_text,
                normalized=source_word.normalized,
                is_favorite=source_word.is_favorite,
                favorited_at=source_word.favorited_at,
                is_active=source_word.is_active,
                is_boosted=source_word.is_boosted,
                boosted_at=source_word.boosted_at,
                explanation=source_word.explanation,
                user_id=target_user_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(new_word)
            session.flush()
            words_mapping[source_word.id] = new_word.id

        logger.info(f"[seed_clone_user] ✓ {len(source_words)} palabra(s) clonada(s)")

        # 2. Clonar WordStatistics
        source_stats = session.exec(select(WordStatistics).join(Word).where(Word.user_id == source_user_id)).all()
        logger.info(f"[seed_clone_user] Clonando {len(source_stats)} estadística(s)...")

        for source_stat in source_stats:
            new_stat = WordStatistics(
                user_id=target_user_id,
                word_id=words_mapping.get(source_stat.word_id),
                type=source_stat.type,
                times_seen=source_stat.times_seen,
                current_cycle_seen=source_stat.current_cycle_seen,
                learning_state=source_stat.learning_state,
                learned_at=source_stat.learned_at,
                last_seen_at=source_stat.last_seen_at,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(new_stat)

        logger.info(f"[seed_clone_user] ✓ {len(source_stats)} estadística(s) clonada(s)")

        # 3. Clonar Examples y ExampleWords
        user_word_ids = {w.id for w in source_words}
        # Obtener ejemplos que están vinculados a palabras del usuario
        source_example_words = session.exec(
            select(ExampleWord).where(ExampleWord.word_id.in_(user_word_ids))
        ).all()
        source_example_ids = {ew.example_id for ew in source_example_words}
        source_examples = session.exec(
            select(Example).where(Example.id.in_(source_example_ids))
        ).all()

        examples_mapping = {}
        logger.info(f"[seed_clone_user] Clonando {len(source_examples)} ejemplo(s)...")

        for source_example in source_examples:
            new_example = Example(
                type=source_example.type,
                text=source_example.text,
                favorited_at=source_example.favorited_at,
                normalized=source_example.normalized,
                times_seen=source_example.times_seen,
                sequence=source_example.sequence,
                enqueued=source_example.enqueued,
                is_favorite=source_example.is_favorite,
                is_consumed=source_example.is_consumed,
                is_marked=source_example.is_marked,
                created_at=datetime.now(timezone.utc),
            )
            session.add(new_example)
            session.flush()
            examples_mapping[source_example.id] = new_example.id

        logger.info(f"[seed_clone_user] ✓ {len(source_examples)} ejemplo(s) clonado(s)")

        # Clonar ExampleWords (relación muchos-a-muchos)
        logger.info(f"[seed_clone_user] Clonando {len(source_example_words)} example_word(s)...")
        for source_ew in source_example_words:
            new_ew = ExampleWord(
                example_id=examples_mapping.get(source_ew.example_id),
                word_id=words_mapping.get(source_ew.word_id),
                text_form=source_ew.text_form,
            )
            session.add(new_ew)

        logger.info(f"[seed_clone_user] ✓ {len(source_example_words)} example_word(s) clonado(s)")

        # 4. Clonar BestOptions
        source_best_options = session.exec(select(BestOption)).all()
        # Filtrar solo best_options que tienen relación con palabras del usuario clonado
        source_best_options = [b for b in source_best_options if b.word_id in user_word_ids]
        logger.info(f"[seed_clone_user] Clonando {len(source_best_options)} best_option(s)...")

        for source_bo in source_best_options:
            new_bo = BestOption(
                word_id=words_mapping.get(source_bo.word_id),
                question=source_bo.question,
                options=source_bo.options,
                correct_option=source_bo.correct_option,
                normalized=source_bo.normalized,
                is_active=source_bo.is_active,
                sequence=source_bo.sequence,
                enqueued=source_bo.enqueued,
                is_consumed=source_bo.is_consumed,
                created_at=datetime.now(timezone.utc),
            )
            session.add(new_bo)

        logger.info(f"[seed_clone_user] ✓ {len(source_best_options)} best_option(s) clonado(s)")

        # 5. Clonar LearningPath
        source_learning_paths = session.exec(select(LearningPath).where(LearningPath.user_id == source_user_id)).all()
        logger.info(f"[seed_clone_user] Clonando {len(source_learning_paths)} learning_path(s)...")

        for source_lp in source_learning_paths:
            new_lp = LearningPath(
                type=source_lp.type,
                word_id=words_mapping.get(source_lp.word_id),
                user_id=target_user_id,
                segment=source_lp.segment,
                position=source_lp.position,
                created_at=datetime.now(timezone.utc),
            )
            session.add(new_lp)

        logger.info(f"[seed_clone_user] ✓ {len(source_learning_paths)} learning_path(s) clonado(s)")

        # 6. Clonar LearningPathHistory
        source_lph = session.exec(select(LearningPathHistory).where(LearningPathHistory.user_id == source_user_id)).all()
        logger.info(f"[seed_clone_user] Clonando {len(source_lph)} learning_path_history...")

        for source_history in source_lph:
            new_history = LearningPathHistory(
                type=source_history.type,
                word_id=words_mapping.get(source_history.word_id),
                user_id=target_user_id,
                segment=source_history.segment,
                position=source_history.position,
                created_at=datetime.now(timezone.utc),
            )
            session.add(new_history)

        logger.info(f"[seed_clone_user] ✓ {len(source_lph)} learning_path_history clonado(s)")

        # 7. Clonar LearningPathCursor
        source_cursors = session.exec(select(LearningPathCursor).where(LearningPathCursor.user_id == source_user_id)).all()
        logger.info(f"[seed_clone_user] Clonando {len(source_cursors)} learning_path_cursor(s)...")

        for source_cursor in source_cursors:
            new_cursor = LearningPathCursor(
                user_id=target_user_id,
                type=source_cursor.type,
                current_segment=source_cursor.current_segment,
                current_position=source_cursor.current_position,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(new_cursor)

        logger.info(f"[seed_clone_user] ✓ {len(source_cursors)} learning_path_cursor(s) clonado(s)")

        # 8. Clonar ContentQueue
        source_cq = session.exec(select(ContentQueue).where(ContentQueue.user_id == source_user_id)).all()
        logger.info(f"[seed_clone_user] Clonando {len(source_cq)} content_queue item(s)...")

        for source_item in source_cq:
            new_item = ContentQueue(
                content_id=source_item.content_id,
                type=source_item.type,
                status=source_item.status,
                user_id=target_user_id,
                priority=source_item.priority,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(new_item)

        logger.info(f"[seed_clone_user] ✓ {len(source_cq)} content_queue item(s) clonado(s)")

        # 9. Clonar QuickWrites
        source_qw = session.exec(select(QuickWrite).where(QuickWrite.user_id == source_user_id)).all()
        logger.info(f"[seed_clone_user] Clonando {len(source_qw)} quick_write(s)...")

        for source_qw_item in source_qw:
            new_qw = QuickWrite(
                user_id=target_user_id,
                prompt=source_qw_item.prompt,
                emoji=source_qw_item.emoji,
                words=source_qw_item.words,
                original_content=source_qw_item.original_content,
                corrected_content=source_qw_item.corrected_content,
                has_corrections=source_qw_item.has_corrections,
                is_favorite=source_qw_item.is_favorite,
                is_active=source_qw_item.is_active,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(new_qw)

        logger.info(f"[seed_clone_user] ✓ {len(source_qw)} quick_write(s) clonado(s)")

        # 10. Clonar Collocations
        source_collocations = session.exec(select(Collocation).where(Collocation.user_id == source_user_id)).all()
        logger.info(f"[seed_clone_user] Clonando {len(source_collocations)} collocation(s)...")

        for source_coll in source_collocations:
            new_coll = Collocation(
                user_id=target_user_id,
                word_id=source_coll.word_id and words_mapping.get(source_coll.word_id),
                phrase=source_coll.phrase,
                text_form=source_coll.text_form,
                is_marked=source_coll.is_marked,
                is_in_use=source_coll.is_in_use,
                in_use_at=source_coll.in_use_at,
                is_active=source_coll.is_active,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(new_coll)

        logger.info(f"[seed_clone_user] ✓ {len(source_collocations)} collocation(s) clonado(s)")

        # 11. Clonar UserExampleSession
        source_ues = session.exec(select(UserExampleSession).where(UserExampleSession.user_id == source_user_id)).all()
        logger.info(f"[seed_clone_user] Clonando {len(source_ues)} user_example_session(s)...")

        for source_ues_item in source_ues:
            new_ues = UserExampleSession(
                user_id=target_user_id,
                buffer_queue_item_ids=source_ues_item.buffer_queue_item_ids,
                buffer_position=source_ues_item.buffer_position,
                visited_queue_item_ids=source_ues_item.visited_queue_item_ids,
                resolved_queue_item_ids=source_ues_item.resolved_queue_item_ids,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(new_ues)

        logger.info(f"[seed_clone_user] ✓ {len(source_ues)} user_example_session(s) clonado(s)")

        # 12. Clonar UserConfiguration
        source_uc = session.exec(select(UserConfiguration).where(UserConfiguration.user_id == source_user_id)).first()
        if source_uc:
            logger.info("[seed_clone_user] Clonando user_configuration...")
            new_uc = UserConfiguration(
                user_id=target_user_id,
                max_words=source_uc.max_words,
                max_examples=source_uc.max_examples,
                max_best_options=source_uc.max_best_options,
                max_collocations=source_uc.max_collocations,
                max_quick_writes=source_uc.max_quick_writes,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(new_uc)
            logger.info("[seed_clone_user] ✓ user_configuration clonada")


        session.commit()
        logger.info(f"[seed_clone_user] ✅ Usuario {source_user_id} clonado exitosamente a {target_user_id}")

    except Exception as e:
        logger.error(f"[seed_clone_user] Error al clonar usuario: {e} - {traceback.format_exc()}")
        session.rollback()
        raise

if __name__ == "__main__":
    import sys
    from db import engine

    # Validar que se proporcionen ambos IDs
    if len(sys.argv) < 3:
        print("❌ Error: Se requieren dos argumentos (SOURCE_USER_ID y TARGET_USER_ID)")
        print("Uso: python seeds/seed_clone_user.py <SOURCE_USER_ID> <TARGET_USER_ID>")
        print("Ejemplo: python seeds/seed_clone_user.py 5 10")
        sys.exit(1)

    try:
        source_user_id = int(sys.argv[1])
        target_user_id = int(sys.argv[2])
    except ValueError:
        print("❌ Error: Los argumentos deben ser números válidos")
        sys.exit(1)

    with Session(engine) as session:
        seed_clone_user(session, source_user_id, target_user_id)
