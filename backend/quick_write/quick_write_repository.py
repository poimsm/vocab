from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlmodel import Session, select, func
from models import QuickWrite
from logging_client import logger


class QuickWriteRepository:
    """Repository para gestión de quick write exercises"""

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        user_id: int,
        prompt: str,
        emoji: str = "✍️",
        words: Optional[List[str]] = None,
        original_content: Optional[str] = None,
        corrected_content: Optional[str] = None,
        has_corrections: bool = False
    ) -> QuickWrite:
        """Crea un nuevo ejercicio de escritura rápida"""
        note = QuickWrite(
            user_id=user_id,
            prompt=prompt,
            emoji=emoji,
            words=words,
            original_content=original_content,
            corrected_content=corrected_content,
            has_corrections=has_corrections,
            is_favorite=False
        )
        self.session.add(note)
        self.session.commit()
        self.session.refresh(note)
        return note

    def get(self, note_id: int, user_id: int) -> Optional[QuickWrite]:
        """Obtiene un ejercicio específico (verifica que pertenezca al usuario y esté activo)"""
        return self.session.exec(
            select(QuickWrite).where(
                QuickWrite.id == note_id,
                QuickWrite.user_id == user_id,
                QuickWrite.is_active == True
            )
        ).first()

    def get_all(self, user_id: int, sort: str = "newest") -> List[QuickWrite]:
        """Obtiene todos los ejercicios activos del usuario"""
        statement = select(QuickWrite).where(
            QuickWrite.user_id == user_id,
            QuickWrite.is_active == True
        )

        if sort == "newest":
            statement = statement.order_by(QuickWrite.created_at.desc())
        elif sort == "oldest":
            statement = statement.order_by(QuickWrite.created_at.asc())
        elif sort == "alphabetical":
            statement = statement.order_by(QuickWrite.original_content.asc())

        return self.session.exec(statement).all()

    def get_with_pagination(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 20,
        sort: str = "newest"
    ) -> Dict[str, Any]:
        """Obtiene ejercicios activos con paginación"""
        statement = select(QuickWrite).where(
            QuickWrite.user_id == user_id,
            QuickWrite.is_active == True
        )

        if sort == "newest":
            statement = statement.order_by(QuickWrite.created_at.desc())
        elif sort == "oldest":
            statement = statement.order_by(QuickWrite.created_at.asc())
        elif sort == "alphabetical":
            statement = statement.order_by(QuickWrite.original_content.asc())

        total = self.session.exec(
            select(func.count()).select_from(QuickWrite).where(
                QuickWrite.user_id == user_id,
                QuickWrite.is_active == True
            )
        ).one()

        offset = (page - 1) * limit
        statement = statement.offset(offset).limit(limit)
        items = self.session.exec(statement).all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    def update(self, note_id: int, user_id: int, data: Dict[str, Any]) -> Optional[QuickWrite]:
        """Actualiza un ejercicio"""
        note = self.get(note_id, user_id)
        if not note:
            return None

        for key, value in data.items():
            if key in ["original_content", "corrected_content", "has_corrections", "is_favorite"] and value is not None:
                setattr(note, key, value)

        note.updated_at = datetime.now(timezone.utc)
        self.session.add(note)
        self.session.commit()
        self.session.refresh(note)
        return note

    def toggle_favorite(self, note_id: int, user_id: int) -> Optional[QuickWrite]:
        """Activa/desactiva ejercicio como favorito"""
        note = self.get(note_id, user_id)
        if not note:
            return None

        note.is_favorite = not note.is_favorite
        note.updated_at = datetime.now(timezone.utc)
        self.session.add(note)
        self.session.commit()
        self.session.refresh(note)
        return note

    def delete(self, note_id: int, user_id: int) -> bool:
        """Desactiva un ejercicio (soft delete)"""
        note = self.get(note_id, user_id)
        if not note:
            return False

        note.is_active = False
        note.updated_at = datetime.now(timezone.utc)
        self.session.add(note)
        self.session.commit()
        return True

    def get_favorites(self, user_id: int) -> List[QuickWrite]:
        """Obtiene todos los ejercicios activos favoritos"""
        return self.session.exec(
            select(QuickWrite).where(
                QuickWrite.user_id == user_id,
                QuickWrite.is_favorite == True,
                QuickWrite.is_active == True
            ).order_by(QuickWrite.created_at.desc())
        ).all()

    def get_total_count(self, user_id: int) -> int:
        """Obtiene el total de ejercicios activos del usuario"""
        return self.session.exec(
            select(func.count()).select_from(QuickWrite).where(
                QuickWrite.user_id == user_id,
                QuickWrite.is_active == True
            )
        ).one()
