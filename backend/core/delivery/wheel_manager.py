# backend/core/delivery/wheel_manager.py
"""
Gestor de la rueda circular (RoundRobinWheel).

Encapsula toda la lógica de construcción, actualización y consumo
de la rueda circular que alterna entre palabras boosteadas y
contenido del learning path.
"""

from typing import Optional, List, Tuple
from sqlmodel import Session, select
from core.enums import ContentType
from core.delivery.models import RoundRobinWheel, RoundRobinNeedle
from core.delivery.enums import RoundRobinWheelNodeStatus
from datetime import datetime, timezone
from logging_client import logger


class WheelManager:
    """
    Gestor de la rueda circular para distribución equitativa de contenido.

    La rueda es una lista enlazada circular que alterna entre:
    - Nodos de palabras boosteadas (word_id != NULL, is_learning_slot = False)
    - Nodos de learning path (word_id = NULL, is_learning_slot = True)

    Ejemplo: word_A → LEARNING → word_B → LEARNING → word_A (loop)
    """

    def __init__(self, session: Session):
        self.session = session

    def get_wheel_for_user(
        self, user_id: int, content_type: ContentType
    ) -> List[RoundRobinWheel]:
        """Obtiene todos los nodos de la rueda de un usuario, ordenados."""
        statement = (
            select(RoundRobinWheel)
            .where(
                RoundRobinWheel.user_id == user_id,
                RoundRobinWheel.content_type == content_type,
            )
            .order_by(RoundRobinWheel.order.asc())
        )
        return list(self.session.exec(statement).all())

    def add_word_to_wheel(
        self, user_id: int, content_type: ContentType, word_id: int
    ) -> Optional[RoundRobinWheel]:
        """
        Agrega una palabra boosteada a la rueda.
        Si es la primera, crea: word_id → LEARNING_SLOT → word_id (loop con learning intercalado).
        Si ya existen palabras, inserta: word_id → LEARNING_SLOT → siguiente.
        """
        # Obtener rueda actual
        wheel = self.get_wheel_for_user(user_id, content_type)

        if not wheel:
            # Primera palabra: crear word → LEARNING → word (loop)
            word_node = RoundRobinWheel(
                user_id=user_id,
                content_type=content_type,
                word_id=word_id,
                is_learning_slot=False,
                next_wheel_id=None,  # Se actualiza después
                order=0,
            )
            self.session.add(word_node)
            self.session.commit()
            self.session.refresh(word_node)

            # Crear nodo learning
            learning_node = RoundRobinWheel(
                user_id=user_id,
                content_type=content_type,
                word_id=None,
                is_learning_slot=True,
                next_wheel_id=word_node.id,  # Vuelve a la palabra
                order=1,
            )
            self.session.add(learning_node)
            self.session.commit()
            self.session.refresh(learning_node)

            # Actualizar word_node para apuntar al learning
            word_node.next_wheel_id = learning_node.id
            self.session.add(word_node)
            self.session.commit()

            # Crear aguja apuntando al nodo de palabra
            needle = RoundRobinNeedle(
                user_id=user_id,
                content_type=content_type,
                current_wheel_id=word_node.id,
            )
            self.session.add(needle)
            self.session.commit()

            logger.debug(
                f"[WheelManager] Created new wheel with word_id={word_id} + LEARNING_SLOT "
                f"for user {user_id} (content_type={content_type.value})"
            )
            return word_node
        else:
            # Agregar palabra a la rueda existente (SIN crear nodo LEARNING_SLOT extra)
            # Solo debería haber 1 nodo LEARNING_SLOT en toda la rueda
            last_node = wheel[-1]
            next_order = max([n.order for n in wheel]) + 1

            # Encontrar el único nodo LEARNING_SLOT
            learning_slot_node = next(
                (n for n in wheel if n.is_learning_slot), None
            )

            if not learning_slot_node:
                logger.warning(
                    f"[WheelManager] No learning_slot found in existing wheel for user {user_id}. "
                    f"This should not happen. Creating one."
                )
                learning_slot_node = RoundRobinWheel(
                    user_id=user_id,
                    content_type=content_type,
                    word_id=None,
                    is_learning_slot=True,
                    next_wheel_id=last_node.next_wheel_id,
                    order=next_order,
                )
                self.session.add(learning_slot_node)
                self.session.commit()
                self.session.refresh(learning_slot_node)
                next_order += 1

            # Crear nodo de palabra (NO crear nodo learning extra)
            word_node = RoundRobinWheel(
                user_id=user_id,
                content_type=content_type,
                word_id=word_id,
                is_learning_slot=False,
                next_wheel_id=learning_slot_node.id,  # ← Apunta al ÚNICO learning_slot
                order=next_order,
            )
            self.session.add(word_node)
            self.session.commit()
            self.session.refresh(word_node)

            # Actualizar conexión: last_node → word_node
            last_node.next_wheel_id = word_node.id
            self.session.add(last_node)
            self.session.commit()

            logger.debug(
                f"[WheelManager] Added word_id={word_id} to wheel "
                f"for user {user_id} at order={next_order} (linked to single LEARNING_SLOT)"
            )
            return word_node

    def remove_word_from_wheel(
        self, user_id: int, content_type: ContentType, word_id: int
    ) -> bool:
        """
        Quita una palabra boosteada de la rueda.
        También elimina el nodo LEARNING_SLOT que la sigue.
        Ajusta la aguja si es necesario:
        - Si la aguja está en el nodo removido, la mueve al ANTERIOR
        """
        wheel = self.get_wheel_for_user(user_id, content_type)
        node_to_remove = None
        prev_node = None
        learning_slot_node = None

        # Encontrar el nodo a eliminar y el anterior
        for node in wheel:
            if node.word_id == word_id:
                node_to_remove = node
                break
            prev_node = node

        if not node_to_remove:
            return False

        # Obtener el nodo LEARNING_SLOT que sigue a esta palabra
        learning_slot_node = self.session.get(RoundRobinWheel, node_to_remove.next_wheel_id)
        if learning_slot_node and not learning_slot_node.is_learning_slot:
            # El siguiente no es un learning slot, buscar después
            learning_slot_node = None

        # Si es el único nodo (o junto con su learning slot), eliminar toda la rueda
        if len(wheel) == 1 or (len(wheel) == 2 and learning_slot_node):
            self.session.delete(node_to_remove)
            if learning_slot_node:
                self.session.delete(learning_slot_node)
            # Eliminar aguja también
            needle_statement = select(RoundRobinNeedle).where(
                RoundRobinNeedle.user_id == user_id,
                RoundRobinNeedle.content_type == content_type,
            )
            needle = self.session.exec(needle_statement).first()
            if needle:
                self.session.delete(needle)
            self.session.commit()
            logger.debug(
                f"[WheelManager] Removed last word from wheel (word_id={word_id}) "
                f"for user {user_id}"
            )
            return True

        # Múltiples palabras: saltar el removido y su learning slot
        next_after_learning = node_to_remove.next_wheel_id
        if learning_slot_node:
            next_after_learning = learning_slot_node.next_wheel_id

        if prev_node:
            prev_node.next_wheel_id = next_after_learning
            self.session.add(prev_node)

        # Si la aguja apunta al nodo removido o su learning slot, moverla al ANTERIOR
        needle_statement = select(RoundRobinNeedle).where(
            RoundRobinNeedle.user_id == user_id,
            RoundRobinNeedle.content_type == content_type,
        )
        needle = self.session.exec(needle_statement).first()

        if needle and (needle.current_wheel_id == node_to_remove.id or
                       (learning_slot_node and needle.current_wheel_id == learning_slot_node.id)):
            if prev_node:
                # Mover aguja al anterior
                needle.current_wheel_id = prev_node.id
                logger.debug(
                    f"[WheelManager] Needle moved to previous node "
                    f"since removed word (word_id={word_id}) was current"
                )
            else:
                # El removido era el primero, mover al siguiente
                needle.current_wheel_id = next_after_learning
                logger.debug(
                    f"[WheelManager] Needle moved to next node "
                    f"since removed word was first"
                )

            needle.updated_at = datetime.now(timezone.utc)
            self.session.add(needle)

        self.session.delete(node_to_remove)
        if learning_slot_node:
            self.session.delete(learning_slot_node)
        self.session.commit()

        logger.debug(
            f"[WheelManager] Removed word_id={word_id} (+ LEARNING_SLOT) from wheel "
            f"for user {user_id}"
        )
        return True

    def get_current_needle_and_next(
        self, user_id: int, content_type: ContentType
    ) -> Optional[Tuple[RoundRobinWheel, Optional[RoundRobinWheel]]]:
        """
        Obtiene el nodo actual de la aguja y el siguiente.
        Retorna: (current_node, next_node) o None si no hay rueda.
        """
        needle_statement = select(RoundRobinNeedle).where(
            RoundRobinNeedle.user_id == user_id,
            RoundRobinNeedle.content_type == content_type,
        )
        needle = self.session.exec(needle_statement).first()

        if not needle:
            return None

        current_node = self.session.get(RoundRobinWheel, needle.current_wheel_id)
        if not current_node:
            return None

        next_node = self.session.get(RoundRobinWheel, current_node.next_wheel_id)
        return (current_node, next_node)

    def advance_needle(
        self, user_id: int, content_type: ContentType
    ) -> Optional[RoundRobinWheel]:
        """
        Avanza la aguja al siguiente nodo en la rueda.
        Retorna el nuevo nodo actual.
        """
        needle_statement = select(RoundRobinNeedle).where(
            RoundRobinNeedle.user_id == user_id,
            RoundRobinNeedle.content_type == content_type,
        )
        needle = self.session.exec(needle_statement).first()

        if not needle:
            return None

        current_node = self.session.get(RoundRobinWheel, needle.current_wheel_id)
        if not current_node or current_node.next_wheel_id is None:
            return None

        needle.current_wheel_id = current_node.next_wheel_id
        needle.updated_at = datetime.now(timezone.utc)
        self.session.add(needle)
        self.session.commit()

        return self.session.get(RoundRobinWheel, needle.current_wheel_id)

    # ==================== Estado Management ====================

    def initialize_wheel_status(
        self, user_id: int, content_type: ContentType
    ) -> int:
        """
        Reinicia el estado de todos los nodos de la rueda a INITIAL.
        GARANTIZA que siempre existe una rueda, incluso con solo LEARNING_SLOT.
        Si no existe, la crea automáticamente.
        Se llama al inicio de get_mixed_content() para resetear el tracking.

        Returns:
            Cantidad de nodos actualizados
        """
        wheel = self.get_wheel_for_user(user_id, content_type)

        # Si la rueda está vacía, crear una rueda mínima con solo LEARNING_SLOT
        if not wheel:
            logger.info(
                f"[WheelManager] No wheel found for user {user_id}. "
                f"Creating minimal wheel with only LEARNING_SLOT."
            )

            # Crear nodo LEARNING_SLOT que apunta a sí mismo (loop de 1 nodo)
            learning_slot = RoundRobinWheel(
                user_id=user_id,
                content_type=content_type,
                word_id=None,
                is_learning_slot=True,
                next_wheel_id=None,  # Se actualiza después
                order=0,
            )
            self.session.add(learning_slot)
            self.session.commit()
            self.session.refresh(learning_slot)

            # Hacer que apunte a sí mismo (loop)
            learning_slot.next_wheel_id = learning_slot.id
            self.session.add(learning_slot)
            self.session.commit()

            # Crear aguja apuntando al LEARNING_SLOT
            needle = RoundRobinNeedle(
                user_id=user_id,
                content_type=content_type,
                current_wheel_id=learning_slot.id,
            )
            self.session.add(needle)
            self.session.commit()

            logger.info(
                f"[WheelManager] Created minimal wheel (LEARNING_SLOT only) for user {user_id}"
            )

            wheel = [learning_slot]

        # Verificar que haya EXACTAMENTE 1 nodo learning_slot
        learning_slot_nodes = [node for node in wheel if node.is_learning_slot]

        if len(learning_slot_nodes) == 0:
            # Crear un nodo learning_slot
            logger.warning(
                f"[WheelManager] No learning_slot found for user {user_id}. Creating one..."
            )
            first_node = wheel[0]
            last_node = wheel[-1]
            max_order = max(node.order for node in wheel)

            learning_slot = RoundRobinWheel(
                user_id=user_id,
                content_type=content_type,
                word_id=None,
                is_learning_slot=True,
                next_wheel_id=first_node.id,  # Apunta al primero para cerrar el círculo
                order=max_order + 1,
            )
            self.session.add(learning_slot)
            self.session.commit()
            self.session.refresh(learning_slot)

            # Actualizar el último nodo para apuntar al nuevo learning_slot
            last_node.next_wheel_id = learning_slot.id
            self.session.add(last_node)
            self.session.commit()

            logger.warning(
                f"[WheelManager] Created learning_slot {learning_slot.id} for user {user_id}"
            )

            # Agregar el nuevo nodo a la lista
            wheel.append(learning_slot)

        elif len(learning_slot_nodes) > 1:
            # ⚠️ PROBLEMA: Hay múltiples LEARNING_SLOT (no debería pasar)
            logger.error(
                f"[WheelManager] ERROR: Found {len(learning_slot_nodes)} learning_slot nodes for user {user_id}. "
                f"Should be exactly 1. This indicates a bug in wheel construction. "
                f"Learning slot IDs: {[n.id for n in learning_slot_nodes]}"
            )
            # Mantener solo el primero, eliminar los extras
            keeper = learning_slot_nodes[0]
            for extra_slot in learning_slot_nodes[1:]:
                # Redirigir nodos que apuntan a slots extra hacia el keeper
                for node in wheel:
                    if node.next_wheel_id == extra_slot.id:
                        node.next_wheel_id = keeper.id
                        self.session.add(node)
                # Eliminar slot extra
                self.session.delete(extra_slot)
                logger.warning(
                    f"[WheelManager] Deleted duplicate learning_slot {extra_slot.id} for user {user_id}"
                )
            self.session.commit()
            # Actualizar wheel list
            wheel = [n for n in wheel if not n.is_learning_slot or n.id == keeper.id]

        # Reiniciar todos los nodos a INITIAL
        now = datetime.now(timezone.utc)
        for node in wheel:
            node.status = RoundRobinWheelNodeStatus.INITIAL
            node.updated_at = now
            self.session.add(node)

        self.session.commit()
        logger.debug(
            f"[WheelManager] Initialized {len(wheel)} wheel nodes to INITIAL state "
            f"for user {user_id} (content_type={content_type.value})"
        )
        return len(wheel)

    def update_node_status(
        self, wheel_id: int, status: RoundRobinWheelNodeStatus
    ) -> bool:
        """
        Actualiza el estado de un nodo específico en la rueda.

        Returns:
            True si se actualizó, False si no se encontró
        """
        node = self.session.get(RoundRobinWheel, wheel_id)
        if not node:
            return False

        node.status = status
        node.updated_at = datetime.now(timezone.utc)
        self.session.add(node)
        self.session.commit()

        logger.debug(
            f"[WheelManager] Updated wheel node {wheel_id} status to {status.value}"
        )
        return True

    def get_nodes_by_status(
        self,
        user_id: int,
        content_type: ContentType,
        status: RoundRobinWheelNodeStatus,
    ) -> List[RoundRobinWheel]:
        """
        Obtiene todos los nodos de la rueda con un estado específico.

        Returns:
            Lista de nodos con el estado especificado
        """
        statement = (
            select(RoundRobinWheel)
            .where(
                RoundRobinWheel.user_id == user_id,
                RoundRobinWheel.content_type == content_type,
                RoundRobinWheel.status == status,
            )
            .order_by(RoundRobinWheel.order.asc())
        )
        return list(self.session.exec(statement).all())

    def get_node_by_word_id(
        self,
        user_id: int,
        content_type: ContentType,
        word_id: int,
    ) -> Optional[RoundRobinWheel]:
        """
        Obtiene el nodo de la rueda para una palabra específica.

        Returns:
            El nodo correspondiente a la palabra, o None si no existe
        """
        statement = (
            select(RoundRobinWheel)
            .where(
                RoundRobinWheel.user_id == user_id,
                RoundRobinWheel.content_type == content_type,
                RoundRobinWheel.word_id == word_id,
            )
        )
        return self.session.exec(statement).first()

    def get_learning_slot_nodes(
        self,
        user_id: int,
        content_type: ContentType,
    ) -> List[RoundRobinWheel]:
        """
        Obtiene todos los nodos de learning slot para un usuario y tipo de contenido.

        Returns:
            Lista de nodos de learning slot
        """
        statement = (
            select(RoundRobinWheel)
            .where(
                RoundRobinWheel.user_id == user_id,
                RoundRobinWheel.content_type == content_type,
                RoundRobinWheel.is_learning_slot == True,
            )
            .order_by(RoundRobinWheel.order.asc())
        )
        return list(self.session.exec(statement).all())
