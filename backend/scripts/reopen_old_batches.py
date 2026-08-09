#!/usr/bin/env python3
"""
Script para reapertura gradual de batches antiguos (Memoria espaciada)
Ejecutar manualmente o configurar en cron: 0 2 * * * python /app/scripts/reopen_old_batches.py
"""

import sys
from pathlib import Path

# Agregar el backend al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from db import engine
from models import User, Batch, BatchStatus, BatchFeatured, ContentType, BatchFeaturedStatus, Word, WordStatistics
from logging_client import logger

def reopen_batches_spaced_repetition():
    """
    Reabre gradualmente batches completados antiguos para memoria espaciada.
    - Reabre 1 batch completado por usuario por día
    - Marca las palabras como is_learned=False
    """
    logger.info("[Spaced Repetition] Starting reopening of old batches...")

    with Session(engine) as db:
        try:
            # Obtener todos los usuarios activos
            users = db.exec(select(User).where(User.is_active == True)).all()
            logger.info(f"[Spaced Repetition] Processing {len(users)} users...")

            total_reopened = 0

            for user in users:
                # Obtener batches con BatchFeatured COMPLETED para SPACED_REPETITION, ordenados por antigüedad
                completed_batches = db.exec(
                    select(Batch)
                    .join(BatchFeatured, BatchFeatured.batch_id == Batch.id)
                    .where(
                        Batch.user_id == user.id,
                        BatchFeatured.status == BatchFeaturedStatus.MASTERED
                    )
                    .order_by(BatchFeatured.completed_at.asc())
                ).unique().all()

                if not completed_batches:
                    continue

                # Reabre solo el batch más antiguo (1 por usuario por día)
                batch_to_reopen = completed_batches[0]

                try:
                    # Marcar todas las palabras del batch como is_learned=False
                    words = db.exec(
                        select(Word).where(Word.batch_id == batch_to_reopen.id)
                    ).all()

                    for word in words:
                        db.add(word)

                        # Resetear estadísticas para todos los tipos
                        all_stats = db.exec(
                            select(WordStatistics).where(WordStatistics.word_id == word.id)
                        ).all()

                        for stats in all_stats:
                            stats.current_cycle_seen = 0
                            stats.is_learned = False
                            db.add(stats)

                    # Cambiar estado del BatchFeatured a ACTIVE (para revisión)
                    featured = db.exec(
                        select(BatchFeatured).where(
                            BatchFeatured.batch_id == batch_to_reopen.id,
                            BatchFeatured.type == ContentType.SPACED_REPETITION
                        )
                    ).first()

                    if featured:
                        featured.status = BatchFeaturedStatus.ACTIVE
                        featured.completed_at = None
                        db.add(featured)

                    db.commit()

                    logger.info(f"✓ User {user.email}: Batch #{batch_to_reopen.id} '{batch_to_reopen.title}' reopened ({len(words)} words)")
                    total_reopened += 1

                except Exception as e:
                    logger.error(f"✗ Error reopening batch {batch_to_reopen.id} for user {user.id}: {str(e)}")
                    db.rollback()
                    continue

            logger.info(f"[Spaced Repetition] Completed. {total_reopened} batches reopened.")
            print(f"\n✓ Proceso completado exitosamente")
            print(f"  Batches reabiertos: {total_reopened}")
            return 0

        except Exception as e:
            logger.error(f"[Spaced Repetition] Critical error: {str(e)}", exc_info=True)
            print(f"\n✗ Error en el proceso: {str(e)}")
            return 1

if __name__ == "__main__":
    exit_code = reopen_batches_spaced_repetition()
    sys.exit(exit_code)
