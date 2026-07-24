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
from models import User, Batch, BatchStatus, Word
from logging_config import logger

def reopen_batches_spaced_repetition():
    """
    Reabre gradualmente batches completados antiguos para memoria espaciada.
    - Reabre 1 batch completado por usuario por día
    - Marca las palabras como is_learned=False
    """
    logger.info("[Spaced Repetition] Iniciando reapertura de batches antiguos...")

    with Session(engine) as db:
        try:
            # Obtener todos los usuarios activos
            users = db.exec(select(User).where(User.is_active == True)).all()
            logger.info(f"[Spaced Repetition] Procesando {len(users)} usuarios...")

            total_reopened = 0

            for user in users:
                # Obtener batches COMPLETED del usuario, ordenados por antigüedad
                completed_batches = db.exec(
                    select(Batch)
                    .where(
                        Batch.user_id == user.id,
                        Batch.status == BatchStatus.COMPLETED
                    )
                    .order_by(Batch.completed_at.asc())
                ).all()

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
                        word.is_learned = False
                        word.current_cycle_seen = 0  # Resetear el ciclo
                        db.add(word)

                    # Cambiar estado del batch a OPEN
                    batch_to_reopen.status = BatchStatus.OPEN
                    batch_to_reopen.mastery_progress = 0.0
                    db.add(batch_to_reopen)

                    db.commit()

                    logger.info(f"✓ Usuario {user.email}: Batch #{batch_to_reopen.id} '{batch_to_reopen.title}' reabierto ({len(words)} palabras)")
                    total_reopened += 1

                except Exception as e:
                    logger.error(f"✗ Error reabriendo batch {batch_to_reopen.id} para usuario {user.id}: {str(e)}")
                    db.rollback()
                    continue

            logger.info(f"[Spaced Repetition] Completado. {total_reopened} batches reabiertos.")
            print(f"\n✓ Proceso completado exitosamente")
            print(f"  Batches reabiertos: {total_reopened}")
            return 0

        except Exception as e:
            logger.error(f"[Spaced Repetition] Error crítico: {str(e)}", exc_info=True)
            print(f"\n✗ Error en el proceso: {str(e)}")
            return 1

if __name__ == "__main__":
    exit_code = reopen_batches_spaced_repetition()
    sys.exit(exit_code)
