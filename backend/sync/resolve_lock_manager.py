"""
ResolveLockManager - Semáforo para coordinar entre resolve() y explore() endpoints.

Previene race conditions cuando:
- resolve() está actualizando un item a CONSUMED
- explore() intenta obtener items PENDING

El flujo es:
1. resolve() llama a acquire() - crea un lock
2. resolve() hace su trabajo (registra exposición, marca como CONSUMED)
3. resolve() llama a release() - elimina el lock
4. explore() llama a wait_for_locks() - espera a que se liberen todos los locks del usuario
5. Después del timeout, explore() procede igual si los locks no se liberan
"""

import time
from datetime import datetime, timezone
from sqlmodel import Session, select
from logging_client import logger
from models import ResolveLock


class ResolveLockManager:
    """Administra locks distribuidos para evitar race conditions en resolve/explore."""

    @staticmethod
    def acquire(session: Session, user_id: int, queue_item_id: int) -> ResolveLock:
        """
        Adquiere un lock para indicar que un resolve está en progreso.

        Args:
            session: SQLModel Session
            user_id: ID del usuario
            queue_item_id: ID del item de contenido siendo resuelto

        Returns:
            El ResolveLock creado
        """
        lock = ResolveLock(
            user_id=user_id,
            queue_item_id=queue_item_id,
            locked_at=datetime.now(timezone.utc),
        )
        session.add(lock)
        session.commit()
        session.refresh(lock)

        logger.debug(
            f"[ResolveLockManager] ACQUIRED lock for user_id={user_id}, "
            f"queue_item_id={queue_item_id}, lock_id={lock.id}"
        )

        return lock

    @staticmethod
    def release(session: Session, user_id: int, queue_item_id: int) -> bool:
        """
        Libera los locks para un item específico.

        Args:
            session: SQLModel Session
            user_id: ID del usuario
            queue_item_id: ID del item de contenido

        Returns:
            True si se eliminó al menos un lock, False si no había locks
        """
        locks = session.exec(
            select(ResolveLock).where(
                ResolveLock.user_id == user_id,
                ResolveLock.queue_item_id == queue_item_id,
            )
        ).all()

        if not locks:
            return False

        for lock in locks:
            session.delete(lock)

        session.commit()

        logger.debug(
            f"[ResolveLockManager] RELEASED {len(locks)} lock(s) for user_id={user_id}, "
            f"queue_item_id={queue_item_id}"
        )

        return True

    @staticmethod
    def count_locks(session: Session, user_id: int) -> int:
        """
        Cuenta cuántos locks activos hay para un usuario.

        Args:
            session: SQLModel Session
            user_id: ID del usuario

        Returns:
            Cantidad de locks activos
        """
        count = session.exec(
            select(ResolveLock).where(ResolveLock.user_id == user_id)
        ).all()

        return len(count)

    @staticmethod
    def wait_for_locks(
        session: Session,
        user_id: int,
        timeout_seconds: float = 2.0,
        check_interval: float = 0.05,
    ) -> bool:
        """
        Espera a que se liberen todos los locks de un usuario.

        Implementa un wait exponencial con timeout.
        Útil para que explore() espere a que resolve() termine.

        Args:
            session: SQLModel Session
            user_id: ID del usuario
            timeout_seconds: Cuántos segundos esperar máximo (default: 2)
            check_interval: Cuánto tiempo esperar entre checks (default: 50ms)

        Returns:
            True si los locks se liberaron antes del timeout
            False si se alcanzó el timeout y aún hay locks
        """
        start_time = time.time()
        elapsed = 0.0

        while elapsed < timeout_seconds:
            lock_count = ResolveLockManager.count_locks(session, user_id)

            if lock_count == 0:
                elapsed = time.time() - start_time
                logger.debug(
                    f"[ResolveLockManager] All locks released for user_id={user_id} "
                    f"after {elapsed:.2f}s"
                )
                return True

            # Esperar antes de hacer otro check
            time.sleep(check_interval)
            elapsed = time.time() - start_time

        # Timeout alcanzado
        lock_count = ResolveLockManager.count_locks(session, user_id)
        logger.warning(
            f"[ResolveLockManager] TIMEOUT for user_id={user_id}: "
            f"{lock_count} lock(s) still active after {timeout_seconds}s. "
            f"Proceeding anyway."
        )

        return False
