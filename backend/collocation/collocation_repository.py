from typing import List, Optional, Dict, Any
from sqlmodel import Session, select
from sqlalchemy import desc
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
        word_id: Optional[int] = None,
        text_form: Optional[str] = None
    ) -> Collocation:
        """Crea una nueva colocación."""
        collocation = Collocation(
            user_id=user_id,
            phrase=phrase,
            word_id=word_id,
            text_form=text_form,
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
            phrases: Lista de dicts con estructura {phrase, word_id (opcional), text_form (opcional)}
        """
        collocations = []
        for item in phrases:
            collocation = Collocation(
                user_id=user_id,
                phrase=item.get("phrase"),
                word_id=item.get("word_id"),
                text_form=item.get("text_form"),
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
        """Obtiene collocations en uso del usuario con filtro opcional de estado.

        Solo devuelve collocations con is_in_use = True.
        Ordena por:
        1. in_use_at DESC (más reciente primero)
        2. created_at DESC (para items sin in_use_at)
        """
        query = select(Collocation).where(
            Collocation.user_id == user_id,
            Collocation.is_active == True,
            Collocation.is_in_use == True
        )

        if status == "marked":
            query = query.where(Collocation.is_marked == True)
        elif status == "not_marked":
            query = query.where(Collocation.is_marked == False)

        return self.session.exec(
            query.order_by(
                desc(Collocation.in_use_at),
                Collocation.created_at.desc()
            )
        ).all()

    def get_available_collocation_for_word(self, user_id: int, word_id: int) -> Optional[Collocation]:
        """Obtiene una collocation disponible (is_in_use=False) para una palabra específica."""
        return self.session.exec(
            select(Collocation)
            .where(
                Collocation.user_id == user_id,
                Collocation.word_id == word_id,
                Collocation.is_in_use == False,
                Collocation.is_active == True
            )
            .order_by(Collocation.created_at.asc())
            .limit(1)
        ).first()

    def mark_as_in_use(self, collocation_id: int) -> Optional[Collocation]:
        """Marca una collocation como en uso y establece in_use_at."""
        from datetime import datetime, timezone
        collocation = self.session.get(Collocation, collocation_id)
        if collocation:
            collocation.is_in_use = True
            collocation.in_use_at = datetime.now(timezone.utc)
            self.session.add(collocation)
            self.session.commit()
            self.session.refresh(collocation)
        return collocation

    def get_text_segments(self, collocation: Collocation) -> List[Dict[str, Any]]:
        """Obtiene los segmentos de texto de una collocation.

        Si text_form está guardado, busca esa forma en la phrase y la marca como highlighted.
        Si no, retorna un segmento único con toda la phrase sin destacar.
        """
        if not collocation.text_form:
            return [{"text": collocation.phrase, "is_highlighted": False}]

        # Buscar text_form en la phrase (case-insensitive)
        phrase = collocation.phrase
        text_form = collocation.text_form

        # Buscar la posición del text_form en la phrase
        phrase_lower = phrase.lower()
        text_form_lower = text_form.lower()
        pos = phrase_lower.find(text_form_lower)

        if pos == -1:
            # No se encontró, retornar la phrase completa sin destacar
            return [{"text": phrase, "is_highlighted": False}]

        # Construir segmentos: antes, highlighted, después
        segments = []

        # Segmento antes
        if pos > 0:
            segments.append({"text": phrase[:pos], "is_highlighted": False})

        # Segmento destacado
        segments.append({"text": phrase[pos:pos + len(text_form)], "is_highlighted": True})

        # Segmento después
        if pos + len(text_form) < len(phrase):
            segments.append({"text": phrase[pos + len(text_form):], "is_highlighted": False})

        return segments
