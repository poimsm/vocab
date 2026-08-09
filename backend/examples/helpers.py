from lemminflect import getAllInflections


# Caché global para diccionario de verbos irregulares
_IRREGULAR_VERBS_CACHE = None


def load_irregular_verbs() -> dict:
    """Carga el diccionario de verbos irregulares desde el archivo."""
    global _IRREGULAR_VERBS_CACHE

    if _IRREGULAR_VERBS_CACHE is not None:
        return _IRREGULAR_VERBS_CACHE

    import os
    irregular_verbs_path = os.path.join(
        os.path.dirname(__file__), 'irregular_verbs.txt')

    irregular_verbs = {}
    try:
        with open(irregular_verbs_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                forms = [form.strip().lower() for form in line.split(';')]
                if forms:
                    # La primera forma es la base
                    base_form = forms[0]
                    # Todas las formas se mapean a todas las otras
                    for form in forms:
                        if form not in irregular_verbs:
                            irregular_verbs[form] = set(forms)
    except Exception:
        pass

    _IRREGULAR_VERBS_CACHE = irregular_verbs
    return irregular_verbs


def approximate_text_form(example_text: str, suggested_text_form: str) -> str:
    """
    Aproxima la forma correcta del text_form basada en cómo aparece en el texto del ejemplo.
    Usa LemmInflect y diccionario de verbos irregulares para generar todas las inflexiones.

    Args:
        example_text: El texto completo del ejemplo
        suggested_text_form: La forma sugerida por IA (puede ser incorrecta)

    Returns:
        La forma más aproximada encontrada en el texto, o la sugerida si no se puede mejorar
    """
    if not suggested_text_form or not suggested_text_form.strip():
        return ""

    import re

    text_lower = example_text.lower()
    suggested_lower = suggested_text_form.lower()

    # 1. Buscar match exacto con límites de palabra (case-insensitive)
    exact_pattern = r'\b' + re.escape(suggested_lower) + r'\b'
    match = re.search(exact_pattern, text_lower)
    if match:
        return example_text[match.start():match.end()]

    # 2. Si no hay match exacto, intentar aproximar
    words = suggested_lower.split()

    # Filtrar artículos comunes (a, an, the) que pueden no estar en el texto
    # pero dejar las otras palabras
    articles = {'a', 'an', 'the'}
    words_without_articles = [w for w in words if w not in articles]

    # Si después de filtrar artículos quedan palabras, usar esas
    # Si no, usar las palabras originales
    if words_without_articles:
        words = words_without_articles

    if len(words) == 1:
        # Palabra única: generar todas las inflexiones posibles
        word = words[0]
        possible_forms = {word}  # Incluir la forma original

        # Obtener formas del diccionario de verbos irregulares
        irregular_verbs = load_irregular_verbs()
        if word in irregular_verbs:
            possible_forms.update(irregular_verbs[word])

        try:
            # Obtener todas las inflexiones con LemmInflect
            inflections = getAllInflections(word)
            if inflections:
                for form_list in inflections.values():
                    possible_forms.update(form_list)
        except Exception:
            pass

        # Buscar las inflexiones en el texto
        # Preferir exacto primero
        for form in possible_forms:
            if form and form.lower() == word:
                pattern = r'\b' + re.escape(form) + r'\b'
                match = re.search(pattern, text_lower)
                if match:
                    return example_text[match.start():match.end()]

        # Si no hay exacto, buscar todas las inflexiones y retornar la más larga encontrada
        # Esto asegura que "dreams" se retorne antes que "dream", y "dreaming" antes que "dream"
        found_matches = []
        sorted_forms = sorted(possible_forms, key=len, reverse=True)
        for form in sorted_forms:
            if form:
                pattern = r'\b' + re.escape(form) + r'\b'
                match = re.search(pattern, text_lower)
                if match:
                    found_matches.append(
                        (len(form), match.start(), match.end(), example_text[match.start():match.end()]))

        if found_matches:
            # Retornar el match más largo encontrado
            found_matches.sort(reverse=True)
            return found_matches[0][3]

        # Fallback: patrón regex si nada encontrado
        pattern = r'\b' + re.escape(word) + r'[a-z]*\b'
        match = re.search(pattern, text_lower)
        if match:
            return example_text[match.start():match.end()]
    else:
        # Frase múltiple: intentar encontrar los componentes en orden
        found_positions = []
        irregular_verbs = load_irregular_verbs()

        for word in words:
            possible_forms = {word}

            # Obtener formas del diccionario de verbos irregulares
            if word in irregular_verbs:
                possible_forms.update(irregular_verbs[word])

            try:
                inflections = getAllInflections(word)
                if inflections:
                    for form_list in inflections.values():
                        possible_forms.update(form_list)
            except Exception:
                pass

            # Buscar todas las formas y retornar la más larga encontrada
            sorted_forms = sorted(possible_forms, key=len, reverse=True)
            best_match = None
            best_length = 0
            for form in sorted_forms:
                if form:
                    pattern = r'\b' + re.escape(form) + r'\b'
                    match = re.search(pattern, text_lower)
                    if match and len(form) > best_length:
                        best_match = (match.start(), match.end(),
                                      example_text[match.start():match.end()])
                        best_length = len(form)

            if best_match:
                found_positions.append(best_match)

        # Si encontramos al menos una palabra
        if found_positions:
            # Si encontramos todas o la mayoría, reconstruir la frase
            if len(found_positions) >= max(1, len(words) - 1):
                # Ordenar por posición en el texto
                found_positions.sort(key=lambda x: x[0])

                # Si los matches están consecutivos (sin grandes gaps), recuperar todo
                first_start = found_positions[0][0]
                last_end = found_positions[-1][1]

                # Verificar que no hay demasiado espacio entre ellos
                gap = last_end - first_start
                expected_length = sum(
                    len(form) for _, _, form in found_positions) + (len(found_positions) - 1) * 2

                if gap <= expected_length * 1.5:  # Permitir espacios y palabras pequeñas entre ellas
                    reconstructed = example_text[first_start:last_end].strip()
                    return reconstructed

            # Si solo encontramos una palabra, devolver esa
            if len(found_positions) == 1:
                return found_positions[0][2]

    # 3. Si no se puede aproximar, devolver la sugerencia original
    return suggested_text_form
