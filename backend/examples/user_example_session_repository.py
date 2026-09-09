import json
from sqlmodel import Session, select
from models import UserExampleSession
from logging_client import logger
from datetime import datetime, timezone


class UserExampleSessionRepository:
    """Gestiona la sesión de ejemplos del usuario"""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_session(self, user_id: int) -> UserExampleSession:
        """
        Obtiene la sesión actual del usuario o crea una nueva si no existe.
        """
        session = self.db.exec(
            select(UserExampleSession).where(UserExampleSession.user_id == user_id)
        ).first()

        if not session:
            logger.info(f"[UserExampleSessionRepository] Creating new session for user {user_id}")
            session = UserExampleSession(user_id=user_id)
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

        return session

    def get_buffer_queue_item_ids(self, user_id: int) -> list[int]:
        """Obtiene los IDs del buffer actual"""
        session = self.get_or_create_session(user_id)
        try:
            return json.loads(session.buffer_queue_item_ids)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_visited_queue_item_ids(self, user_id: int) -> list[int]:
        """Obtiene los IDs de items visitados en esta sesión"""
        session = self.get_or_create_session(user_id)
        try:
            return json.loads(session.visited_queue_item_ids)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_resolved_queue_item_ids(self, user_id: int) -> list[int]:
        """Obtiene los IDs de items resueltos en esta sesión"""
        session = self.get_or_create_session(user_id)
        try:
            return json.loads(session.resolved_queue_item_ids)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_buffer_position(self, user_id: int) -> int:
        """Obtiene la posición actual en el buffer"""
        session = self.get_or_create_session(user_id)
        return session.buffer_position

    def update_session(
        self,
        user_id: int,
        buffer_queue_item_ids: list[int],
        buffer_position: int,
    ):
        """Actualiza la sesión con el nuevo buffer y posición"""
        session = self.get_or_create_session(user_id)
        session.buffer_queue_item_ids = json.dumps(buffer_queue_item_ids)
        session.buffer_position = buffer_position
        session.updated_at = datetime.now(timezone.utc)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.debug(
            f"[UserExampleSessionRepository] Updated session for user {user_id}: "
            f"buffer_ids={buffer_queue_item_ids}, position={buffer_position}"
        )

    def mark_queue_item_as_resolved(self, user_id: int, queue_item_id: int):
        """Marca un item como resuelto en esta sesión"""
        session = self.get_or_create_session(user_id)
        resolved_ids = self.get_resolved_queue_item_ids(user_id)

        if queue_item_id not in resolved_ids:
            resolved_ids.append(queue_item_id)
            session.resolved_queue_item_ids = json.dumps(resolved_ids)
            session.updated_at = datetime.now(timezone.utc)
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            logger.debug(
                f"[UserExampleSessionRepository] Marked item {queue_item_id} as resolved for user {user_id}. "
                f"Total resolved: {len(resolved_ids)}"
            )

    def is_queue_item_resolved(self, user_id: int, queue_item_id: int) -> bool:
        """Chequea si un item ya fue resuelto en esta sesión"""
        resolved_ids = self.get_resolved_queue_item_ids(user_id)
        return queue_item_id in resolved_ids

    def mark_queue_item_as_visited(self, user_id: int, queue_item_id: int):
        """Marca un item como visitado en esta sesión"""
        session = self.get_or_create_session(user_id)
        visited_ids = self.get_visited_queue_item_ids(user_id)

        if queue_item_id not in visited_ids:
            visited_ids.append(queue_item_id)
            session.visited_queue_item_ids = json.dumps(visited_ids)
            session.updated_at = datetime.now(timezone.utc)
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            logger.debug(
                f"[UserExampleSessionRepository] Marked item {queue_item_id} as visited for user {user_id}. "
                f"Total visited: {len(visited_ids)}"
            )

    def is_queue_item_visited(self, user_id: int, queue_item_id: int) -> bool:
        """Chequea si un item ya fue visitado en esta sesión"""
        visited_ids = self.get_visited_queue_item_ids(user_id)
        return queue_item_id in visited_ids

    def reset_session(self, user_id: int):
        """Resetea la sesión del usuario (limpia buffer, visitados y resueltos)"""
        session = self.get_or_create_session(user_id)
        session.buffer_queue_item_ids = "[]"
        session.buffer_position = 0
        session.visited_queue_item_ids = "[]"
        session.resolved_queue_item_ids = "[]"
        session.updated_at = datetime.now(timezone.utc)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"[UserExampleSessionRepository] Reset session for user {user_id}")
