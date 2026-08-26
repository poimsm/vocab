from lemminflect import getAllInflections
import re

# Intenta cargar NLTK para lematización, fallback a diccionario si no está disponible
try:
    from nltk.stem import WordNetLemmatizer
    _lemmatizer = WordNetLemmatizer()
    _has_nltk = True
except ImportError:
    _has_nltk = False
    _lemmatizer = None

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


def _get_all_forms_for_word(word: str) -> set:
    """
    Obtiene todas las formas posibles de una palabra (inflexiones).
    Intenta primero con lemminflect, luego con diccionario de irregulares.
    """
    possible_forms = {word}  # Incluir la forma original

    # 1. Intentar con LemmInflect
    try:
        inflections = getAllInflections(word)
        if inflections:
            for form_list in inflections.values():
                possible_forms.update(form_list)
    except Exception:
        pass

    # 2. Fallback: diccionario de verbos irregulares
    irregular_verbs = load_irregular_verbs()
    if word in irregular_verbs:
        possible_forms.update(irregular_verbs[word])

    return possible_forms


def _find_word_in_text(word: str, text_lower: str, example_text: str) -> tuple:
    """
    Busca una palabra (y sus inflexiones) en el texto.
    Retorna (matched_text, start_pos, end_pos) o (None, -1, -1) si no encuentra.
    Prioriza el match más largo.
    """
    possible_forms = _get_all_forms_for_word(word)

    # Ordenar por longitud descendente para preferir matches más largos
    sorted_forms = sorted(possible_forms, key=len, reverse=True)

    best_match = None
    best_length = 0

    for form in sorted_forms:
        if form:
            pattern = r'\b' + re.escape(form) + r'\b'
            match = re.search(pattern, text_lower)
            if match and len(form) > best_length:
                best_match = (example_text[match.start():match.end()], match.start(), match.end())
                best_length = len(form)

    return best_match if best_match else (None, -1, -1)


def _get_lemma(word: str) -> str:
    """
    Obtiene el lema (forma base) de una palabra.
    Intenta primero con NLTK, luego con diccionario de irregulares.
    """
    # 1. Intentar con NLTK WordNetLemmatizer
    if _has_nltk and _lemmatizer:
        try:
            # Intentar como verbo primero, luego como sustantivo
            lemma_verb = _lemmatizer.lemmatize(word, pos='v')
            if lemma_verb != word:
                return lemma_verb

            lemma_noun = _lemmatizer.lemmatize(word, pos='n')
            if lemma_noun != word:
                return lemma_noun

            # Fallback: lematizar sin POS
            lemma = _lemmatizer.lemmatize(word)
            if lemma:
                return lemma
        except Exception:
            pass

    # 2. Fallback: usar diccionario de verbos irregulares
    irregular_verbs = load_irregular_verbs()
    if word in irregular_verbs:
        # Retornar la forma base (primera en el conjunto)
        forms = irregular_verbs[word]
        # La primera forma en el diccionario es la base
        return sorted(forms)[0]

    # 3. Si todo falla, devolver la palabra original
    return word


def approximate_text_form(example_text: str, suggested_text_form: str) -> str:
    """
    Aproxima la forma correcta del text_form basada en cómo aparece en el texto del ejemplo.

    Estrategia:
    1. Busca match exacto
    2. Para palabras simples: lematiza, compara lemas, y busca la forma real en texto
    3. Para frases: busca las palabras componentes

    Usa lemminflect como primera opción y diccionario de irregulares como fallback.

    Args:
        example_text: El texto completo del ejemplo
        suggested_text_form: La forma sugerida (puede ser lema o forma flexionada)

    Returns:
        La forma encontrada en el texto, o suggested_text_form si no se puede aproximar
    """
    if not suggested_text_form or not suggested_text_form.strip():
        return ""

    text_lower = example_text.lower()
    suggested_lower = suggested_text_form.lower()

    # 1. Buscar match exacto con límites de palabra
    exact_pattern = r'\b' + re.escape(suggested_lower) + r'\b'
    match = re.search(exact_pattern, text_lower)
    if match:
        return example_text[match.start():match.end()]

    # 2. Procesar según si es palabra simple o frase
    words = suggested_lower.split()

    # Filtrar artículos comunes que podrían no estar en el texto
    articles = {'a', 'an', 'the'}
    words_without_articles = [w for w in words if w not in articles]

    if words_without_articles:
        words = words_without_articles

    if len(words) == 1:
        # === CASO: PALABRA ÚNICA ===
        word = words[0]

        # Obtener el lema de la palabra sugerida
        base_lemma = _get_lemma(word)

        # Buscar cualquier forma del lema en el texto
        matched_text, _, _ = _find_word_in_text(base_lemma, text_lower, example_text)
        if matched_text:
            return matched_text

        # Si el lema no se encuentra, intentar con la palabra original
        matched_text, _, _ = _find_word_in_text(word, text_lower, example_text)
        if matched_text:
            return matched_text

    else:
        # === CASO: FRASE MÚLTIPLE ===
        found_positions = []

        for word in words:
            # Lematizar la palabra
            base_lemma = _get_lemma(word)

            # Intentar encontrar cualquier forma del lema
            matched_text, start, end = _find_word_in_text(base_lemma, text_lower, example_text)
            if not matched_text:
                # Si no encuentra el lema, intentar con la palabra original
                matched_text, start, end = _find_word_in_text(word, text_lower, example_text)

            if matched_text:
                found_positions.append((start, end, matched_text))

        # Si encontramos al menos una palabra o la mayoría
        if found_positions:
            if len(found_positions) >= max(1, len(words) - 1):
                # Ordenar por posición en el texto
                found_positions.sort(key=lambda x: x[0])

                # Recuperar el segmento del texto entre la primera y última palabra encontrada
                first_start = found_positions[0][0]
                last_end = found_positions[-1][1]

                # Verificar que no hay demasiado espacio entre ellos
                gap = last_end - first_start
                expected_length = sum(len(m[2]) for m in found_positions) + (len(found_positions) - 1) * 2

                if gap <= expected_length * 1.5:
                    reconstructed = example_text[first_start:last_end].strip()
                    return reconstructed

            # Si solo encontramos una palabra, devolver esa
            if len(found_positions) == 1:
                return found_positions[0][2]

    # 3. Fallback: devolver la sugerencia original
    return suggested_text_form
