from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import joinedload
from sqlalchemy import nulls_last, distinct, case, and_
from sqlmodel import Session, func, or_, select
from logging_client import logger
from models import ContentQueue, ContentQueueStatus

import random
from models import (
    Example,
    ExampleWord,
    WordStatistics,
    ContentType,
    ExampleType,
    Word,
    LearningState,
)


class ExampleRepository:
    """
    Repository para la gestión de Examples.
    """

    def __init__(self, session: Session):
        self.session = session

    def get_available_content_for_path(self, user_id: int) -> List[int]:
        """
        Obtiene IDs de examples pristine que no están en ContentQueue.

        Estos examples pueden ser reutilizados en lugar de generar nuevos.
        """

        # Obtener IDs de examples ya encolados
        enqueued_ids = self.session.exec(
            select(ContentQueue.content_id)
            .where(
                ContentQueue.user_id == user_id,
                ContentQueue.type == ContentType.EXAMPLE,
                ContentQueue.status == ContentQueueStatus.PENDING,
            )
        ).all()

        enqueued_ids = set(enqueued_ids)

        # Obtener examples pristine que no estén encolados
        examples = self.session.exec(
            select(Example.id)
            .where(
                Example.id.notin_(enqueued_ids) if enqueued_ids else True,
            )
        ).all()

        return examples

    def count_available_examples_for_word(self, word_id: int) -> int:
        """
        Cuenta cuántos ejemplos disponibles hay para una palabra.

        Un example está disponible si:
        - Contiene la palabra (a través de ExampleWord)
        - Es de tipo EXPLORE
        - No ha sido encolado aún (enqueued=False)
        - No contiene SOLO palabras en estado LEARNED

        UNA SOLA QUERY: GROUP BY para contar palabras LEARNED vs total en cada ejemplo.
        """
        from models import WordStatistics, LearningState

        # Subquery: para cada ejemplo, contar palabras LEARNED y total
        example_stats = (
            select(
                Example.id,
                func.count(distinct(ExampleWord.word_id)).label("total_words"),
                func.count(
                    case(
                        (WordStatistics.learning_state == LearningState.LEARNED, 1),
                        else_=None
                    )
                ).label("learned_words")
            )
            .join(ExampleWord, Example.id == ExampleWord.example_id)
            .outerjoin(
                WordStatistics,
                and_(
                    WordStatistics.word_id == ExampleWord.word_id,
                    WordStatistics.type == ContentType.EXAMPLE
                )
            )
            .where(
                ExampleWord.word_id == word_id,
                Example.type == ExampleType.EXPLORE,
                Example.enqueued == False
            )
            .group_by(Example.id)
            .subquery()
        )

        # Contar ejemplos donde learned_words < total_words
        count = self.session.exec(
            select(func.count())
            .select_from(example_stats)
            .where(example_stats.c.learned_words < example_stats.c.total_words)
        ).first() or 0

        return count

    def get_available_content_for_word(self, word_id: int) -> Optional[int]:
        """
        Obtiene el próximo example disponible para una palabra específica.

        Un example está disponible si:
        - Contiene la palabra (a través de ExampleWord)
        - Es de tipo EXPLORE
        - No ha sido encolado aún (enqueued=False)
        - NUNCA fue consumido antes (excluye examples con CONSUMED items)
        - No contiene SOLO palabras en estado LEARNED

        Retorna el example con la secuencia más baja (el más antiguo).

        UNA SOLA QUERY: GROUP BY para filtrar ejemplos válidos de una vez.
        """
        from logging_client import logger
        from models import WordStatistics, LearningState

        # Subquery: para cada ejemplo, contar palabras LEARNED y total
        example_stats = (
            select(
                Example.id,
                Example.sequence,
                func.count(distinct(ExampleWord.word_id)).label("total_words"),
                func.count(
                    case(
                        (WordStatistics.learning_state == LearningState.LEARNED, 1),
                        else_=None
                    )
                ).label("learned_words")
            )
            .join(ExampleWord, Example.id == ExampleWord.example_id)
            .outerjoin(
                WordStatistics,
                and_(
                    WordStatistics.word_id == ExampleWord.word_id,
                    WordStatistics.type == ContentType.EXAMPLE
                )
            )
            .where(
                ExampleWord.word_id == word_id,
                Example.type == ExampleType.EXPLORE,
                Example.enqueued == False,
                Example.is_consumed == False
            )
            .group_by(Example.id, Example.sequence)
            .subquery()
        )

        # Obtener el primer ejemplo válido (donde learned_words < total_words)
        result = self.session.exec(
            select(example_stats.c.id)
            .where(example_stats.c.learned_words < example_stats.c.total_words)
            .order_by(example_stats.c.sequence.asc())
            .limit(1)
        ).first()

        if result:
            logger.debug(
                f"[ExampleRepository] Found available EXPLORE example {result} for word {word_id}"
            )
            return result

        logger.debug(
            f"[ExampleRepository] No valid EXPLORE examples found for word {word_id} "
            f"(all candidates have only LEARNED words)"
        )
        return None

    def get_word_ids(self, example_id: int) -> List[int]:
        """
        Obtiene los IDs de las palabras asociadas a un example.
        """
        word_ids = self.session.exec(
            select(ExampleWord.word_id)
            .where(ExampleWord.example_id == example_id)
        ).all()

        return word_ids

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
        - target_word: Optional[Dict] con id, main, type, meaning, level, is_boosted, batch_id
        """
        # Obtener las palabras asociadas al ejemplo
        example_words = self.session.exec(
            select(ExampleWord, Word)
            .join(Word, ExampleWord.word_id == Word.id)
            .where(ExampleWord.example_id == example.id)
        ).all()

        if not example_words:
            # Si no hay palabras, retornar el texto completo sin resaltar
            return [
                {
                    "text": example.text,
                    "is_highlighted": False,
                    "target_word": None,
                }
            ]

        # Crear un mapa de texto_form -> Word para búsqueda rápida
        word_map = {}
        for example_word, word in example_words:
            text_form = example_word.text_form
            word_map[text_form.lower()] = {
                "id": word.id,
                "main": word.main,
                "type": "word",
                "meaning": word.meaning,
                "level": word.level,
                "is_boosted": word.is_boosted,
                "text_form": text_form,  # Guardar text_form original para referencia
            }

        # Buscar todas las ocurrencias de palabras en el texto
        text = example.text
        segments = []
        current_pos = 0

        # Encontrar todas las palabras en orden de aparición
        words_found = []
        import re
        from examples.helpers import getAllInflections

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

    def toggle_favorite(self, example_id: int) -> bool:
        """
        Alterna el estado de favorito de un ejemplo.

        Retorna el nuevo estado de is_favorite.
        """
        example = self.session.get(Example, example_id)

        if not example:
            logger.warning(f"[ExampleRepository] Example {example_id} not found")
            return False

        example.is_favorite = not example.is_favorite
        # Registrar cuándo se marcó como favorito
        if example.is_favorite:
            example.favorited_at = datetime.now(timezone.utc)
        else:
            example.favorited_at = None

        self.session.add(example)
        self.session.commit()
        self.session.refresh(example)

        logger.debug(f"[ExampleRepository] Example {example_id} is_favorite toggled to {example.is_favorite}")
        return example.is_favorite

    def toggle_marked(self, example_id: int) -> bool:
        """
        Alterna el estado de marcado de un ejemplo.

        Retorna el nuevo estado de is_marked.
        """
        example = self.session.get(Example, example_id)

        if not example:
            logger.warning(f"[ExampleRepository] Example {example_id} not found")
            return False

        example.is_marked = not example.is_marked
        self.session.add(example)
        self.session.commit()
        self.session.refresh(example)

        logger.debug(f"[ExampleRepository] Example {example_id} is_marked toggled to {example.is_marked}")
        return example.is_marked

    def get_examples(self, page: int = 1, limit: int = 15, is_marked: bool | None = None, sort_by: str = 'not_marked_first') -> dict:
        """
        Obtiene ejemplos favoritos con paginación.

        Args:
            page: Número de página
            limit: Items por página
            is_marked: Filtrar por estado de marcado (True/False/None para sin filtro) - DEPRECATED en favor de sort_by
            sort_by: Modo de ordenamiento ('done', 'random', 'not_marked_first')
                - 'done': Solo favoritos marcados, ordenados por fecha
                - 'not_marked_first': Todos los favoritos, primero no marcados, luego marcados
                - 'random': Solo NO marcados en orden aleatorio

        Retorna un diccionario con:
        - items: List de ejemplos
        - total: Total de ejemplos favoritos
        - page: Página actual
        - limit: Items por página
        - pages: Total de páginas
        """
        # Construir condiciones de filtro
        filters = [Example.is_favorite == True]

        # Si se usa sort_by='done', filtrar solo marcados
        if sort_by == 'done':
            filters.append(Example.is_marked == True)
        # Si se usa sort_by='random', filtrar solo NO marcados
        elif sort_by == 'random':
            filters.append(Example.is_marked == False)
        # Si se proporciona is_marked explícitamente (por compatibilidad), usarlo
        elif is_marked is not None:
            filters.append(Example.is_marked == is_marked)

        # Contar total de ejemplos favoritos
        total = self.session.exec(
            select(func.count(Example.id))
            .where(*filters)
        ).first() or 0

        # Calcular paginación
        offset = (page - 1) * limit
        pages = (total + limit - 1) // limit if total > 0 else 1

        # Construir query base
        query = select(Example).where(*filters)

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

        logger.debug(f"[ExampleRepository] Retrieved {len(examples)} favorite examples (page {page}, total {total}, sort_by={sort_by})")

        return {
            "items": examples,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages
        }
