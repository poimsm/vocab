from typing import List, Dict, Any, Tuple


class ContentMixer:
    """
    Motor agnóstico de DB para mezclar contenido del learning path con contenido boosteado.

    Reglas:
    - Learning path: se agrega secuencialmente con order_position enteros
    - Boost: se intercala desde el order más pequeño no-dispatched hasta el más alto
    """

    @staticmethod
    def calculate_boost_position(
        existing_items: List[Dict[str, Any]],
        source_type: str,
    ) -> float:
        """
        Calcula la posición (order_position) para insertar un nuevo contenido.

        Estrategia:
        - Learning path: agregar secuencialmente al final
        - Boost: intercalar ANTES de items normales para máxima exposición
          * Primer boost va en 0.5 (antes del item 1.0)
          * Segundo boost en 1.5 (antes del item 2.0)
          * Tercero en 2.5 (antes del item 3.0), etc.

        Args:
            existing_items: List de items actuales en el buffer con keys:
                            id, order_position, status, source_type
            source_type: 'learning_path' | 'boost' | 'custom'

        Returns:
            float: order_position para el nuevo item
        """
        if not existing_items:
            return 1.0

        if source_type == 'learning_path':
            # Learning path: agregar secuencialmente después del último
            max_position = max(item['order_position'] for item in existing_items)
            return max_position + 1.0

        elif source_type == 'boost':
            # Boost: intercalar ANTES de items normales para máxima exposición
            # Buscar items no-despachados (PENDING, SERVED)
            non_dispatched = [
                item for item in existing_items
                if item['status'] in ['PENDING', 'SERVED']
            ]

            if not non_dispatched:
                # Si no hay items sin despachar, agregar al final
                max_position = max(item['order_position'] for item in existing_items)
                return max_position + 1.0

            # Ordenar items no-despachados por posición
            non_dispatched_sorted = sorted(non_dispatched, key=lambda x: x['order_position'])

            # Contar cuántos boosts ya existen para determinar índice
            existing_boosts = [
                item for item in existing_items
                if item['source_type'] == 'boost' and item['status'] in ['PENDING', 'SERVED']
            ]

            # El nuevo boost va justo ANTES del item en índice = len(existing_boosts)
            # Si hay 0 boosts existentes, va antes del item 0 (posición - 0.5)
            # Si hay 1 boost existente, va antes del item 1 (posición - 0.5)
            # etc.
            target_idx = len(existing_boosts)

            if target_idx >= len(non_dispatched_sorted):
                # Si ya hay demasiados boosts, agregar al final
                max_position = max(item['order_position'] for item in existing_items)
                return max_position + 1.0

            # Retornar posición justo ANTES del target item
            target_item_pos = non_dispatched_sorted[target_idx]['order_position']
            return target_item_pos - 0.5

        else:
            # Custom o desconocido: agregar al final
            max_position = max(item['order_position'] for item in existing_items)
            return max_position + 1.0

    @staticmethod
    def mix_contents(
        learning_path_items: List[Dict[str, Any]],
        boosted_items: List[Dict[str, Any]],
        boost_ratio: float = 0.25,
    ) -> List[Dict[str, Any]]:
        """
        Mezcla contenido de learning path con contenido boosteado.

        Args:
            learning_path_items: Items del learning path
            boosted_items: Items boosteados
            boost_ratio: Proporción de items boosteados (0-1)

        Returns:
            List de items mezclados ordenados por order_position
        """
        if not learning_path_items:
            return boosted_items

        if not boosted_items:
            return learning_path_items

        # Mezclar manteniendo el order_position correcto
        all_items = learning_path_items + boosted_items
        return sorted(all_items, key=lambda x: x['order_position'])
