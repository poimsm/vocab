from sqlmodel import Session
from best_options import generator as BestOptionsGenerator
from words import repository as WordRepository
from generation.queue import repository as QueueRepository
from generation.queue.generation_strategy import GenerationStrategy
from models import ContentType
from best_options import repository as BestOptionsRepository


class BestOptionGenerationStrategy(GenerationStrategy):

    CONTENT_TYPE = ContentType.BEST_OPTIONS

    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id

    def get_pending_items(self):
        return QueueRepository.pending(self.db, self.CONTENT_TYPE, self.user_id)

    def enqueue_generated_items(self):
        generated = BestOptionsRepository.available_for_queue(self.db)
        
        if generated:
            QueueRepository.enqueue(
                self.db,
                self.CONTENT_TYPE,
                self.user_id,
                generated
            )

    def get_available_words(self):
        return WordRepository.available(self.db, self.CONTENT_TYPE, self.user_id)

    def trigger_generation(self, words):
        # Pasar solo IDs de palabras (serializables) en lugar de objetos ORM
        word_ids = [w.id for w in words] if words else []
        BestOptionsGenerator.generate.delay(self.user_id, word_ids)

    def resolve_completed(self):
        from logging_client import logger
        try:
            pending = QueueRepository.pending(self.db, self.CONTENT_TYPE, self.user_id)
            logger.debug(f"[BestOptionStrategy] Checking {len(pending)} pending items for completion")

            if not isinstance(pending, list):
                return

            for item in pending:
                if not hasattr(item, 'id') or not hasattr(item, 'content_id'):
                    continue

                words = BestOptionsRepository.get_words(self.db, item.content_id)

                if WordRepository.are_learned(self.db, words, self.CONTENT_TYPE):
                    QueueRepository.mark_resolved(self.db, item.id)
                    logger.debug(f"[BestOptionStrategy] Marked queue item {item.id} as resolved (all words learned)")
        except Exception as e:
            logger.error(f"[BestOptionStrategy.resolve_completed] Error: {e}", exc_info=True)

    def is_generating(self):
        return QueueRepository.is_generating(self.db, self.CONTENT_TYPE, self.user_id)
