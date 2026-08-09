from abc import ABC, abstractmethod
from typing import List, Any
import random


class GenerationStrategy(ABC):

    CONTENT_TYPE = None
    MIN_QUEUE_THRESHOLD = 5

    @abstractmethod
    def get_pending_items(self) -> List[Any]:
        """Devuelve lista de items pendientes (nunca None)"""
        pass

    @abstractmethod
    def enqueue_generated_items(self):
        pass

    @abstractmethod
    def get_available_words(self) -> List[Any]:
        """Devuelve lista de palabras disponibles (nunca None)"""
        pass

    @abstractmethod
    def trigger_generation(self, words):
        pass

    @abstractmethod
    def resolve_completed(self):
        pass

    @abstractmethod
    def is_generating(self) -> bool:
        pass

    def shuffle(self, items):
        if not items:
            return items
        random.shuffle(items)
        return items

    def need_more(self, required, available):
        return available < required
