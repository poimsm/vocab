# src/core/delivery/service.py
import time
from typing import Optional, Dict, Any, List
from sqlmodel import Session
from core.delivery.repository import DeliveryRepository
from core.delivery.wheel_manager import WheelManager
from core.enums import ContentSourceType, ContentType
from core.event_bus import publish_event_background
from logging_client import logger
from core.learning_path.services import LearningPathService

class DeliveryService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = DeliveryRepository(session)
        self.wheel_manager = WheelManager(session)

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

    def discard_word_content(self, user_id: int, word_id: int, boosted_word_ids: Optional[List[int]] = None) -> None:
        """
        Descarta todo el contenido PENDING de una palabra específica.
        Usado cuando se des-boostea una palabra.
        """
        # Publicar evento que triggeará removal de rueda y descarte de contenido
        publish_event_background('word.unboosted', user_id=user_id, word_id=word_id)

    def get_mixed_content(
        self,
        user_id: int,
        content_type: ContentType,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Obtiene contenido con round robin usando una rueda circular persistente con state management.
        La rueda es la fuente de verdad, actualizada por eventos de boost/unboost.

        Estrategia:
        - Inicializa todos los nodos de la rueda a INITIAL
        - Usa aguja para saber por dónde va la rotación
        - Alterna: palabra_boosteada, learning_path, palabra_boosteada, learning_path, ...
        - Para cada nodo:
          - Si tiene contenido: marca como READY, lo consume
          - Si NO tiene contenido: marca como GENERATING, publica evento, CONTINÚA al siguiente
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
        from core.delivery.enums import RoundRobinWheelNodeStatus
        from core.enums import ContentSourceType
        from core.learning_path.enums import LearningPathQueueStatus

        from features.content_repository import UnifiedContentRepository

        content_repo = UnifiedContentRepository(self.session)
        learning_path_service = LearningPathService(self.session, content_repo)
        items_collected = []
        consumed_item_ids = set()
        generating_node_ids = set()  # Nodos que quedaron en GENERATING

        # ========== PASO 1: Inicializar estado de la rueda ==========
        self.wheel_manager.initialize_wheel_status(user_id, content_type)

        # ========== PASO 2: Consumir directamente desde la rueda circular ==========
        needle_and_next = self.wheel_manager.get_current_needle_and_next(user_id, content_type)

        if needle_and_next:
            current_node, next_node = needle_and_next
            logger.debug(
                f"[DeliveryService] Rueda circular encontrada para user {user_id}: "
                f"current_node={current_node.word_id if current_node.word_id else 'LEARNING_SLOT'}"
            )

            iteration_count = 0
            max_iterations = 15  # Allow more iterations to wait for background generation tasks to complete
            exhausted_words = set()  # Palabras sin contenido (evitar duplicar eventos)
            total_nodes = len(self.wheel_manager.get_wheel_for_user(user_id, content_type))
            exhausted_node_count = 0  # Contador de nodos EXHAUSTED
            had_generating_node = False  # Track si hay nodos GENERATING en esta iteración

            while len(items_collected) < limit:
                iteration_count += 1
                had_generating_node = False  # Reset para esta iteración

                if iteration_count > max_iterations:
                    logger.warning(
                        f"[DeliveryService] Max iterations ({max_iterations}) exceeded consuming from wheel "
                        f"for user {user_id}. Collected {len(items_collected)} items."
                    )
                    break

                if not current_node:
                    break

                # Skipear nodos EXHAUSTED
                if current_node.status == RoundRobinWheelNodeStatus.EXHAUSTED:
                    logger.debug(
                        f"[DeliveryService] Skipping EXHAUSTED node {current_node.id} "
                        f"for user {user_id}"
                    )
                    exhausted_node_count += 1
                    # Si todos los nodos están EXHAUSTED, salir
                    if exhausted_node_count >= total_nodes:
                        logger.info(
                            f"[DeliveryService] All {total_nodes} nodes are EXHAUSTED for user {user_id}. "
                            f"Breaking wheel traversal."
                        )
                        break
                    # Avanzar al siguiente nodo
                    self.wheel_manager.advance_needle(user_id, content_type)
                    needle_and_next = self.wheel_manager.get_current_needle_and_next(user_id, content_type)
                    if needle_and_next:
                        current_node, next_node = needle_and_next
                    else:
                        break
                    continue

                # Reset exhausted_node_count cuando encontramos un nodo que NO es EXHAUSTED
                exhausted_node_count = 0

                # Consumir de la posición actual de la rueda
                if current_node.is_learning_slot:
                    # Nodo LEARNING_SLOT: primero verificar PENDING en delivery_buffer
                    logger.debug(
                        f"[DeliveryService] LEARNING_SLOT node {current_node.id}: "
                        f"checking for pending items first..."
                    )

                    pending_learning_items = self.repo.get_pending_content(
                        user_id=user_id,
                        limit=1,
                        content_type=content_type,
                        source_type=ContentSourceType.LEARNING_PATH
                    )

                    if pending_learning_items:
                        # ✅ Hay item PENDING generado anteriormente
                        delivery_item = pending_learning_items[0]
                        if delivery_item.id not in consumed_item_ids:
                            items_collected.append(delivery_item)
                            consumed_item_ids.add(delivery_item.id)

                            # Marcar item como DISPATCHED inmediatamente para no reiterarlo
                            self.repo.mark_multiple_as_dispatched([delivery_item.id], user_id=user_id)

                            # Marcar nodo como READY
                            self.wheel_manager.update_node_status(
                                current_node.id, RoundRobinWheelNodeStatus.READY
                            )

                            logger.debug(
                                f"[DeliveryService] Consumed pending learning path content (id={delivery_item.id}) "
                                f"from delivery_buffer for user {user_id}. Node marked as READY and DISPATCHED."
                            )
                    else:
                        # No hay PENDING, obtener contenido prioritizado nuevo
                        logger.debug(
                            f"[DeliveryService] No pending learning items. "
                            f"Fetching prioritized content from learning path service..."
                        )

                        queue_item = learning_path_service.get_prioritized_content(
                            user_id=user_id,
                            content_type=content_type,
                        )

                        if queue_item:
                            try:
                                # Transferir a DeliveryBuffer on-demand
                                delivery_item = self.repo.push_to_buffer(
                                    user_id=user_id,
                                    content_id=queue_item.content_id,
                                    source_type=ContentSourceType.LEARNING_PATH,
                                    content_type=queue_item.content_type,
                                    word_id=queue_item.word_id,
                                    learning_path_queue_id=queue_item.id,
                                )

                                if delivery_item and delivery_item.id not in consumed_item_ids:
                                    items_collected.append(delivery_item)
                                    consumed_item_ids.add(delivery_item.id)

                                    # Marcar como TRANSFERRED
                                    queue_item.status = LearningPathQueueStatus.TRANSFERRED
                                    self.session.add(queue_item)
                                    self.session.commit()

                                    # Marcar item como DISPATCHED inmediatamente para no reiterarlo
                                    self.repo.mark_multiple_as_dispatched([delivery_item.id], user_id=user_id)

                                    # Marcar nodo como READY
                                    self.wheel_manager.update_node_status(
                                        current_node.id, RoundRobinWheelNodeStatus.READY
                                    )

                                    logger.debug(
                                        f"[DeliveryService] Consumed learning path content (id={delivery_item.id}, "
                                        f"queue_item={queue_item.id}) for user {user_id}. Node marked as READY and DISPATCHED."
                                    )
                            except Exception as e:
                                logger.error(
                                    f"[DeliveryService] Error consuming learning path content: {e}",
                                    exc_info=True
                                )
                        else:
                            # No hay contenido (ni PENDING ni nuevo)
                            # Verificar si hay generación en progreso
                            is_generating = learning_path_service.is_content_generating(user_id, content_type)

                            if is_generating:
                                # Generación en progreso: marcar como GENERATING
                                self.wheel_manager.update_node_status(
                                    current_node.id, RoundRobinWheelNodeStatus.GENERATING
                                )
                                generating_node_ids.add(current_node.id)
                                had_generating_node = True
                                logger.info(
                                    f"[DeliveryService] Learning path content is GENERATING for user {user_id}. "
                                    f"Node {current_node.id} marked as GENERATING."
                                )
                            else:
                                # No hay generación en progreso: marcar como EXHAUSTED (definitivo)
                                self.wheel_manager.update_node_status(
                                    current_node.id, RoundRobinWheelNodeStatus.EXHAUSTED
                                )
                                logger.warning(
                                    f"[DeliveryService] Learning path content exhausted (no pending, no prioritized, "
                                    f"no generation in progress). Node {current_node.id} marked as EXHAUSTED."
                                )
                            # CONTINUAR al siguiente nodo, no break

                else:
                    # Nodo de palabra boosteada
                    word_id = current_node.word_id
                    logger.debug(
                        f"[DeliveryService] Checking boost word node {current_node.id}: "
                        f"word_id={word_id}, status={current_node.status.value}"
                    )

                    items = self.repo.get_pending_content(
                        user_id,
                        limit=1,
                        word_id=word_id,
                        content_type=content_type,
                        source_type=ContentSourceType.BOOST
                    )

                    logger.debug(
                        f"[DeliveryService] Query for boost word {word_id}: "
                        f"found {len(items)} pending items"
                    )

                    # Filtrar items ya consumidos en esta request
                    found_item = False
                    for item in items:
                        if item.id not in consumed_item_ids:
                            items_collected.append(item)
                            consumed_item_ids.add(item.id)
                            found_item = True

                            # Marcar item como DISPATCHED inmediatamente para no reiterarlo
                            self.repo.mark_multiple_as_dispatched([item.id], user_id=user_id)

                            # Marcar nodo como READY
                            self.wheel_manager.update_node_status(
                                current_node.id, RoundRobinWheelNodeStatus.READY
                            )

                            logger.debug(
                                f"[DeliveryService] Consumed boost content (id={item.id}, word_id={word_id}) "
                                f"for user {user_id}. Node marked as READY and DISPATCHED."
                            )

                    if not found_item:
                        # No hay contenido
                        if word_id not in exhausted_words:
                            # Primera vez sin contenido: publicar evento y marcar como GENERATING
                            self.wheel_manager.update_node_status(
                                current_node.id, RoundRobinWheelNodeStatus.GENERATING
                            )
                            generating_node_ids.add(current_node.id)
                            had_generating_node = True

                            publish_event_background(
                                'boost.content.exhausted',
                                user_id=user_id,
                                word_id=word_id,
                                content_type=content_type.value,
                            )
                            logger.info(
                                f"[DeliveryService] Boost content exhausted for word {word_id}. "
                                f"Node marked as GENERATING. Event published."
                            )
                            exhausted_words.add(word_id)
                        else:
                            # Boost word nodes NUNCA se marcan como EXHAUSTED
                            # Siempre pueden generar más contenido (boost es infinito)
                            # Mantener GENERATING hasta que haya contenido disponible
                            self.wheel_manager.update_node_status(
                                current_node.id, RoundRobinWheelNodeStatus.GENERATING
                            )
                            generating_node_ids.add(current_node.id)
                            had_generating_node = True
                            logger.debug(
                                f"[DeliveryService] Boost word {word_id} still has no content. "
                                f"Node remains GENERATING (boost can generate indefinitely)."
                            )
                        # CONTINUAR al siguiente nodo, no break

                # Avanzar aguja al siguiente nodo
                self.wheel_manager.advance_needle(user_id, content_type)
                needle_and_next = self.wheel_manager.get_current_needle_and_next(user_id, content_type)
                if needle_and_next:
                    current_node, next_node = needle_and_next
                else:
                    break

                # Si hay nodos GENERATING, hacer sleep para dar tiempo a la generación
                if had_generating_node:
                    logger.debug(
                        f"[DeliveryService] Found GENERATING node, sleeping 0.5s to allow content generation "
                        f"for user {user_id}"
                    )
                    time.sleep(0.5)

        # ========== PASO 3: Si hay contenido (boosted + learning), retornarlo ==========
        if items_collected:
            logger.info(
                f"[DeliveryService] Returning {len(items_collected)} mixed content items "
                f"(round-robin boosted + learning path) for user {user_id}"
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

        # ========== PASO 4: Si hay nodos en GENERATING, retornar "generating" ==========
        if generating_node_ids:
            logger.info(
                f"[DeliveryService] {len(generating_node_ids)} wheel nodes are GENERATING for user {user_id}"
            )
            return {
                "status": "generating",
                "content": [],
            }

        # ========== PASO 5: No hay contenido - determinar estado ==========
        # El while ya verificó PENDING e intentó obtener de LearningPathQueue
        # Si llegamos aquí, no hay contenido disponible

        logger.info(
            f"[DeliveryService] No content available after wheel traversal for user {user_id}"
        )

        # Verificar si hay generación en progreso
        if learning_path_service.is_content_generating(user_id, content_type):
            logger.info(
                f"[DeliveryService] Content is currently generating for user {user_id}"
            )
            return {
                "status": "generating",
                "content": [],
            }

        # Si no hay generación en progreso y no hay contenido, es "no_words"
        logger.warning(
            f"[DeliveryService] No content available and no generation in progress for user {user_id}"
        )
        return {
            "status": "no_words",
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