import re
import unicodedata
from difflib import SequenceMatcher
from typing import Tuple

class DynamicWakeWordMatcher:
    def __init__(self, threshold: float = 0.72):
        self.threshold = threshold

    def normalize_phonetic(self, text: str) -> str:
        """
        Normaliza el texto a minúsculas, remueve acentos/puntuación
        y aplica transformaciones fonéticas aproximadas en español/inglés.
        """
        if not text:
            return ""
        # 1. Quitar acentos y caracteres especiales
        normalized = unicodedata.normalize("NFD", text.lower().strip())
        clean_text = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        clean_text = re.sub(r'[^\w\s]', '', clean_text)
        
        # 2. Mapeos fonéticos equivalentes en español/inglés
        phonetic_text = clean_text
        phonetic_text = re.sub(r'[v]', 'b', phonetic_text)
        phonetic_text = re.sub(r'[c|q|k]', 'k', phonetic_text)
        phonetic_text = re.sub(r'[z|s]', 's', phonetic_text)
        phonetic_text = re.sub(r'[g|j]', 'j', phonetic_text)
        phonetic_text = re.sub(r'[h]', '', phonetic_text)  # H muda
        phonetic_text = re.sub(r'\s+', ' ', phonetic_text).strip()
        
        return phonetic_text

    def check_and_extract(self, text: str, target_wake_word: str) -> Tuple[bool, str]:
        """
        Verifica si el texto de la transcripción contiene la palabra de activación deseada
        (o una variante fonética/fuzzy similar) al inicio o dentro de la frase.
        
        Retorna:
        - bool: True si se detectó la palabra de activación.
        - str: El texto limpio removiendo la palabra de activación detectada.
        """
        if not text or not target_wake_word:
            return False, text

        # Si la transcripción completa coincide exactamente
        norm_text = self.normalize_phonetic(text)
        norm_target = self.normalize_phonetic(target_wake_word)
        
        if not norm_target:
            return False, text

        words = norm_text.split()
        target_words = norm_target.split()
        target_word_count = len(target_words)

        if not words:
            return False, text

        # Probar subfrases n-grama desde el inicio del texto
        # Probamos combinaciones de longitud: target_word_count y target_word_count + 1
        for n in range(target_word_count, min(len(words) + 1, target_word_count + 2)):
            ngram = " ".join(words[:n])
            ratio = SequenceMatcher(None, ngram, norm_target).ratio()
            
            if ratio >= self.threshold:
                # Extraer la palabra de activación del texto original
                # Buscamos la posición aproximada en las palabras originales
                orig_words = text.strip().split()
                remaining_words = orig_words[n:]
                clean_extracted_text = " ".join(remaining_words).lstrip(" ,.:;!?")
                return True, clean_extracted_text

        # Buscar si el wakeword está en cualquier parte de la frase (por ejemplo con prefijos de duda)
        for i in range(len(words)):
            for n in range(target_word_count, min(len(words) - i + 1, target_word_count + 2)):
                ngram = " ".join(words[i:i+n])
                ratio = SequenceMatcher(None, ngram, norm_target).ratio()
                if ratio >= self.threshold:
                    orig_words = text.strip().split()
                    remaining_words = orig_words[i+n:]
                    clean_extracted_text = " ".join(remaining_words).lstrip(" ,.:;!?")
                    return True, clean_extracted_text

        return False, text

wake_word_matcher = DynamicWakeWordMatcher()
