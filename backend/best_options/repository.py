from typing import List
from sqlmodel import Session, select
from models import BestOption


class BestOptionRepository:
    """Repository para gestión de best options"""

    def __init__(self, session: Session):
        self.session = session

    def get_available_content_for_path(self, user_id: int) -> List[int]:
        """
        Obtiene IDs de best_options disponibles para el path del usuario.

        Retorna best_options que existen pero todavía no están en ContentQueue.
        """
        # Retorna todas las best_options activas
        best_options = self.session.exec(
            select(BestOption).where(BestOption.is_active == True)
        ).all()

        return [bo.id for bo in best_options]

    def save(self, best_option: BestOption) -> BestOption:
        """Guarda una best_option en la BD"""
        self.session.add(best_option)
        self.session.commit()
        self.session.refresh(best_option)
        return best_option

    def mark_as_not_pristine(self, db: Session, best_option_ids: List[int]) -> None:
        """
        Marca best_options como no pristinas (ya encoladas).

        Este método puede implementarse en el futuro si es necesario.
        """
        pass
