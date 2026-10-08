# backend/features/examples/generator.py
from typing import List, Optional
from sqlmodel import Session
from logging_client import logger

from core.generation_ai.repository import GenerationAIRepository
from core.enums import ContentSourceType, ContentType


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
        content_source_type: str = ContentSourceType.LEARNING_PATH.value,
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
            # Convertir content_source_type string a enum
            source_type_enum = ContentSourceType(content_source_type)

            payload = {
                "user_id": user_id,
                "word_ids": word_ids,
                "amount": amount,
                "pre_generated_examples": pre_generated_examples,
                "content_source_type": content_source_type,
            }

            logger.info(
                f"[ExampleGenerator] Queueing generation for {len(word_ids)} words (user={user_id}), "
                f"source_type={source_type_enum.value}"
            )

            # Instanciar repositorio y delegar la creación
            gen_repo = GenerationAIRepository(session)
            queue_item_id = gen_repo.create_queue_item(
                user_id=user_id,
                word_id=word_ids[0],  # Usar el primer word_id para el registro
                source_type=source_type_enum,
                content_type=ContentType.EXAMPLE,
                payload=payload,
                process_event="event.generation.content_requested",
                callback_event="event.generation.examples_completed",
            )

            logger.info(
                f"[ExampleGenerator] Generation queued successfully (queue_id={queue_item_id})"
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