"""
BatchManager: Clase centralizada para manejo de lógica de Batches.

Proporciona métodos para:
- Crear y gestionar batches
- Almacenar palabras en batches apropiados
- Consultar estadísticas de batches
- Encontrar batches dormidos
- Gestionar BatchFeatured
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, func
from logging_config import logger

import models
from models import (
    Batch,
    BatchFeatured,
    BatchFeaturedType,
    BatchSource,
    BatchStatus,
    Word,
    WordStatistics,
)


class BatchManager:
    """Gestor centralizado de lógica de batches."""

    def __init__(self, db: Session):
        self.db = db

    # ==========================================
    # GESTIÓN DE PALABRAS EN BATCHES
    # ==========================================

    def save_words_to_batches(
        self,
        user_id: int,
        words_data: List[dict],
        source: BatchSource = BatchSource.ORGANIC,
        batch_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Almacena un lote de palabras en batches apropiadoss.

        Args:
            user_id: ID del usuario
            words_data: Lista de diccionarios con datos de palabras
            source: Origen del batch (ORGANIC o BULK_IMPORT)
            batch_title: Título del batch (opcional, solo para BULK_IMPORT)

        Returns:
            Dict con información de batches creados/actualizados y palabras almacenadas
        """
        if not words_data:
            return {"batches": [], "words_count": 0}

        batch_capacity = 15  # TODO: Obtener de config
        affected_batches = []
        created_words = []

        # Agrupar palabras en batches según capacidad
        for i, word_data in enumerate(words_data):
            batch_index = i // batch_capacity

            if batch_index >= len(affected_batches):
                # Crear nuevo batch
                batch = self._get_or_create_batch(
                    user_id=user_id,
                    source=source,
                    batch_title=batch_title,
                    batch_number=batch_index + 1
                )
                affected_batches.append(batch)
            else:
                batch = affected_batches[batch_index]

            # Crear palabra y asociarla al batch
            word = self._create_word_in_batch(
                user_id=user_id,
                word_data=word_data,
                batch=batch
            )
            if word:
                created_words.append(word)

        self.db.commit()

        # Crear BatchFeatured de todos los tipos para cada batch creado
        for batch in affected_batches:
            for featured_type in BatchFeaturedType:
                self._create_or_update_batch_featured(
                    batch_id=batch.id,
                    featured_type=featured_type
                )

        return {
            "batches": [{"id": b.id, "title": b.title} for b in affected_batches],
            "words_count": len(created_words),
            "words": created_words
        }

    def _get_or_create_batch(
        self,
        user_id: int,
        source: BatchSource,
        batch_title: Optional[str] = None,
        batch_number: int = 1
    ) -> Batch:
        """Obtiene o crea un batch apropiado."""
        if source == BatchSource.ORGANIC:
            # Para ORGANIC, reutilizar batch OPEN si existe
            existing_batch = self.db.exec(
                select(Batch)
                .where(
                    Batch.user_id == user_id,
                    Batch.status == BatchStatus.OPEN,
                    Batch.source == BatchSource.ORGANIC
                )
                .order_by(Batch.created_at.desc())
            ).first()

            if existing_batch and len(existing_batch.words) < existing_batch.capacity:
                return existing_batch

        # Crear nuevo batch
        count = self.db.exec(
            select(func.count(Batch.id)).where(Batch.user_id == user_id)
        ).one() or 0

        title = batch_title or f"Lote {count + 1}"
        status = BatchStatus.ACTIVE if source == BatchSource.BULK_IMPORT else BatchStatus.OPEN

        new_batch = Batch(
            user_id=user_id,
            title=title,
            source=source,
            status=status
        )
        self.db.add(new_batch)
        self.db.flush()
        return new_batch

    def _create_word_in_batch(
        self,
        user_id: int,
        word_data: dict,
        batch: Batch
    ) -> Optional[Word]:
        """Crea una palabra y la asocia a un batch."""
        main_raw = word_data.get("main", "").strip()
        if not main_raw:
            return None

        normalized = main_raw.lower()

        # Evitar duplicados
        existing = self.db.exec(
            select(Word).where(
                Word.user_id == user_id,
                Word.normalized == normalized,
                Word.is_active == True
            )
        ).first()

        if existing:
            return None

        word = Word(
            **word_data,
            user_id=user_id,
            normalized=normalized,
            batch_id=batch.id
        )
        self.db.add(word)
        self.db.flush()

        # Crear estadísticas para la palabra
        stats = WordStatistics(
            word_id=word.id,
            type=""
        )
        self.db.add(stats)
        self.db.flush()

        return word

    # ==========================================
    # GESTIÓN DE PALABRAS POR TIPO
    # ==========================================

    def get_words_by_batch_featured_type(
        self,
        user_id: int,
        featured_type: BatchFeaturedType,
        limit: int = 50
    ) -> List[Word]:
        """
        Obtiene palabras de batches featured de un tipo específico.

        Args:
            user_id: ID del usuario
            featured_type: Tipo de BatchFeatured
            limit: Límite de palabras a retornar

        Returns:
            Lista de palabras asociadas a ese tipo de BatchFeatured
        """
        statement = (
            select(Word)
            .join(Batch, Word.batch_id == Batch.id)
            .join(BatchFeatured, BatchFeatured.batch_id == Batch.id)
            .where(
                Batch.user_id == user_id,
                BatchFeatured.type == featured_type,
                BatchFeatured.is_active == True,
                Word.is_active == True
            )
            .order_by(Word.created_at.desc())
            .limit(limit)
        )
        return self.db.exec(statement).all()

    # ==========================================
    # GESTIÓN DE BATCHES DORMIDOS
    # ==========================================

    def get_dormant_batches(
        self,
        user_id: int,
        days_threshold: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Encuentra batches que no han tenido actividad en N días.

        Args:
            user_id: ID del usuario
            days_threshold: Número de días sin actividad para considerar "dormido"

        Returns:
            Lista de batches dormidos con metadatos
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)

        dormant_batches = self.db.exec(
            select(Batch, BatchFeatured)
            .where(
                Batch.user_id == user_id,
                Batch.status.in_([BatchStatus.OPEN, BatchStatus.ACTIVE]),
                Batch.completed_at.is_(None)
            )
            .outerjoin(BatchFeatured, BatchFeatured.batch_id == Batch.id)
            .order_by(Batch.created_at.asc())
        ).all()

        result = []
        for batch, featured in dormant_batches:
            last_activity = featured.last_activity_at if featured else batch.created_at

            if last_activity < cutoff_date:
                result.append({
                    "batch_id": batch.id,
                    "title": batch.title,
                    "status": batch.status.value,
                    "last_activity": last_activity,
                    "days_dormant": (datetime.now(timezone.utc) - last_activity).days,
                    "words_count": len(batch.words),
                    "featured_type": featured.type.value if featured else None
                })

        return result

    # ==========================================
    # GESTIÓN DE BATCH FEATURED
    # ==========================================

    def create_batch_featured(
        self,
        batch_id: int,
        featured_type: BatchFeaturedType
    ) -> BatchFeatured:
        """
        Crea un BatchFeatured para un batch.

        Args:
            batch_id: ID del batch
            featured_type: Tipo de BatchFeatured

        Returns:
            BatchFeatured creado
        """
        return self._create_or_update_batch_featured(batch_id, featured_type)

    def _create_or_update_batch_featured(
        self,
        batch_id: int,
        featured_type: BatchFeaturedType
    ) -> BatchFeatured:
        """Crea o actualiza BatchFeatured."""
        batch = self.db.get(Batch, batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} no encontrado")

        # Buscar si ya existe
        existing = self.db.exec(
            select(BatchFeatured).where(
                BatchFeatured.batch_id == batch_id,
                BatchFeatured.type == featured_type
            )
        ).first()

        if existing:
            self._update_batch_featured_stats(existing)
            return existing

        # Crear nuevo
        words = batch.words or []
        learned = sum(1 for w in words if w.is_learned)

        featured = BatchFeatured(
            batch_id=batch_id,
            type=featured_type,
            total_words=len(words),
            learned_words=learned,
            mastery_progress=round((learned / len(words) * 100), 2) if words else 0.0
        )
        self.db.add(featured)
        self.db.commit()
        self.db.refresh(featured)
        return featured

    def _update_batch_featured_stats(self, featured: BatchFeatured) -> None:
        """Actualiza estadísticas de un BatchFeatured."""
        batch = self.db.get(Batch, featured.batch_id)
        if not batch:
            return

        words = batch.words or []
        learned = sum(1 for w in words if w.is_learned)

        featured.total_words = len(words)
        featured.learned_words = learned
        featured.mastery_progress = round((learned / len(words) * 100), 2) if words else 0.0
        featured.last_activity_at = datetime.now(timezone.utc)

        if featured.mastery_progress >= 100.0 and not featured.completed_at:
            featured.completed_at = datetime.now(timezone.utc)

        self.db.add(featured)
        self.db.commit()

    def get_all_batch_featured(
        self,
        user_id: int,
        featured_type: Optional[BatchFeaturedType] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene todos los BatchFeatured de un usuario, opcionalmente filtrados por tipo.

        Args:
            user_id: ID del usuario
            featured_type: Tipo de BatchFeatured (opcional)

        Returns:
            Lista de BatchFeatured con metadatos
        """
        statement = (
            select(BatchFeatured, Batch)
            .join(Batch, BatchFeatured.batch_id == Batch.id)
            .where(Batch.user_id == user_id, BatchFeatured.is_active == True)
        )

        if featured_type:
            statement = statement.where(BatchFeatured.type == featured_type)

        results = self.db.exec(statement).all()

        return [
            {
                "featured_id": featured.id,
                "batch_id": batch.id,
                "batch_title": batch.title,
                "type": featured.type.value,
                "mastery_progress": featured.mastery_progress,
                "total_words": featured.total_words,
                "learned_words": featured.learned_words,
                "completed_at": featured.completed_at,
                "last_activity_at": featured.last_activity_at,
                "days_since_activity": (datetime.now(timezone.utc) - featured.last_activity_at).days
            }
            for featured, batch in results
        ]

    # ==========================================
    # UTILIDADES
    # ==========================================

    def update_featured_stats_for_batch(self, batch_id: int) -> None:
        """
        Actualiza estadísticas de todos los BatchFeatured asociados a un batch.
        Se llama después de cambios en palabras del batch.

        Args:
            batch_id: ID del batch
        """
        featured_list = self.db.exec(
            select(BatchFeatured).where(BatchFeatured.batch_id == batch_id)
        ).all()

        for featured in featured_list:
            self._update_batch_featured_stats(featured)
