from language_tool_python import LanguageTool
from langdetect import detect, DetectorFactory
from logging_client import logger
from typing import List, Dict, Any
import nltk
from nltk.corpus import stopwords, wordnet
from nltk.tokenize import word_tokenize
import re

# Establecer seed para langdetect para resultados consistentes
DetectorFactory.seed = 0

# Descargar recursos necesarios de NLTK si no existen
try:
    stopwords.words('english')
except LookupError:
    nltk.download('stopwords')
    nltk.download('wordnet')
    nltk.download('punkt')
    nltk.download('averaged_perceptron_tagger')


class GrammarEngine:
    """Motor de gramática para revisar y corregir textos en inglés"""

    def __init__(self):
        """Inicializa el motor de gramática con LanguageTool para inglés"""
        try:
            self.tool = LanguageTool('en-US')
            logger.info("[GrammarEngine] Initialized with LanguageTool for en-US")
        except Exception as e:
            logger.error(f"[GrammarEngine] Error initializing LanguageTool: {e}")
            self.tool = None

        # Caché para palabras ya verificadas en WordNet
        self._english_word_cache = {}

    def detect_language(self, text: str) -> str:
        """
        Detecta el idioma del texto usando langdetect

        Args:
            text: Texto a analizar

        Returns:
            Código de idioma detectado (ej: 'en', 'es', 'fr')
        """
        try:
            if not text.strip():
                return "unknown"

            lang = detect(text)
            logger.debug(f"[GrammarEngine] Detected language: {lang}")
            return lang
        except Exception as e:
            logger.warning(f"[GrammarEngine] Error detecting language: {e}")
            return "unknown"

    def is_english(self, text: str, threshold: float = 0.5) -> bool:
        """
        Verifica si el texto está en inglés

        Args:
            text: Texto a analizar
            threshold: Confianza mínima (0-1) para considerar que es inglés

        Returns:
            True si el idioma detectado es inglés, False en caso contrario
        """
        try:
            if not text.strip():
                return False

            lang = self.detect_language(text)
            is_en = lang == 'en'
            logger.debug(f"[GrammarEngine] Is English: {is_en} (detected: {lang})")
            return is_en
        except Exception as e:
            logger.warning(f"[GrammarEngine] Error checking if English: {e}")
            return False

    def check_grammar(self, text: str) -> List[Dict[str, Any]]:
        """
        Revisa la gramática del texto y retorna errores encontrados

        Args:
            text: Texto a revisar (debe estar en inglés)

        Returns:
            Lista de errores encontrados con detalles
        """
        if not self.tool:
            logger.warning("[GrammarEngine] LanguageTool not initialized")
            return []

        try:
            if not text.strip():
                return []

            matches = self.tool.check(text)
            errors = []

            for match in matches:
                error = {
                    "message": match.message,
                    "offset": match.offset,
                    "length": match.length,
                    "category": match.category,
                    "rule_id": match.ruleId,
                    "replacements": match.replacements[:3] if match.replacements else []
                }
                errors.append(error)

            logger.debug(f"[GrammarEngine] Found {len(errors)} grammar errors")
            return errors

        except Exception as e:
            logger.error(f"[GrammarEngine] Error checking grammar: {e}")
            return []

    def correct_text(self, text: str) -> str:
        """
        Corrige automáticamente los errores de gramática encontrados

        Args:
            text: Texto a corregir (debe estar en inglés)

        Returns:
            Texto corregido
        """
        if not self.tool:
            logger.warning("[GrammarEngine] LanguageTool not initialized")
            return text

        try:
            if not text.strip():
                return text

            corrected = self.tool.correct(text)
            logger.debug(f"[GrammarEngine] Text corrected")
            return corrected

        except Exception as e:
            logger.error(f"[GrammarEngine] Error correcting text: {e}")
            return text

    def get_error_count(self, text: str) -> int:
        """
        Obtiene el número total de errores gramáticales

        Args:
            text: Texto a analizar

        Returns:
            Número de errores encontrados
        """
        errors = self.check_grammar(text)
        return len(errors)

    def has_errors(self, text: str) -> bool:
        """
        Verifica si el texto tiene errores gramáticales

        Args:
            text: Texto a verificar

        Returns:
            True si hay errores, False en caso contrario
        """
        return self.get_error_count(text) > 0

    def detect_english_with_tolerance(self, text: str, confidence_threshold: float = 0.5) -> Dict[str, Any]:
        """
        Detecta si el texto es inglés con flexibilidad ante errores gramaticales e idiomas mixtos.
        Usa NLTK para analizar palabras. Optimizado para velocidad: solo procesa primeras N palabras
        y cachea resultados.

        Args:
            text: Texto a analizar
            confidence_threshold: Porcentaje mínimo (0-1) de palabras en inglés para considerar que es inglés

        Returns:
            Diccionario con:
            - is_english: bool - True si el porcentaje de palabras en inglés >= threshold
            - confidence: float - Porcentaje de confianza (0-1) basado en palabras identificadas
            - english_words_count: int - Número de palabras identificadas como inglés
            - total_words: int - Número total de palabras analizadas
            - english_words_percentage: float - Porcentaje de palabras en inglés
        """
        try:
            if not text.strip():
                return {
                    "is_english": False,
                    "confidence": 0.0,
                    "english_words_count": 0,
                    "total_words": 0,
                    "english_words_percentage": 0.0
                }

            # Limpiar y normalizar texto
            cleaned_text = re.sub(r'[^a-zA-Z\s]', ' ', text).lower()

            # Tokenizar
            tokens = word_tokenize(cleaned_text)
            # Filtrar palabras vacías y muy cortas (1-2 caracteres)
            words = [w for w in tokens if len(w) > 2 and w.isalpha()]

            if not words:
                return {
                    "is_english": False,
                    "confidence": 0.0,
                    "english_words_count": 0,
                    "total_words": 0,
                    "english_words_percentage": 0.0
                }

            # Obtener stopwords en inglés
            english_stopwords = set(stopwords.words('english'))

            # Limitar a primeras 100 palabras para velocidad
            words_to_check = words[:100]
            english_word_count = 0

            for word in words_to_check:
                # Verificar caché primero
                if word in self._english_word_cache:
                    if self._english_word_cache[word]:
                        english_word_count += 1
                    continue

                is_english_word = False

                # 1. Verificar si es stopword en inglés (confianza alta)
                if word in english_stopwords:
                    is_english_word = True
                # 2. Verificar si existe en WordNet como palabra inglesa
                elif wordnet.synsets(word, lang='eng'):
                    is_english_word = True
                # 3. Heurística: palabras con terminaciones comunes inglesas
                elif word.endswith(('s', 'ed', 'ing', 'er', 'ly', 'tion')):
                    is_english_word = True

                # Cachear resultado
                self._english_word_cache[word] = is_english_word

                if is_english_word:
                    english_word_count += 1

            # Calcular porcentaje de confianza
            total_words = len(words_to_check)
            confidence = english_word_count / total_words if total_words > 0 else 0.0
            english_words_percentage = round(confidence * 100, 2)

            result = {
                "is_english": confidence >= confidence_threshold,
                "confidence": round(confidence, 3),
                "english_words_count": english_word_count,
                "total_words": total_words,
                "english_words_percentage": english_words_percentage
            }

            logger.debug(
                f"[GrammarEngine] English detection with tolerance: "
                f"confidence={result['confidence']}, "
                f"english_words={english_word_count}/{total_words}"
            )
            return result

        except Exception as e:
            logger.error(f"[GrammarEngine] Error detecting English with tolerance: {e}")
            return {
                "is_english": False,
                "confidence": 0.0,
                "english_words_count": 0,
                "total_words": 0,
                "english_words_percentage": 0.0
            }
        
    def detect_english_regex(self, text: str) -> bool:
        """
        Detecta si el texto es inglés usando patrones regex sin librerías externas.
        Busca: terminaciones comunes, palabras funcionales, contracciones tipicas del inglés.

        Args:
            text: Texto a analizar

        Returns:
            True si el texto contiene suficientes patrones de inglés, False en caso contrario
        """
        if not text or len(text.strip()) < 5:
            return False

        text_lower = text.lower()
        pattern_matches = 0

        # Patrones de palabras funcionales muy comunes en inglés
        common_english_words = [
            r'\b(the|and|is|are|was|were|be|have|has|do|does|did|will|would|can|could|should|may|might)\b',
            r'\b(i|you|he|she|it|we|they|me|him|her|us|them)\b',
            r'\b(a|an|in|on|at|to|for|with|from|by|of|or|not|but|if|that|this|which)\b',
        ]

        for pattern in common_english_words:
            matches = len(re.findall(pattern, text_lower))
            pattern_matches += matches

        # Patrones de terminaciones típicas del inglés
        ending_patterns = [
            (r'\w+ing\b', 15),      # -ing (verbos/gerundios): running, making, thinking
            (r'\w+ed\b', 10),       # -ed (pasado): walked, played, wanted
            (r'\w+er\b', 8),        # -er (comparativo/agente): better, teacher, player
            (r'\w+ly\b', 8),        # -ly (adverbios): quickly, slowly, carefully
            (r'\w+tion\b', 15),     # -tion (sustantivos): action, nation, creation
            (r'\w+ness\b', 12),     # -ness (sustantivos abstractos): happiness, kindness
            (r'\w+ment\b', 12),     # -ment (sustantivos): movement, development
            (r'\w+able\b', 12),     # -able (adjetivos): readable, comfortable
            (r'\w+ful\b', 10),      # -ful (adjetivos): beautiful, wonderful
            (r'\w+less\b', 10),     # -less (adjetivos): homeless, careless
            (r'\w+ous\b', 10),      # -ous (adjetivos): dangerous, famous
            (r'\w+ive\b', 8),       # -ive (adjetivos): active, creative
            (r'\w+ish\b', 8),       # -ish (adjetivos): foolish, English
        ]

        for pattern, weight in ending_patterns:
            matches = len(re.findall(pattern, text_lower))
            pattern_matches += matches * (weight / 10)

        # Contracciones típicas del inglés
        contractions = [
            r"'s\b",      # 's (is, has, possessive): it's, she's, John's
            r"'t\b",      # 't (not): don't, can't, won't
            r"'re\b",     # 're (are): we're, they're
            r"'ve\b",     # 've (have): I've, we've
            r"'ll\b",     # 'll (will): I'll, he'll
            r"'d\b",      # 'd (would, had): I'd, she'd
        ]

        for pattern in contractions:
            matches = len(re.findall(pattern, text_lower))
            pattern_matches += matches * 2  # Las contracciones son muy específicas del inglés

        # Calcular proporción de palabras que contienen patrones de inglés
        # (no contar coincidencias acumuladas, sino palabras únicas con patrones)
        words = text.split()
        word_count = len(words)

        if word_count == 0:
            return False

        # Compilar todos los patrones en un solo regex para eficiencia
        all_patterns = (
            r'\b(the|and|is|are|was|were|be|have|has|do|does|did|will|would|can|could|should|may|might|'
            r'i|you|he|she|it|we|they|me|him|her|us|them|'
            r'a|an|in|on|at|to|for|with|from|by|of|or|not|but|if|that|this|which)\b|'
            r"(\w+ing|\w+ed|\w+er|\w+ly|\w+tion|\w+ness|\w+ment|\w+able|\w+ful|\w+less|\w+ous|\w+ive|\w+ish)\b|"
            r"('s|'t|'re|'ve|'ll|'d)\b"
        )

        words_with_pattern = 0
        for word in words:
            if re.search(all_patterns, word.lower()):
                words_with_pattern += 1

        # Proporción de palabras con patrón de inglés
        english_proportion = words_with_pattern / word_count

        logger.debug(
            f"[GrammarEngine] English regex detection: "
            f"words_with_pattern={words_with_pattern}, total_words={word_count}, "
            f"proportion={english_proportion:.2%}"
        )

        # Threshold: al menos 40% de las palabras deben tener patrón de inglés
        return english_proportion >= 0.20
