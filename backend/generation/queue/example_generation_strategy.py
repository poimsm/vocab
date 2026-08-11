from sqlmodel import Session
from examples import repository as ExampleRepository
from examples import generator as ExampleGenerator
from words import repository as WordRepository

from generation.queue import repository as QueueRepository
from generation.queue.generation_strategy import GenerationStrategy
from models import ContentType
from batch_manager import BatchManager
from config_manager import ConfigManager


class ExampleGenerationStrategy(GenerationStrategy):

    CONTENT_TYPE = ContentType.EXAMPLE

    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id
        self.batch_manager = BatchManager(db)
        self.config_manager = ConfigManager(db)

    def get_pending_items(self):
        return QueueRepository.pending(self.db, self.CONTENT_TYPE, self.user_id)

    def enqueue_generated_items(self):
        threshold = self.config_manager.get_threshold_for_transition()

        generated = self.batch_manager.get_content_items_for_queue(
            user_id=self.user_id,
            content_type=self.CONTENT_TYPE,
            limit=threshold
        )

        if generated:
            QueueRepository.enqueue(
                self.db,
                self.CONTENT_TYPE,
                self.user_id,
                generated
            )

            example_ids = [item.id for item in generated]
            ExampleRepository.mark_as_not_pristine(self.db, example_ids)

    def get_available_words(self):
        return WordRepository.available(self.db, self.CONTENT_TYPE, self.user_id)

    def trigger_generation(self, words):
        # Pasar solo IDs de palabras (serializables) en lugar de objetos ORM
        word_ids = [w.id for w in words] if words else []
        ExampleGenerator.generate.delay(self.user_id, word_ids)

    def resolve_completed(self):
        from logging_client import logger
        try:
            pending = QueueRepository.pending(self.db, self.CONTENT_TYPE, self.user_id)
            logger.debug(f"[ExampleStrategy] Checking {len(pending)} pending items for completion")

            if not isinstance(pending, list):
                return

            for item in pending:
                if not hasattr(item, 'id') or not hasattr(item, 'content_id'):
                    continue

                words = ExampleRepository.get_words(self.db, item.content_id)

                if WordRepository.are_learned(self.db, words, self.CONTENT_TYPE):
                    QueueRepository.mark_resolved(self.db, item.id)
                    logger.debug(f"[ExampleStrategy] Marked queue item {item.id} as resolved (all words learned)")
        except Exception as e:
            logger.error(f"[ExampleStrategy.resolve_completed] Error: {e}", exc_info=True)

    def is_generating(self):
        return QueueRepository.is_generating(self.db, self.CONTENT_TYPE, self.user_id)
