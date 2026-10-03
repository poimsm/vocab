# backend/features/examples/generator.py
from typing import List, Optional
from sqlmodel import Session
from logging_client import logger

from core.generation_ai.repository import GenerationAIRepository


class ExampleGenerator:
    """
    Centraliza la solicitud de generación de ejemplos usando el repositorio core.
    """

    @staticmethod
    def generate_simple(
        user_id: int,
        word_ids: List[int],
        amount: int = 1,
        pre_generated_examples: dict = None,
        session: Optional[Session] = None,
        content_source_type: str = "learning_path",
    ):
        """
        Solicita la generación de ejemplos simples agregando la tarea a GeneratorQueue
        a través del GenerationAIRepository.
        """
        if not word_ids:
            logger.warning(f"[ExampleGenerator] No words provided for user {user_id}")
            return

        close_session = False
        if session is None:
            from db import engine
            session = Session(engine)
            close_session = True

        try:
            payload = {
                "user_id": user_id,
                "word_ids": word_ids,
                "amount": amount,
                "pre_generated_examples": pre_generated_examples,
                "content_source_type": content_source_type,
            }

            logger.info(
                f"[ExampleGenerator] Queueing generation for {len(word_ids)} words (user={user_id})"
            )

            # Instanciar repositorio y delegar la creación
            gen_repo = GenerationAIRepository(session)
            queue_item = gen_repo.create_queue_item(
                payload=payload,
                process_event="event.generation.content_requested",
                callback_event="event.generation.examples_completed",
            )

            logger.info(
                f"[ExampleGenerator] Generation queued successfully (queue_id={queue_item.id})"
            )

        except Exception as e:
            logger.error(
                f"[ExampleGenerator] Error queuing generation: {e}",
                exc_info=True,
            )
            session.rollback()

        finally:
            if close_session:
                session.close()