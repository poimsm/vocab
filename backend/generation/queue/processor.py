from logging_client import logger
import traceback

class GenerationProcessor:

    def __init__(self, db, user_id, strategy_class):
        """
        Inicializa el procesador de generación.

        Args:
            db: Sesión de la base de datos
            user_id: ID del usuario
            strategy_class: Clase de estrategia (ej: ExampleGenerationStrategy)
        """
        self.db = db
        self.user_id = user_id
        self.strategy = strategy_class(db, user_id)

    def process(self, required_count):
        try:
            if self.strategy.is_generating():
                return {"status": "generating", "items": []}

            self.strategy.resolve_completed()

            current_items = self.strategy.get_pending_items()

            if len(current_items) < self.strategy.MIN_QUEUE_THRESHOLD:
                self.strategy.enqueue_generated_items()

            items = self.strategy.get_pending_items()

            if not items:
                words = self.strategy.get_available_words()
                if words:
                    self.strategy.trigger_generation(words)
                    return {"status": "generating", "items": []}
                return {"status": "no_words", "items": []}

            items = self.strategy.shuffle(items)

            if self.strategy.need_more(required_count, len(items)):
                if len(items) < self.strategy.MIN_QUEUE_THRESHOLD:
                    self.strategy.enqueue_generated_items()

                items = self.strategy.get_pending_items()
                items = self.strategy.shuffle(items)

                if not self.strategy.need_more(required_count, len(items)):
                    return {"status": "ok", "items": items[:required_count]}

                words = self.strategy.get_available_words()
                if words:
                    self.strategy.trigger_generation(words)
                    return {"status": "generating", "items": []}

                return {"status": "no_words", "items": []}

            return {"status": "ok", "items": items[:required_count]}
        except Exception as e:
            full_traceback = traceback.format_exc()
            logger.error(f"[GenerationProcessor.process] FULL STACKTRACE:\n{full_traceback}")
            logger.error(f"[GenerationProcessor.process] Error type: {type(e).__name__}")
            logger.error(f"[GenerationProcessor.process] Error message: {str(e)}")

            error_type = type(e).__name__
            error_msg = str(e)
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."

            return {"status": "error", "items": [], "error_detail": f"{error_type}: {error_msg}"}
