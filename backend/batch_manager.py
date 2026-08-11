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
from logging_client import logger

import models
from models import (
    Batch,
    BatchFeatured,
    ContentType,
    BatchSource,
    BatchStatus,
    BatchFeaturedStatus,
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
            for content_type in ContentType:
                self._create_or_update_batch_featured(
                    batch_id=batch.id,
                    content_type=content_type
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
            # Para ORGANIC, reutilizar batch si existe y tiene capacidad
            existing_batch = self.db.exec(
                select(Batch)
                .where(
                    Batch.user_id == user_id,
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
        status = BatchStatus.OPEN

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

        # Crear estadísticas para la palabra por cada tipo
        for content_type in ContentType:
            stats = WordStatistics(
                word_id=word.id,
                type=content_type
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
        content_type: ContentType,
        limit: int = 50
    ) -> List[Word]:
        """
        Obtiene palabras de batches featured de un tipo específico.

        Args:
            user_id: ID del usuario
            content_type: Tipo de contenido (ContentType.EXAMPLE o ContentType.BEST_OPTIONS)
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
                BatchFeatured.type == content_type,
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
                Batch.status == BatchStatus.OPEN,
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
        content_type: ContentType
    ) -> BatchFeatured:
        """
        Crea un BatchFeatured para un batch.

        Args:
            batch_id: ID del batch
            content_type: Tipo de contenido (ContentType.EXAMPLE o ContentType.BEST_OPTIONS)

        Returns:
            BatchFeatured creado
        """
        return self._create_or_update_batch_featured(batch_id, content_type)

    def _create_or_update_batch_featured(
        self,
        batch_id: int,
        content_type: ContentType
    ) -> BatchFeatured:
        """Crea o actualiza BatchFeatured."""
        batch = self.db.get(Batch, batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} no encontrado")

        # Buscar si ya existe
        existing = self.db.exec(
            select(BatchFeatured).where(
                BatchFeatured.batch_id == batch_id,
                BatchFeatured.type == content_type
            )
        ).first()

        if existing:
            self._update_batch_featured_stats(existing)
            return existing

        # Crear nuevo
        words = batch.words or []
        learned = sum(1 for w in words if w.statistics and all(stat.is_learned for stat in w.statistics if stat.type == content_type))

        featured = BatchFeatured(
            batch_id=batch_id,
            type=content_type,
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
        learned = sum(1 for w in words if w.statistics and all(stat.is_learned for stat in w.statistics if stat.type == featured.type))

        featured.mastery_progress = round((learned / len(words) * 100), 2) if words else 0.0
        featured.last_activity_at = datetime.now(timezone.utc)

        if featured.mastery_progress >= 100.0 and not featured.completed_at:
            featured.completed_at = datetime.now(timezone.utc)

        self.db.add(featured)
        self.db.commit()

    def get_all_batch_featured(
        self,
        user_id: int,
        content_type: Optional[ContentType] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene todos los BatchFeatured de un usuario, opcionalmente filtrados por tipo.

        Args:
            user_id: ID del usuario
            content_type: Tipo de contenido (opcional)

        Returns:
            Lista de BatchFeatured con metadatos
        """
        statement = (
            select(BatchFeatured, Batch)
            .join(Batch, BatchFeatured.batch_id == Batch.id)
            .where(Batch.user_id == user_id, BatchFeatured.is_active == True)
        )

        if content_type:
            statement = statement.where(BatchFeatured.type == content_type)

        results = self.db.exec(statement).all()

        return [
            {
                "featured_id": featured.id,
                "batch_id": batch.id,
                "batch_title": batch.title,
                "type": featured.type.value,
                "mastery_progress": featured.mastery_progress,
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

    # ==========================================
    # GESTIÓN DE TRANSICIONES DE BATCHES POR TIPO
    # ==========================================

    def get_words_with_transition(
        self,
        user_id: int,
        content_type: ContentType,
        limit: int = 10,
        threshold_for_transition: int = 4
    ) -> List[Word]:
        """
        Obtiene palabras respetando transiciones entre batches por tipo específico.

        Estrategia:
        - Obtiene palabras del batch actual que no estén aprendidas (según el tipo)
        - Si el batch actual tiene pocas palabras restantes, comienza a incluir del siguiente
        - Cuando un batch se completa (todas sus palabras aprendidas para este tipo),
          se marca como COMPLETED
        - Cada tipo (EXAMPLE, BEST_OPTIONS) tiene su propio progreso

        Args:
            user_id: ID del usuario
            content_type: Tipo de contenido (ContentType.EXAMPLE o ContentType.BEST_OPTIONS)
            limit: Cantidad de palabras a devolver
            threshold_for_transition: Mínimo de palabras no aprendidas para no hacer transición

        Returns:
            Lista de palabras ordenadas por ciclo y última vez vista
        """
        # 1. Obtener batches con BatchFeatured ACTIVE u OPEN ordenados por antigüedad
        active_batches = self.db.exec(
            select(Batch)
            .join(BatchFeatured, BatchFeatured.batch_id == Batch.id)
            .where(
                Batch.user_id == user_id,
                BatchFeatured.type == content_type,
                BatchFeatured.status == BatchFeaturedStatus.ACTIVE
            )
            .order_by(Batch.created_at.asc())
        ).unique().all()

        if not active_batches:
            return []

        primary_batch = active_batches[0]
        result_words: List[Word] = []

        # 2. Obtener palabras no aprendidas del batch primario (según el tipo)
        unlearned_primary = self.db.exec(
            select(Word)
            .join(WordStatistics, (WordStatistics.word_id == Word.id) & (WordStatistics.type == content_type))
            .where(
                Word.batch_id == primary_batch.id,
                Word.is_active == True,
                WordStatistics.is_learned == False
            )
            .order_by(WordStatistics.current_cycle_seen.asc(), WordStatistics.last_seen_at.asc().nullsfirst())
        ).unique().all()

        # 3. Evaluar transición al siguiente batch
        if len(unlearned_primary) <= threshold_for_transition and len(active_batches) > 1:
            # El batch primario está casi completo, comenzar transición
            result_words = unlearned_primary
            needed_from_next = limit - len(result_words)

            if needed_from_next > 0:
                next_batch = active_batches[1]
                secondary_words = self.db.exec(
                    select(Word)
                    .join(WordStatistics, (WordStatistics.word_id == Word.id) & (WordStatistics.type == content_type))
                    .where(
                        Word.batch_id == next_batch.id,
                        Word.is_active == True,
                        WordStatistics.is_learned == False
                    )
                    .order_by(WordStatistics.current_cycle_seen.asc(), WordStatistics.last_seen_at.asc().nullsfirst())
                    .limit(needed_from_next)
                ).unique().all()

                result_words.extend(secondary_words)
        else:
            # Batch primario aún tiene suficientes palabras
            result_words = unlearned_primary[:limit]

        # 4. Verificar y actualizar estado de BatchFeatured si están completados (para este tipo)
        for batch in active_batches[:2]:  # Revisar máximo primero y segundo batch
            # Obtener el BatchFeatured para este tipo específico
            batch_featured = self.db.exec(
                select(BatchFeatured).where(
                    BatchFeatured.batch_id == batch.id,
                    BatchFeatured.type == content_type
                )
            ).first()

            if batch_featured and batch_featured.status != BatchFeaturedStatus.MASTERED:
                total_words_in_batch = self.db.exec(
                    select(func.count(Word.id)).where(Word.batch_id == batch.id, Word.is_active == True)
                ).one() or 0

                if total_words_in_batch > 0:
                    learned_words_for_type = self.db.exec(
                        select(func.count(Word.id))
                        .join(WordStatistics, (WordStatistics.word_id == Word.id) & (WordStatistics.type == content_type))
                        .where(
                            Word.batch_id == batch.id,
                            Word.is_active == True,
                            WordStatistics.is_learned == True
                        )
                    ).one() or 0

                    if learned_words_for_type >= total_words_in_batch:
                        # Todas las palabras del batch están aprendidas para este tipo
                        # Solo marcar como MASTERED si el Batch está COMPLETED
                        if batch.status == BatchStatus.COMPLETED:
                            batch_featured.status = BatchFeaturedStatus.MASTERED
                            batch_featured.completed_at = datetime.now(timezone.utc)
                            self.db.add(batch_featured)

        self.db.commit()
        return result_words

    # ==========================================
    # GESTIÓN DE BATCH FEATURED (para rutas)
    # ==========================================

    def get_all_batch_featured_by_user(
        self,
        user_id: int,
        content_type: Optional[ContentType] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene todos los BatchFeatured del usuario, opcionalmente filtrados por tipo.
        """
        query = (
            select(Batch, BatchFeatured)
            .join(BatchFeatured, BatchFeatured.batch_id == Batch.id)
            .where(Batch.user_id == user_id)
        )

        if content_type:
            query = query.where(BatchFeatured.type == content_type)

        results = self.db.exec(query).all()

        featured_list = []
        for batch, featured in results:
            total_words = len(batch.words)
            learned_words = sum(1 for w in batch.words if w.statistics and all(stat.is_learned for stat in w.statistics if stat.type == featured.type))
            progress = round((learned_words / total_words * 100), 2) if total_words > 0 else 0.0

            featured_list.append({
                "batch_featured_id": featured.id,
                "batch_id": batch.id,
                "batch_title": batch.title,
                "featured_type": featured.type.value,
                "status": featured.status.value,
                "progress": progress,
                "created_at": featured.created_at,
                "completed_at": featured.completed_at
            })

        return featured_list

    def get_words_for_batch_featured(
        self,
        batch_featured_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene todas las palabras asociadas a un BatchFeatured específico.
        """
        featured = self.db.get(BatchFeatured, batch_featured_id)
        if not featured:
            return None

        batch = featured.batch
        words = self.db.exec(
            select(Word).where(Word.batch_id == batch.id)
        ).all()

        return {
            "batch_featured_id": featured.id,
            "batch_id": batch.id,
            "batch_title": batch.title,
            "featured_type": featured.type.value,
            "status": featured.status.value,
            "total_words": len(words),
            "words": [
                {
                    "id": w.id,
                    "main": w.main,
                    "meaning": w.meaning,
                    "type": w.type,
                    "level": w.level,
                    "is_learned": all(stat.is_learned for stat in w.statistics if stat.type == featured.type) if w.statistics else False,
                    "is_active": w.is_active
                }
                for w in words
            ]
        }

    def reopen_batch_featured(
        self,
        batch_featured_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Reabre un BatchFeatured específico, marcando sus palabras como no aprendidas.
        """
        featured = self.db.get(BatchFeatured, batch_featured_id)
        if not featured:
            return None

        batch = featured.batch
        words = self.db.exec(
            select(Word).where(Word.batch_id == batch.id)
        ).all()

        # Resetear estadísticas para este tipo específico
        for word in words:
            stats = self.db.exec(
                select(WordStatistics).where(
                    WordStatistics.word_id == word.id,
                    WordStatistics.type == featured.type
                )
            ).first()

            if stats:
                stats.current_cycle_seen = 0
                stats.is_learned = False
                self.db.add(stats)

        # Cambiar estado a ACTIVE
        featured.status = BatchFeaturedStatus.ACTIVE
        featured.completed_at = None
        self.db.add(featured)
        self.db.commit()

        return {
            "batch_featured_id": featured.id,
            "batch_id": batch.id,
            "batch_title": batch.title,
            "featured_type": featured.type.value,
            "words_count": len(words),
            "message": f"BatchFeatured '{batch.title}' reabierto para revisión"
        }

    def reopen_multiple_batch_featured(
        self,
        batch_featured_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Reabre múltiples BatchFeatured específicos.
        """
        reopened = []
        failed = []

        for batch_featured_id in batch_featured_ids:
            try:
                result = self.reopen_batch_featured(batch_featured_id)
                if result:
                    reopened.append(result)
                else:
                    failed.append({
                        "batch_featured_id": batch_featured_id,
                        "reason": "No encontrado"
                    })
            except Exception as e:
                failed.append({
                    "batch_featured_id": batch_featured_id,
                    "reason": str(e)
                })

        return {
            "reopened_count": len(reopened),
            "reopened": reopened,
            "failed": failed
        }

    # ==========================================
    # CREACIÓN Y REUTILIZACIÓN DE BATCHES
    # ==========================================

    def get_or_create_propitious_batch(
        self,
        user_id: int,
        source: BatchSource = BatchSource.ORGANIC,
        title: Optional[str] = None
    ) -> Batch:
        """
        Obtiene un batch existente con capacidad disponible o crea uno nuevo.

        Args:
            user_id: ID del usuario
            source: Origen del batch (ORGANIC o BULK_IMPORT)
            title: Título del batch (opcional, solo para BULK_IMPORT)

        Returns:
            Batch disponible o recién creado
        """
        if source == BatchSource.ORGANIC:
            open_batch = self.db.exec(
                select(Batch)
                .where(
                    Batch.user_id == user_id,
                    Batch.source == BatchSource.ORGANIC
                )
                .order_by(Batch.created_at.desc())
            ).first()

            if open_batch and len(open_batch.words) < open_batch.capacity:
                self._create_batch_featured_for_types(open_batch.id)
                return open_batch

        else:
            # Para BULK_IMPORT, también buscar un batch existente con capacidad disponible
            open_batch = self.db.exec(
                select(Batch)
                .where(
                    Batch.user_id == user_id,
                    Batch.source == BatchSource.BULK_IMPORT
                )
                .order_by(Batch.created_at.desc())
            ).first()

            if open_batch and len(open_batch.words) < open_batch.capacity:
                self._create_batch_featured_for_types(open_batch.id)
                return open_batch

        # Si no hay batch disponible, crear uno nuevo
        count_batches = self.db.exec(
            select(func.count(Batch.id)).where(Batch.user_id == user_id)
        ).one() or 0

        new_batch = Batch(
            user_id=user_id,
            title=title or (f"Lote {count_batches + 1}" if source == BatchSource.ORGANIC else f"Importación {count_batches + 1}"),
            source=source
        )
        self.db.add(new_batch)
        self.db.commit()
        self.db.refresh(new_batch)
        self._create_batch_featured_for_types(new_batch.id)
        return new_batch

    def _create_batch_featured_for_types(self, batch_id: int) -> None:
        """
        Crea registros de BatchFeatured para todos los tipos disponibles.

        Args:
            batch_id: ID del batch
        """
        for content_type in ContentType:
            existing = self.db.exec(
                select(BatchFeatured).where(
                    BatchFeatured.batch_id == batch_id,
                    BatchFeatured.type == content_type
                )
            ).first()

            if not existing:
                featured = BatchFeatured(
                    batch_id=batch_id,
                    type=content_type,
                    status=BatchFeaturedStatus.ACTIVE
                )
                self.db.add(featured)
        self.db.commit()

    # ==========================================
    # REAPERTURA DE BATCHES (SPACED REPETITION)
    # ==========================================

    def reopen_batch_for_spaced_repetition(self, user_id: int) -> dict:
        """
        Reabre el batch completado más antiguo para memoria espaciada.

        Args:
            user_id: ID del usuario

        Returns:
            Diccionario con info del batch reabierto o mensaje de error
        """
        # Obtener batches COMPLETED del usuario, ordenados por antigüedad
        completed_batches = self.db.exec(
            select(Batch)
            .where(
                Batch.user_id == user_id,
                Batch.status == BatchStatus.COMPLETED
            )
            .order_by(Batch.completed_at.asc())
        ).all()

        if not completed_batches:
            logger.info(f"[reopen_batch_spaced_repetition] User {user_id}: No completed batches to reopen")
            return {"reopened": 0, "message": "No hay batches completados para reabrir"}

        batch_to_reopen = completed_batches[0]

        try:
            # Marcar todas las palabras del batch como is_learned=False
            words = self.db.exec(
                select(Word).where(Word.batch_id == batch_to_reopen.id)
            ).all()

            for word in words:
                # Resetear estadísticas para todos los tipos
                all_stats = self.db.exec(
                    select(WordStatistics).where(WordStatistics.word_id == word.id)
                ).all()

                for stats in all_stats:
                    stats.current_cycle_seen = 0
                    stats.is_learned = False
                    self.db.add(stats)

            # Cambiar estado de BatchFeatured a ACTIVE para memoria espaciada
            featured_items = self.db.exec(
                select(BatchFeatured).where(
                    BatchFeatured.batch_id == batch_to_reopen.id,
                    BatchFeatured.type == ContentType.SPACED_REPETITION
                )
            ).all()

            for featured in featured_items:
                featured.status = BatchFeaturedStatus.ACTIVE
                featured.completed_at = None
                self.db.add(featured)

            self.db.commit()

            logger.info(f"[reopen_batch_spaced_repetition] Batch #{batch_to_reopen.id} reopened for user {user_id}. Words: {len(words)}")

            return {
                "reopened": 1,
                "batch_id": batch_to_reopen.id,
                "batch_title": batch_to_reopen.title,
                "words_count": len(words),
                "message": f"Batch '{batch_to_reopen.title}' reabierto para revisión"
            }

        except Exception as e:
            logger.error(f"[reopen_batch_spaced_repetition] Error reopening batch: {str(e)}", exc_info=True)
            return {"reopened": 0, "error": str(e)}

    def reopen_batches_by_ids(self, user_id: int, batch_ids: List[int]) -> dict:
        """
        Reabre múltiples batches específicos manualmente.

        Args:
            user_id: ID del usuario
            batch_ids: Lista de IDs de batches a reabrir

        Returns:
            Diccionario con batches reabiertos y errores
        """
        reopened = []
        failed = []

        for batch_id in batch_ids:
            try:
                batch = self.db.exec(
                    select(Batch).where(
                        Batch.id == batch_id,
                        Batch.user_id == user_id
                    )
                ).first()

                if not batch:
                    failed.append({"batch_id": batch_id, "reason": "No encontrado"})
                    continue

                # Marcar palabras como is_learned=False
                words = self.db.exec(
                    select(Word).where(Word.batch_id == batch.id)
                ).all()

                for word in words:
                    # Resetear estadísticas para todos los tipos
                    all_stats = self.db.exec(
                        select(WordStatistics).where(WordStatistics.word_id == word.id)
                    ).all()

                    for stats in all_stats:
                        stats.current_cycle_seen = 0
                        stats.is_learned = False
                        self.db.add(stats)

                # Cambiar estado de BatchFeatured a ACTIVE
                featured_items = self.db.exec(
                    select(BatchFeatured).where(BatchFeatured.batch_id == batch.id)
                ).all()

                for featured in featured_items:
                    featured.status = BatchFeaturedStatus.ACTIVE
                    featured.completed_at = None
                    self.db.add(featured)

                reopened.append({
                    "batch_id": batch.id,
                    "title": batch.title,
                    "words_count": len(words)
                })

                logger.info(f"[reopen_batches_by_ids] Batch #{batch_id} manually reopened")

            except Exception as e:
                failed.append({"batch_id": batch_id, "reason": str(e)})
                logger.error(f"[reopen_batches_by_ids] Error in batch {batch_id}: {str(e)}")

        self.db.commit()

        return {
            "reopened_count": len(reopened),
            "reopened": reopened,
            "failed": failed
        }

    def get_batch_words(self, batch_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene todas las palabras de un batch con sus estadísticas.

        Args:
            batch_id: ID del batch
            user_id: ID del usuario

        Returns:
            Diccionario con información del batch y palabras, o None si no existe
        """
        batch = self.db.exec(
            select(Batch).where(
                Batch.id == batch_id,
                Batch.user_id == user_id
            )
        ).first()

        if not batch:
            return None

        words = self.db.exec(
            select(Word).where(Word.batch_id == batch_id)
        ).all()

        # Obtener estadísticas de palabras
        word_stats_map = {}
        for w in words:
            stats = self.db.exec(
                select(WordStatistics).where(WordStatistics.word_id == w.id)
            ).first()
            word_stats_map[w.id] = stats

        # Calcular progreso desde las palabras
        total_words = len(words)
        learned_words = sum(1 for w in words if word_stats_map.get(w.id) and word_stats_map[w.id].is_learned)
        batch_progress = round((learned_words / total_words * 100), 2) if total_words > 0 else 0.0

        return {
            "batch_id": batch.id,
            "batch_title": batch.title,
            "batch_status": batch.status.value,
            "batch_progress": batch_progress,
            "total_words": total_words,
            "words": [
                {
                    "id": w.id,
                    "main": w.main,
                    "meaning": w.meaning,
                    "type": w.type,
                    "level": w.level,
                    "is_learned": word_stats_map[w.id].is_learned if word_stats_map[w.id] else False,
                    "is_active": w.is_active,
                    "times_seen": word_stats_map[w.id].times_seen if word_stats_map[w.id] else 0,
                    "last_seen_at": word_stats_map[w.id].last_seen_at if word_stats_map[w.id] else None
                }
                for w in words
            ]
        }

    # ==========================================
    # SELECCIÓN DE CONTENIDO POR BATCH (EXAMPLES, BEST_OPTIONS)
    # ==========================================

    def get_content_items_for_queue(
        self,
        user_id: int,
        content_type: ContentType,
        limit: int = 10,
        threshold_for_transition: int = 4
    ) -> List[Any]:
        """
        Obtiene items de contenido (Examples o BestOptions) para la cola.

        Estrategia:
        - Obtiene palabras del batch actual respetando transiciones
        - Filtra contenido que contiene esas palabras
        - Solo selecciona items pristine
        - Randomiza y devuelve hasta el límite

        Args:
            user_id: ID del usuario
            content_type: Tipo de contenido (ContentType.EXAMPLE o ContentType.BEST_OPTIONS)
            limit: Cantidad máxima de items a devolver
            threshold_for_transition: Umbral para transición entre batches

        Returns:
            Lista de items de contenido (Examples o BestOptions)
        """
        # 1. Obtener palabras de batches activos (con transiciones)
        eligible_words = self.get_words_with_transition(
            user_id=user_id,
            content_type=content_type,
            limit=500,  # Obtener muchas palabras para filtrar
            threshold_for_transition=threshold_for_transition
        )

        if not eligible_words:
            return []

        eligible_word_ids = [w.id for w in eligible_words]

        # 2. Filtrar contenido pristine que contenga estas palabras
        if content_type == ContentType.EXAMPLE:
            from models import Example, ExampleWord

            # Obtener ejemplos pristine que contengan palabras elegibles
            statement = (
                select(Example)
                .join(ExampleWord, ExampleWord.example_id == Example.id)
                .where(
                    ExampleWord.word_id.in_(eligible_word_ids),
                    Example.is_pristine == True
                )
                .distinct()
            )
            eligible_items = self.db.exec(statement).all()

        elif content_type == ContentType.BEST_OPTIONS:
            from models import BestOption

            # Obtener best_options pristine que contengan palabras elegibles
            statement = (
                select(BestOption)
                .where(
                    BestOption.word_id.in_(eligible_word_ids),
                    BestOption.is_pristine == True
                )
            )
            eligible_items = self.db.exec(statement).all()
        else:
            return []

        if not eligible_items:
            return []

        # 3. Randomizar y seleccionar hasta el límite
        import random
        random.shuffle(eligible_items)
        selected_items = eligible_items[:limit]

        return selected_items
