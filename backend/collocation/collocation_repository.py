from typing import List, Optional
from sqlmodel import Session, select
from models import Collocation


class CollocationRepository:
    """Repository para la gestión de collocations."""

    def __init__(self, session: Session):
        self.session = session

    def get_user_collocations(self, user_id: int) -> List[Collocation]:
        """Obtiene todas las collocations activas del usuario."""
        return self.session.exec(
            select(Collocation)
            .where(
                Collocation.user_id == user_id,
                Collocation.is_active == True
            )
            .order_by(Collocation.created_at.desc())
        ).all()

    def get_by_id(self, collocation_id: int, user_id: int) -> Optional[Collocation]:
        """Obtiene una colocación específica."""
        return self.session.exec(
            select(Collocation)
            .where(
                Collocation.id == collocation_id,
                Collocation.user_id == user_id
            )
        ).first()

    def create(
        self,
        user_id: int,
        phrase: str,
        word_id: Optional[int] = None
    ) -> Collocation:
        """Crea una nueva colocación."""
        collocation = Collocation(
            user_id=user_id,
            phrase=phrase,
            word_id=word_id,
            is_active=True
        )
        self.session.add(collocation)
        self.session.commit()
        self.session.refresh(collocation)
        return collocation

    def create_many(self, user_id: int, phrases: List[dict]) -> List[Collocation]:
        """Crea múltiples collocations desde un listado.

        Args:
            user_id: ID del usuario
            phrases: Lista de dicts con estructura {phrase, word_id (opcional)}
        """
        collocations = []
        for item in phrases:
            collocation = Collocation(
                user_id=user_id,
                phrase=item.get("phrase"),
                word_id=item.get("word_id"),
                is_active=True
            )
            self.session.add(collocation)
            collocations.append(collocation)

        self.session.commit()
        for c in collocations:
            self.session.refresh(c)

        return collocations

    def delete(self, collocation_id: int, user_id: int) -> bool:
        """Marca una colocación como inactiva (soft delete)."""
        collocation = self.get_by_id(collocation_id, user_id)
        if collocation:
            collocation.is_active = False
            self.session.add(collocation)
            self.session.commit()
            return True
        return False

    def delete_all(self, user_id: int) -> int:
        """Marca todas las collocations del usuario como inactivas."""
        collocations = self.session.exec(
            select(Collocation)
            .where(
                Collocation.user_id == user_id,
                Collocation.is_active == True
            )
        ).all()

        count = 0
        for c in collocations:
            c.is_active = False
            self.session.add(c)
            count += 1

        self.session.commit()
        return count

    def toggle_marked(self, collocation_id: int, user_id: int, is_marked: bool) -> Optional[Collocation]:
        """Actualiza el estado de marcado de una colocación."""
        collocation = self.get_by_id(collocation_id, user_id)
        if collocation:
            collocation.is_marked = is_marked
            self.session.add(collocation)
            self.session.commit()
            self.session.refresh(collocation)
            return collocation
        return None

    def get_user_collocations_filtered(
        self,
        user_id: int,
        status: str = "all"  # "all", "marked", "not_marked"
    ) -> List[Collocation]:
        """Obtiene collocations del usuario con filtro opcional de estado."""
        query = select(Collocation).where(
            Collocation.user_id == user_id,
            Collocation.is_active == True
        )

        if status == "marked":
            query = query.where(Collocation.is_marked == True)
        elif status == "not_marked":
            query = query.where(Collocation.is_marked == False)

        return self.session.exec(query.order_by(Collocation.created_at.desc())).all()
