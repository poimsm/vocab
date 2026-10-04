# src/core/delivery/services.py
from typing import Optional, Dict, Any, List
from sqlmodel import Session
from core.delivery.repository import DeliveryRepository
from core.delivery.enums import DeliveryStatus
from core.enums import ContentSourceType, ContentType
from core.event_bus import publish_event
from logging_client import logger
from core.boost.repository import BoostRepository
from core.learning_path.services import LearningPathService

class DeliveryService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = DeliveryRepository(session)

    def complete_content(self, buffer_id: int) -> bool:
        """
        Invocado cuando el usuario resuelve o completa el contenido en la UI.
        AQUÍ es donde se confirma que el ítem fue consumido.
        """
        updated = self.repo.mark_as_consumed(buffer_id)
        return updated is not None

    def register_generated_content(
        self,
        user_id: int,
        content_id: int,
        source_type: ContentSourceType,
        content_type: ContentType = ContentType.EXAMPLE,
        word_id: Optional[int] = None,
        learning_path_queue_id: Optional[int] = None,
    ) -> None:
        """
        Invocado desde las tareas/eventos cuando la generación de contenido termina exitosamente.

        Registra el contenido en DeliveryBuffer de manera secuencial.
        El contenido se consume en orden LIFO (último en llegar, último en consumirse).

        Args:
            learning_path_queue_id: ID del queue item si el contenido es para learning path, NULL para boost
        """
        source_type_value = source_type.value if hasattr(source_type, 'value') else source_type
        content_type_value = content_type.value if hasattr(content_type, 'value') else content_type

        self.repo.push_to_buffer(
            user_id=user_id,
            content_id=content_id,
            source_type=source_type,
            content_type=content_type,
            word_id=word_id,
            learning_path_queue_id=learning_path_queue_id,
        )

        logger.info(
            f"[DeliveryService] Registered content_id={content_id} for user {user_id} "
            f"(word_id={word_id}, queue_item_id={learning_path_queue_id}, "
            f"content_type={content_type_value}, source_type={source_type_value})"
        )

    def discard_word_content(self, user_id: int, word_id: int) -> None:
        """
        Publica el evento global 'event.word.unboosted' para descartar
        todo el contenido PENDING de una palabra específica del usuario.
        Usado cuando se des-boostea una palabra.
        """
        publish_event('event.word.unboosted', user_id=user_id, word_id=word_id)

    def get_mixed_content(
        self,
        user_id: int,
        content_type: ContentType,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Obtiene contenido con round robin entre palabras boosteadas y contenido normal.
        Retorna status + contenido.

        Estrategia:
        - Obtiene palabras boosteadas del usuario
        - Hace round robin: word_A, word_B, word_C, ..., normal, word_A, word_B, ...
        - Si se agota contenido de una palabra, la reemplaza con la siguiente en la rotación
        - Retorna items en orden LIFO (último en llegar primero)

        Status:
        - "ok": Contenido disponible en el buffer
        - "generating": Contenido está siendo generado o se triggeó generación
        - "no_words": Sin palabras disponibles para aprender

        Args:
            user_id: ID del usuario
            content_type: Tipo de contenido requerido (ContentType enum)
            limit: Cantidad de items a obtener

        Returns:
            Dict con status + content list
        """
        content_type_enum = content_type
        boost_repo = BoostRepository(self.session)
        learning_path_service = LearningPathService(self.session)

        # Obtener palabras boosteadas activas
        boosted_words = boost_repo.get_active_boosts(user_id)
        boosted_word_ids = [w.id for w in boosted_words]

        items_collected = []
        exhausted_words = set()

        # ========== PASO 1: Intentar obtener contenido boosteado ==========
        if boosted_word_ids:
            logger.debug(
                f"[DeliveryService] User {user_id} has {len(boosted_word_ids)} boosted words. "
                f"Attempting round robin collection..."
            )

            boost_idx = 0
            iteration_count = 0
            max_iterations = 15

            while len(items_collected) < limit and boosted_word_ids:
                iteration_count += 1
                if iteration_count > max_iterations:
                    logger.warning(
                        f"[DeliveryService] Max iterations ({max_iterations}) exceeded in boosted content collection "
                        f"for user {user_id}. Collected {len(items_collected)} items."
                    )
                    break

                # Ciclo round robin: word_A, word_B, word_C, ..., normal, word_A, ...
                if boost_idx < len(boosted_word_ids):
                    # Turno de palabra boosteada
                    word_id = boosted_word_ids[boost_idx]
                    item = self.repo.get_pending_content(
                        user_id, limit=1, word_id=word_id, content_type=content_type_enum
                    )

                    if item:
                        items_collected.extend(item)
                    else:
                        # Si se agota contenido de esta palabra, publicar evento para regeneración (una sola vez)
                        if content_type and word_id not in exhausted_words:
                            publish_event(
                                'event.boost.content_exhausted',
                                user_id=user_id,
                                word_id=word_id,
                                content_type=content_type.value,
                            )
                            exhausted_words.add(word_id)
                            logger.info(
                                f"[DeliveryService] Boost content exhausted for word {word_id}: {content_type.value}"
                            )

                        # Remover palabra agotada de la rotación
                        boosted_word_ids.pop(boost_idx)
                        if not boosted_word_ids:
                            break

                        # Ajustar índice
                        if boost_idx >= len(boosted_word_ids):
                            boost_idx = 0
                        else:
                            boost_idx += 1
                else:
                    # Turno de contenido normal (learning path)
                    if not boosted_word_ids:
                        break

                    item = self.repo.get_pending_content(
                        user_id, limit=1, word_id=None, content_type=content_type_enum
                    )

                    if item:
                        items_collected.extend(item)

                    # Resetear índice para nuevo ciclo
                    boost_idx = 0

        # ========== PASO 2: Si hay contenido boosteado, retornarlo ==========
        if items_collected:
            logger.info(
                f"[DeliveryService] Returning {len(items_collected)} boosted content items for user {user_id}"
            )
            return {
                "status": "ok",
                "content": [
                    {
                        'id': item.id,
                        'content_id': item.content_id,
                        'queue_item_id': item.learning_path_queue_id,
                        'word_id': item.word_id,
                        'content_type': item.content_type.value,
                        'source_type': item.source_type.value,
                        'status': item.status.value,
                    }
                    for item in items_collected[:limit]
                ],
            }

        # ========== PASO 3: No hay contenido boosteado, evaluar learning path ==========
        logger.debug(
            f"[DeliveryService] No boosted content for user {user_id}. "
            f"Checking learning path status..."
        )

        # 3a. Chequear si hay generación en progreso
        if learning_path_service.is_content_generating(user_id, content_type_enum):
            logger.info(
                f"[DeliveryService] Learning path content is currently generating for user {user_id}"
            )
            return {
                "status": "generating",
                "content": [],
            }

        # 3b. Chequear si hay palabras disponibles para generar
        has_available_words = learning_path_service.has_available_words_for_generation(
            user_id, content_type_enum
        )

        if not has_available_words:
            logger.warning(
                f"[DeliveryService] No available words for user {user_id} to generate content"
            )
            return {
                "status": "no_words",
                "content": [],
            }

        # 3c. Hay palabras disponibles pero no se está generando: intenta obtener contenido
        logger.debug(
            f"[DeliveryService] Checking for learning path content for user {user_id}..."
        )
        items = self.repo.get_pending_content(
            user_id, limit=limit, word_id=None, content_type=content_type_enum
        )

        if items:
            # Hay contenido disponible
            logger.info(
                f"[DeliveryService] Found {len(items)} learning path content items for user {user_id}"
            )
            return {
                "status": "ok",
                "content": [
                    {
                        'id': item.id,
                        'content_id': item.content_id,
                        'queue_item_id': item.learning_path_queue_id,
                        'word_id': item.word_id,
                        'content_type': item.content_type.value,
                        'source_type': item.source_type.value,
                        'status': item.status.value,
                    }
                    for item in items
                ],
            }

        # 3d. No hay contenido pero hay palabras disponibles: triggear generación
        logger.info(
            f"[DeliveryService] No learning path content in buffer but words available for user {user_id}. "
            f"Triggering generation..."
        )
        publish_event(
            'event.learning_path.content_exhausted',
            user_id=user_id,
            content_type=content_type_enum.value,
        )
        return {
            "status": "generating",
            "content": [],
        }

    def get_delivery_items_by_ids(self, delivery_ids: List[int], user_id: int) -> List:
        """
        Obtiene delivery buffer items por sus IDs.

        Args:
            delivery_ids: Lista de IDs de DeliveryBuffer
            user_id: ID del usuario (para validación de pertenencia)

        Returns:
            Lista de DeliveryBuffer items
        """
        if not delivery_ids:
            return []

        from core.delivery.models import DeliveryBuffer
        from sqlmodel import select

        items = self.session.exec(
            select(DeliveryBuffer).where(
                DeliveryBuffer.id.in_(delivery_ids),
                DeliveryBuffer.user_id == user_id,
            )
        ).all()

        return items

    def _get_available_word_ids_for_generation(
        self, user_id: int, content_type: ContentType
    ) -> List[int]:
        """
        Obtiene IDs de palabras disponibles para generar contenido.
        Usado cuando necesitamos triggear generación de learning path.
        """
        from features.words.models import Word, WordStatistics
        from core.learning_path.enums import LearningState
        from sqlmodel import select

        # Obtener palabras no-LEARNED para este usuario
        statement = (
            select(Word.id)
            .join(WordStatistics)
            .where(
                Word.user_id == user_id,
                Word.is_active == True,
                WordStatistics.type == content_type,
                WordStatistics.learning_state != LearningState.LEARNED,
            )
        )

        word_ids = self.session.exec(statement).all()
        return word_ids[:10]  # Limitar a 10 palabras para generación