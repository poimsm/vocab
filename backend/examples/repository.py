from typing import List
from sqlmodel import Session, select
from models import Example, ExampleType, ExampleWord


class ExampleRepository:
    """Repository para gestión de ejemplos"""

    def __init__(self, session: Session):
        self.session = session

    def get_available_content_for_path(self, user_id: int) -> List[int]:
        """
        Obtiene IDs de ejemplos disponibles para el path del usuario.

        Retorna ejemplos que existen pero todavía no están en ContentQueue.
        """
        # Por ahora retorna ejemplos del tipo EXPLORE
        examples = self.session.exec(
            select(Example).where(Example.type == ExampleType.EXPLORE)
        ).all()

        return [e.id for e in examples]

    def save(self, example: Example) -> Example:
        """Guarda un ejemplo en la BD"""
        self.session.add(example)
        self.session.commit()
        self.session.refresh(example)
        return example

    def mark_as_not_pristine(self, db: Session, example_ids: List[int]) -> None:
        """
        Marca ejemplos como no pristinos (ya encolados).

        Este método puede implementarse en el futuro si es necesario.
        """
        pass
