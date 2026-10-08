from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import joinedload
from sqlalchemy import nulls_last, distinct, case, and_
from sqlmodel import Session, func, or_, select
from logging_client import logger
import random
from features.examples.models import Example, ExampleType
from features.words.models import WordStatistics, Word
from core.enums import ContentType
from core.learning_path.enums import LearningState


class ExampleRepository:
    """
    Repository para la gestión de Examples.
    """

    def __init__(self, session: Session):
        self.session = session

    def count_available_examples_for_word(self, word_id: int) -> int:
        """
        Cuenta cuántos ejemplos disponibles hay para una palabra.

        Un example está disponible si:
        - Enseña la palabra (word_id coincide)
        - Es de tipo EXPLORE
        - No ha sido encolado aún (enqueued=False)
        - Su palabra no está en estado LEARNED
        """
        from features.words.models import WordStatistics
        from core.learning_path.models import LearningState

        # Obtener stats de la palabra con tipo EXAMPLE
        word_stats = self.session.exec(
            select(WordStatistics)
            .where(
                WordStatistics.word_id == word_id,
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).first()

        # Si la palabra ya está LEARNED, no hay ejemplos disponibles
        if word_stats and word_stats.learning_state == LearningState.LEARNED:
            return 0

        # Contar EXPLORE examples para esta palabra que no estén encolados
        count = self.session.exec(
            select(func.count(Example.id))
            .where(
                Example.word_id == word_id,
                Example.type == ExampleType.EXPLORE,
                Example.enqueued == False
            )
        ).first() or 0

        return count

    def get_available_content_for_word(self, word_id: int) -> Optional[int]:
        """
        Obtiene el próximo example disponible para una palabra específica.

        Un example está disponible si:
        - Enseña la palabra (word_id coincide)
        - Es de tipo EXPLORE
        - No ha sido encolado aún (enqueued=False)
        - Su palabra no está en estado LEARNED

        Retorna el example con la secuencia más baja (el más antiguo).
        """
        from logging_client import logger
        from features.words.models import WordStatistics
        from core.learning_path.models import LearningState

        # Verificar si la palabra ya está LEARNED
        word_stats = self.session.exec(
            select(WordStatistics)
            .where(
                WordStatistics.word_id == word_id,
                WordStatistics.type == ContentType.EXAMPLE
            )
        ).first()

        if word_stats and word_stats.learning_state == LearningState.LEARNED:
            logger.debug(
                f"[ExampleRepository] No valid EXPLORE examples found for word {word_id} "
                f"(word is already LEARNED)"
            )
            return None

        # Obtener el primer EXPLORE example para esta palabra
        result = self.session.exec(
            select(Example.id)
            .where(
                Example.word_id == word_id,
                Example.type == ExampleType.EXPLORE,
                Example.enqueued == False
            )
            .order_by(Example.sequence.asc())
            .limit(1)
        ).first()

        if result:
            logger.debug(
                f"[ExampleRepository] Found available EXPLORE example {result} for word {word_id}"
            )
            return result

        logger.debug(
            f"[ExampleRepository] No valid EXPLORE examples found for word {word_id}"
        )
        return None

    def get_word_ids(self, example_id: int) -> List[int]:
        """
        Obtiene los IDs de las palabras asociadas a un example.
        Retorna una lista con un solo ID (cada ejemplo solo enseña una palabra).
        """
        example = self.session.get(Example, example_id)
        if not example or not example.word_id:
            return []
        return [example.word_id]

    def is_example_learned(self, example_id: int, user_id: int) -> bool:
        """
        Chequea si un example está aprendido (su palabra está en estado LEARNED).

        Args:
            example_id: ID del example a chequear
            user_id: ID del usuario (para validación)

        Returns:
            True si el example debe ser descartado (palabra LEARNED)
            False si el example es válido
        """
        # Obtener el ejemplo con su word_id
        example = self.session.get(Example, example_id)
        if not example or not example.word_id:
            return False

        # Verificar que la palabra pertenece al usuario
        word = self.session.get(Word, example.word_id)
        if not word or word.user_id != user_id:
            return False

        # Verificar el estado de la palabra en WordStatistics
        word_stats = self.session.exec(
            select(WordStatistics)
            .where(
                WordStatistics.word_id == example.word_id,
                WordStatistics.type == ContentType.EXAMPLE,
            )
        ).first()

        if not word_stats:
            # Si no hay stats, no está aprendido
            return False

        # Retornar True si está LEARNED
        return word_stats.learning_state == LearningState.LEARNED

    def save(self, example: Example) -> Example:
        """
        Guarda un example en la base de datos.
        """
        self.session.add(example)
        self.session.commit()
        self.session.refresh(example)
        return example

    def segment_example_text(self, example: Example) -> List[Dict[str, Any]]:
        """
        Segmenta el texto de un ejemplo en chunks, marcando qué parts contienen target words.

        Retorna una lista de diccionarios con:
        - text: str
        - is_highlighted: bool
        - target_word: Optional[Dict] con id, main, type, meaning, level, is_boosted
        """
        # Obtener la palabra asociada al ejemplo
        if not example.word_id:
            # Si no hay palabra, retornar el texto completo sin resaltar
            return [
                {
                    "text": example.text,
                    "is_highlighted": False,
                    "target_word": None,
                }
            ]

        word = self.session.get(Word, example.word_id)
        if not word:
            # Si la palabra no existe, retornar el texto completo sin resaltar
            return [
                {
                    "text": example.text,
                    "is_highlighted": False,
                    "target_word": None,
                }
            ]

        # Crear un mapa de text_form -> Word (solo una palabra por ejemplo)
        text_form = example.text_form
        word_map = {
            text_form.lower(): {
                "id": word.id,
                "main": word.main,
                "type": "word",
                "meaning": word.meaning,
                "level": word.level,
                "is_boosted": word.is_boosted,
                "text_form": text_form,  # Guardar text_form original para referencia
            }
        }

        # Buscar todas las ocurrencias de palabras en el texto
        text = example.text
        segments = []
        current_pos = 0

        # Encontrar todas las palabras en orden de aparición
        words_found = []
        import re
        from features.examples.helpers import getAllInflections

        for word_form_key, word_data in word_map.items():
            # Generar todas las posibles inflexiones del word_form
            possible_forms = {word_form_key}  # Incluir la forma original

            try:
                # Intentar generar inflexiones
                inflections = getAllInflections(word_form_key)
                if inflections:
                    for form_list in inflections.values():
                        possible_forms.update([f.lower() for f in form_list if f])
            except Exception:
                pass

            # Para cada forma, también agregar variantes con apóstrofo (posesivo)
            forms_with_variants = set()
            for form in possible_forms:
                forms_with_variants.add(form)
                forms_with_variants.add(form + "'s")  # singular posesivo: crocodile's
                # Para plurales: crocodiles'
                if form.endswith('s'):
                    forms_with_variants.add(form + "'")
                else:
                    forms_with_variants.add(form + "s'")  # crocodiles'

            # Buscar cada una de las formas posibles en el texto
            for form in forms_with_variants:
                if not form:
                    continue
                # Patrón flexible: límite de palabra al inicio, pero flexible al final
                # Permite encontrar: "Crocodiles", "crocodile's", "crocodiles'"
                # No encuentra: "crocodile" en "cocrocodileal"
                pattern = r'(?:^|\W)(' + re.escape(form) + r')(?:\W|$)'
                for match in re.finditer(pattern, text.lower()):
                    # match.group(1) es la palabra sin los límites
                    pos = match.start(1)
                    actual_text = text[pos : match.end(1)]
                    words_found.append(
                        {
                            "start": pos,
                            "end": match.end(1),
                            "word_form": word_form_key,
                            "actual_text": actual_text,
                        }
                    )

        # Resolver overlaps: mantener solo la palabra más larga en cada posición
        words_found.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))

        merged_words = []
        for word in words_found:
            # Si no hay overlaps con palabras ya seleccionadas, agregar
            if not any(m["start"] <= word["start"] < m["end"] or
                      m["start"] < word["end"] <= m["end"]
                      for m in merged_words):
                merged_words.append(word)

        # Ordenar por posición de inicio
        merged_words.sort(key=lambda x: x["start"])

        # Segmentar el texto
        current_pos = 0
        for word_found in merged_words:
            start = word_found["start"]
            end = word_found["end"]
            word_form = word_found["word_form"]
            actual_text = word_found["actual_text"]

            # Agregar texto antes de la palabra
            if current_pos < start:
                segments.append(
                    {
                        "text": text[current_pos:start],
                        "is_highlighted": False,
                        "target_word": None,
                    }
                )

            # Agregar la palabra resaltada
            segments.append(
                {
                    "text": actual_text,
                    "is_highlighted": True,
                    "target_word": word_map[word_form],
                }
            )

            current_pos = end

        # Agregar texto restante después de la última palabra
        if current_pos < len(text):
            segments.append(
                {
                    "text": text[current_pos:],
                    "is_highlighted": False,
                    "target_word": None,
                }
            )

        return segments

    def toggle_favorite(self, user_id: int, example_id: int) -> bool:
        """
        Alterna el estado de favorito de un ejemplo (SOLO si pertenece al usuario).

        Cuando se marca como favorito:
        - Actualiza favorited_at con la fecha actual (aparecerá primero en el listado)
        - Resetea is_marked a False (favorite siempre se inicia sin marcar)

        Args:
            user_id: ID del usuario (REQUERIDO para validar pertenencia)
            example_id: ID del ejemplo a alternar

        Retorna el nuevo estado de is_favorite (False si el usuario no es propietario).
        """
        example = self.session.get(Example, example_id)

        if not example or not example.word_id:
            logger.warning(f"[ExampleRepository] Example {example_id} not found")
            return False

        # Verificar que el ejemplo pertenece al usuario
        word = self.session.get(Word, example.word_id)
        if not word or word.user_id != user_id:
            logger.warning(f"[ExampleRepository] User {user_id} attempted to modify example {example_id} of user {word.user_id if word else None} (SECURITY: Blocked)")
            return False

        example.is_favorite = not example.is_favorite
        # Registrar cuándo se marcó como favorito
        if example.is_favorite:
            example.favorited_at = datetime.now(timezone.utc)
            # Resetear marcado cuando se agrega a favoritos
            example.is_marked = False
            logger.debug(f"[ExampleRepository] Example {example_id} added to favorites by user {user_id}, is_marked reset to False")
        else:
            example.favorited_at = None

        self.session.add(example)
        self.session.commit()
        self.session.refresh(example)

        logger.debug(f"[ExampleRepository] Example {example_id} is_favorite toggled to {example.is_favorite} by user {user_id}")
        return example.is_favorite

    def toggle_marked(self, user_id: int, example_id: int) -> bool:
        """
        Alterna el estado de marcado de un ejemplo (SOLO si pertenece al usuario).

        Args:
            user_id: ID del usuario (REQUERIDO para validar pertenencia)
            example_id: ID del ejemplo a alternar

        Retorna el nuevo estado de is_marked (False si el usuario no es propietario).
        """
        example = self.session.get(Example, example_id)

        if not example or not example.word_id:
            logger.warning(f"[ExampleRepository] Example {example_id} not found")
            return False

        # Verificar que el ejemplo pertenece al usuario
        word = self.session.get(Word, example.word_id)
        if not word or word.user_id != user_id:
            logger.warning(f"[ExampleRepository] User {user_id} attempted to modify example {example_id} of user {word.user_id if word else None} (SECURITY: Blocked)")
            return False

        example.is_marked = not example.is_marked
        self.session.add(example)
        self.session.commit()
        self.session.refresh(example)

        logger.debug(f"[ExampleRepository] Example {example_id} is_marked toggled to {example.is_marked} by user {user_id}")
        return example.is_marked

    def get_examples(self, user_id: int, page: int = 1, limit: int = 15, is_marked: bool | None = None, sort_by: str = 'not_marked_first') -> dict:
        """
        Obtiene ejemplos favoritos del usuario con paginación.

        Args:
            user_id: ID del usuario (REQUERIDO para filtrar por propietario)
            page: Número de página
            limit: Items por página
            is_marked: Filtrar por estado de marcado (True/False/None para sin filtro) - DEPRECATED en favor de sort_by
            sort_by: Modo de ordenamiento ('done', 'random', 'not_marked_first')
                - 'done': Solo favoritos marcados, ordenados por fecha
                - 'not_marked_first': Todos los favoritos, primero no marcados, luego marcados
                - 'random': Solo NO marcados en orden aleatorio

        Retorna un diccionario con:
        - items: List de ejemplos
        - total: Total de ejemplos favoritos del usuario
        - page: Página actual
        - limit: Items por página
        - pages: Total de páginas
        """
        # Construir condiciones de filtro
        filters = [
            Example.is_favorite == True,
        ]

        # Si se usa sort_by='done', filtrar solo marcados
        if sort_by == 'done':
            filters.append(Example.is_marked == True)
        # Si se usa sort_by='random', filtrar solo NO marcados
        elif sort_by == 'random':
            filters.append(Example.is_marked == False)
        # Si se proporciona is_marked explícitamente (por compatibilidad), usarlo
        elif is_marked is not None:
            filters.append(Example.is_marked == is_marked)

        # Contar total de ejemplos favoritos del usuario
        total = self.session.exec(
            select(func.count(Example.id))
            .join(Word, Example.word_id == Word.id)
            .where(
                Word.user_id == user_id,
                *filters
            )
        ).first() or 0

        # Calcular paginación
        offset = (page - 1) * limit
        pages = (total + limit - 1) // limit if total > 0 else 1

        # Construir query base
        query = (
            select(Example)
            .join(Word, Example.word_id == Word.id)
            .where(
                Word.user_id == user_id,
                *filters
            )
        )

        # Aplicar ordenamiento según sort_by
        if sort_by == 'random':
            # Ordenamiento aleatorio
            from sqlalchemy import func as sa_func
            query = query.order_by(sa_func.random())
        elif sort_by == 'not_marked_first':
            # Primero no marcados, luego marcados, dentro de cada grupo por fecha (más reciente primero)
            query = query.order_by(
                Example.is_marked.asc(),  # False (0) antes que True (1)
                nulls_last(Example.favorited_at.desc())
            )
        else:  # 'done' o default
            # Solo por fecha (más reciente primero)
            query = query.order_by(nulls_last(Example.favorited_at.desc()))

        # Aplicar paginación
        examples = self.session.exec(
            query.offset(offset).limit(limit)
        ).all()

        logger.debug(f"[ExampleRepository] Retrieved {len(examples)} favorite examples for user {user_id} (page {page}, total {total}, sort_by={sort_by})")

        return {
            "items": examples,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages
        }

    def count_unmarked_favorites(self, user_id: int) -> int:
        """
        Cuenta el total de ejemplos favoritos no marcados del usuario.

        Args:
            user_id: ID del usuario (REQUERIDO para filtrar por propietario)

        Retorna el número de ejemplos del usuario donde is_favorite=True e is_marked=False.
        """
        count = self.session.exec(
            select(func.count(Example.id))
            .join(Word, Example.word_id == Word.id)
            .where(
                Word.user_id == user_id,
                Example.is_favorite == True,
                Example.is_marked == False
            )
        ).first() or 0

        logger.debug(f"[ExampleRepository] Unmarked favorite examples count for user {user_id}: {count}")
        return count
