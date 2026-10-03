import json
from sqlmodel import Session, select
from logging_client import logger
from datetime import datetime, timezone
from core.explore.models import ExploreSession


class ExploreRepository:
    """Gestiona la sesión de explore del usuario"""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_session(self, user_id: int) -> ExploreSession:
        """
        Obtiene la sesión actual del usuario o crea una nueva si no existe.
        """
        session = self.db.exec(
            select(ExploreSession).where(ExploreSession.user_id == user_id)
        ).first()

        if not session:
            logger.info(f"[ExploreRepository] Creating new session for user {user_id}")
            session = ExploreSession(user_id=user_id)
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

        return session

    def get_buffer_delivery_ids(self, user_id: int) -> list[int]:
        """Obtiene los IDs del delivery buffer actual"""
        session = self.get_or_create_session(user_id)
        try:
            return json.loads(session.buffer_delivery_ids)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_visited_delivery_ids(self, user_id: int) -> list[int]:
        """Obtiene los IDs de delivery buffer items visitados en esta sesión"""
        session = self.get_or_create_session(user_id)
        try:
            return json.loads(session.visited_delivery_ids)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_resolved_delivery_ids(self, user_id: int) -> list[int]:
        """Obtiene los IDs de delivery buffer items resueltos en esta sesión"""
        session = self.get_or_create_session(user_id)
        try:
            return json.loads(session.resolved_delivery_ids)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_buffer_position(self, user_id: int) -> int:
        """Obtiene la posición actual en el buffer"""
        session = self.get_or_create_session(user_id)
        return session.buffer_position

    def update_session(
        self,
        user_id: int,
        buffer_delivery_ids: list[int],
        buffer_position: int,
    ):
        """Actualiza la sesión con el nuevo delivery buffer y posición"""
        session = self.get_or_create_session(user_id)
        session.buffer_delivery_ids = json.dumps(buffer_delivery_ids)
        session.buffer_position = buffer_position
        session.updated_at = datetime.now(timezone.utc)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.debug(
            f"[ExploreRepository] Updated session for user {user_id}: "
            f"delivery_ids={buffer_delivery_ids}, position={buffer_position}"
        )

    def mark_delivery_item_as_resolved(self, user_id: int, delivery_id: int):
        """Marca un delivery item como resuelto en esta sesión"""
        session = self.get_or_create_session(user_id)
        resolved_ids = self.get_resolved_delivery_ids(user_id)

        if delivery_id not in resolved_ids:
            resolved_ids.append(delivery_id)
            session.resolved_delivery_ids = json.dumps(resolved_ids)
            session.updated_at = datetime.now(timezone.utc)
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            logger.debug(
                f"[ExploreRepository] Marked delivery item {delivery_id} as resolved for user {user_id}. "
                f"Total resolved: {len(resolved_ids)}"
            )

    def is_delivery_item_resolved(self, user_id: int, delivery_id: int) -> bool:
        """Chequea si un delivery item ya fue resuelto en esta sesión"""
        resolved_ids = self.get_resolved_delivery_ids(user_id)
        return delivery_id in resolved_ids

    def mark_delivery_item_as_visited(self, user_id: int, delivery_id: int):
        """Marca un delivery item como visitado en esta sesión"""
        session = self.get_or_create_session(user_id)
        visited_ids = self.get_visited_delivery_ids(user_id)

        if delivery_id not in visited_ids:
            visited_ids.append(delivery_id)
            session.visited_delivery_ids = json.dumps(visited_ids)
            session.updated_at = datetime.now(timezone.utc)
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            logger.debug(
                f"[ExploreRepository] Marked delivery item {delivery_id} as visited for user {user_id}. "
                f"Total visited: {len(visited_ids)}"
            )

    def is_delivery_item_visited(self, user_id: int, delivery_id: int) -> bool:
        """Chequea si un delivery item ya fue visitado en esta sesión"""
        visited_ids = self.get_visited_delivery_ids(user_id)
        return delivery_id in visited_ids

    def reset_session(self, user_id: int):
        """Resetea la sesión del usuario (limpia delivery buffer, visitados y resueltos)"""
        session = self.get_or_create_session(user_id)
        session.buffer_delivery_ids = "[]"
        session.buffer_position = 0
        session.visited_delivery_ids = "[]"
        session.resolved_delivery_ids = "[]"
        session.updated_at = datetime.now(timezone.utc)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"[ExploreRepository] Reset session for user {user_id}")
