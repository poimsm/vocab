"""
Tareas Celery para generación y exploración de best options.

Celery autodiscover busca módulos llamados 'tasks.py'.
"""

import random
import time
from typing import List, Optional
from sqlmodel import Session, select
from logging_client import logger
from celery_app import celery_app
from core.celery_queues import CeleryQueue
import ai
from features.best_options.repository import BestOptionRepository
from config import UserProfileManager
from core.enums import ContentType, ContentSourceType
from core.event_bus import publish_event_background, subscribe_to_ai
from core.generation_ai.enums import GenerationAIStatus
from features.best_options.response_builder import BestOptionsResponseBuilder
from core.delivery.service import DeliveryService


def _shuffle_options_with_correct_index(options: list, correct_option_idx: int) -> tuple:
    """
    Desordena una lista de opciones y retorna la lista desordenada
    junto con el nuevo índice de la opción correcta.
    """
    if not options or correct_option_idx >= len(options):
        return options, correct_option_idx

    shuffled_indices = random.sample(range(len(options)), len(options))
    shuffled_options = [options[i] for i in shuffled_indices]
    new_correct_idx = shuffled_indices.index(correct_option_idx)

    return shuffled_options, new_correct_idx


@subscribe_to_ai('generation.content_requested')
@celery_app.task(name="tasks.best_options.on_generation_requested", queue=CeleryQueue.AI)
def on_generation_requested_task(
    user_id: int,
    word_ids: List[int],
    content_type: str,
    queue_item_id: Optional[int] = None,
    content_source_type: str = "learning_path",
    **kwargs
) -> None:
    """
    Suscriptor al evento 'generation.content_requested'.
    Solo procesa requests para best_options, ignora otros tipos de contenido.
    """
    # Solo procesar si es para best_options
    if content_type != ContentType.BEST_OPTIONS.value:
        logger.debug(
            f"[BestOptionsGenerator] Skipping: content_type '{content_type}' is not BEST_OPTIONS. "
            f"This event is for BEST_OPTIONS content only."
        )
        return

    logger.info(
        f"[BestOptionsGenerator] Received generation request for best_options: "
        f"user_id={user_id}, word_ids={word_ids}, content_source_type={content_source_type}"
    )

    # Encolar la generación de best_options
    generate_best_options_task.apply_async(
        args=[user_id, word_ids],
        kwargs={
            "queue_item_id": queue_item_id,
            "content_source_type": content_source_type,
        },
        queue=CeleryQueue.AI,
    )

    logger.debug(
        f"[BestOptionsGenerator] Enqueued generation task for {len(word_ids)} words "
        f"(source_type={content_source_type})"
    )


@celery_app.task(name="tasks.best_options.generate", queue=CeleryQueue.AI)
def generate_best_options_task(
    user_id: int,
    word_ids: List[int],
    queue_item_id: Optional[int] = None,
    content_source_type: str = "learning_path",
    **kwargs
) -> None:
    """
    Genera ejercicios best_option para una lista de palabras usando IA.

    Args:
        user_id: ID del usuario (para logging)
        word_ids: Lista de IDs de palabras para las que generar ejercicios
        queue_item_id: ID del item en la queue (para tracking de generación)
        content_source_type: LEARNING_PATH o BOOST (default: LEARNING_PATH)
        **kwargs: Argumentos adicionales (para compatibilidad defensiva)
    """
    from db import engine
    from features.words.models import Word
    from features.best_options.models import BestOption

    logger.debug(
        f"[BestOptionsGenerator] Task started: user_id={user_id}, word_ids={word_ids}, "
        f"content_source_type={content_source_type}, queue_item_id={queue_item_id}"
    )

    # Log de kwargs inesperados (para debugging)
    if kwargs:
        logger.debug(f"[BestOptionsGenerator] Extra kwargs received: {kwargs}")

    if not word_ids:
        logger.warning(f"[BestOptionsGenerator] No words provided for user {user_id}")
        return

    logger.info(
        f"[BestOptionsGenerator] Generating best option exercises for {len(word_ids)} words "
        f"(user {user_id}, source: {content_source_type})"
    )

    # Extraer parámetro configurable de cantidad de preguntas
    questions_per_word = kwargs.get('questions_per_word', 5)
    logger.debug(f"[BestOptionsGenerator] Using questions_per_word={questions_per_word}")

    try:
        # Crear nueva sesión para la tarea
        with Session(engine) as db:
            # ✅ Validar cuota de best_options
            from config import QuotaValidator
            try:
                QuotaValidator.validate_max_best_options_per_user(db, user_id)
            except Exception as quota_error:
                logger.warning(
                    f"[BestOptionsGenerator] Quota exceeded for user {user_id}: {quota_error}"
                )
                return

            # Cargar palabras por sus IDs
            words = db.exec(
                select(Word).where(Word.id.in_(word_ids), Word.user_id == user_id)
            ).all()

            if not words:
                logger.warning(f"[BestOptionsGenerator] Words not found for user {user_id}")
                return

            # Filtrar palabras que realmente necesitan generación
            best_option_repo = BestOptionRepository(db)
            words_needing_generation = []

            for word in words:
                # Para BOOST content, siempre generar sin importar cantidad existente
                # Para LEARNING_PATH, solo generar si hay menos de 2 disponibles
                if content_source_type == ContentSourceType.BOOST.value:
                    words_needing_generation.append(word)
                    logger.debug(
                        f"[BestOptionsGenerator] Word {word.id} ({word.main}) queued for BOOST generation"
                    )
                else:
                    available_count = best_option_repo.count_available_best_options_for_word(word.id)
                    if available_count < 2:
                        words_needing_generation.append(word)
                    else:
                        logger.debug(
                            f"[BestOptionsGenerator] Word {word.id} ({word.main}) already has {available_count} available best options, skipping"
                        )

            if not words_needing_generation:
                logger.info(
                    f"[BestOptionsGenerator] No words need generation"
                )
                return

            # Generar ejercicios usando IA solo para palabras que lo necesitan
            logger.info(
                f"[BestOptionsGenerator] Generating for {len(words_needing_generation)} words that need exercises"
            )
            raw_best_options = ai.generate_best_options_from_words(words_needing_generation, questions_per_word=questions_per_word)

            if not raw_best_options:
                logger.warning(f"[BestOptionsGenerator] No exercises generated by AI for user {user_id}")
                return

            logger.info(f"[BestOptionsGenerator] AI generated {len(raw_best_options)} exercise sets")

            # Obtener el máximo sequence actual para continuar secuencia
            from sqlalchemy import func as sql_func
            max_sequence = db.exec(
                select(sql_func.max(BestOption.sequence))
            ).first() or 0

            sequence_counter = max_sequence + 1

            # Procesar cada set de ejercicios
            for exercise_set in raw_best_options:
                word_id = exercise_set.get("word_id")
                questions = exercise_set.get("questions", [])

                if not questions or not word_id:
                    logger.warning(f"[BestOptionsGenerator] Skipping exercise set for word {word_id} (no questions)")
                    continue

                # Crear un BestOption para cada pregunta
                for sequence_idx, question_data in enumerate(questions, start=1):
                    question_text = question_data.get("question")
                    options = question_data.get("options", [])
                    correct_option_idx = question_data.get("correct_option", 0)

                    if not question_text or not options:
                        logger.warning(f"[BestOptionsGenerator] Skipping question {sequence_idx} for word {word_id}")
                        continue

                    # Desordena las opciones
                    shuffled_options, new_correct_idx = _shuffle_options_with_correct_index(
                        options, correct_option_idx
                    )

                    # Crear la cadena de opciones separadas por ";"
                    options_string = ";".join(shuffled_options)

                    # Crear el BestOption en DB con sequence
                    best_option = BestOption(
                        word_id=word_id,
                        question=question_text,
                        options=options_string,
                        correct_option=new_correct_idx,
                        sequence=sequence_counter,
                        enqueued=False,
                    )
                    db.add(best_option)
                    db.flush()

                    sequence_counter += 1

            db.commit()

            # ✅ Agregar best_options a LearningPathQueue para que estén disponibles inmediatamente
            from core.learning_path.models import LearningPathQueue
            from core.learning_path.enums import LearningPathQueueStatus

            best_options_for_queue = db.exec(
                select(BestOption).where(
                    BestOption.sequence > max_sequence,
                    BestOption.word_id.in_(word_ids)
                )
            ).all()

            if best_options_for_queue:
                queue_items = []
                for best_option in best_options_for_queue:
                    queue_item = LearningPathQueue(
                        user_id=user_id,
                        content_type=ContentType.BEST_OPTIONS,
                        content_id=best_option.id,
                        word_id=best_option.word_id,
                        status=LearningPathQueueStatus.PENDING,
                        priority=0.5,
                    )
                    db.add(queue_item)
                    db.flush()  # Flush para obtener el ID generado
                    queue_items.append(queue_item)
                db.commit()
                logger.debug(
                    f"[BestOptionsGenerator] Added {len(best_options_for_queue)} best options to LearningPathQueue for user {user_id}"
                )

                # ✅ Publicar evento content.generated para cada best_option creado
                # Esto permitirá que el evento listener registre BOOST content al delivery buffer
                logger.debug(f"[BestOptionsGenerator] Publishing content.generated events for {len(queue_items)} best options")
                for best_option in best_options_for_queue:
                    publish_event_background(
                        'content.generated',
                        user_id=user_id,
                        word_id=best_option.word_id,
                        content_id=best_option.id,
                        queue_item_id=queue_item_id,
                        content_type=ContentType.BEST_OPTIONS.value,
                        content_source_type=content_source_type,
                        status=GenerationAIStatus.COMPLETED.value,
                    )
                logger.debug(
                    f"[BestOptionsGenerator] Published {len(queue_items)} content.generated events for user {user_id}"
                )

                # ✅ NO transferir a DeliveryBuffer inmediatamente para LEARNING_PATH
                # Para BOOST, el evento listener registrará al buffer automáticamente
                logger.debug(
                    f"[BestOptionsGenerator] Items left in PENDING status for user {user_id}. "
                    f"For LEARNING_PATH: will be transferred on-demand by DeliveryService using priority engine. "
                    f"For BOOST: event listener will register to delivery buffer."
                )

            # ✅ Contar best_options creados
            best_options_created = sequence_counter - max_sequence - 1
            if best_options_created > 0:
                UserProfileManager.increment_best_options(db, user_id, amount=best_options_created)
                logger.debug(
                    f"[BestOptionsGenerator] Counted {best_options_created} best options for user {user_id}"
                )

            # ✅ Marcar generación como completada en el monitor
            from core.learning_path.repository import LearningPathRepository
            learning_path_repo = LearningPathRepository(db)
            learning_path_repo.complete_generation_monitor(user_id, ContentType.BEST_OPTIONS)
            logger.debug(
                f"[BestOptionsGenerator] Marked generation as COMPLETED for user {user_id}"
            )

            logger.info(
                f"[BestOptionsGenerator] Successfully created best options for user {user_id}"
            )

    except Exception as e:
        logger.error(
            f"[BestOptionsGenerator] Error generating best options for user {user_id}: {e}",
            exc_info=True
        )


@celery_app.task(name="tasks.best_options.explore_best_options", queue=CeleryQueue.BACKGROUND)
def explore_best_options_task(
    user_id: int,
    request_id: str,
    actions: List[str],
    resolve_queue_item_id: Optional[int] = None,
    limit: int = 6,
    buffer_delivery_ids: List[int] = None,
    buffer_position: int = 0,
) -> None:
    """
    Task de background que procesa acciones de explore para best options y publica eventos en tiempo real.

    Flujo:
    1. Recibe solicitud de explore con acciones
    2. Ejecuta acciones usando ExploreActions
    3. Publica eventos en RealtimeEventBus para transmitir al frontend vía SSE
    4. Eventos: explore.started, explore.processing, explore.completed, explore.failed

    Los datos se transmiten en tiempo real a través de /explore-stream (SSE).
    """
    from core.realtime_event_bus import get_realtime_bus
    from db import engine

    realtime_bus = get_realtime_bus()
    buffer_delivery_ids = buffer_delivery_ids or []

    logger.info(
        f"[explore_best_options_task] Iniciando exploración para user {user_id}: "
        f"request_id={request_id}, actions={actions}"
    )

    try:
        realtime_bus.publish(
            channel=f"user:{user_id}:best_options_explore.processing",
            data={
                "request_id": request_id,
                "message": "Processing explore actions...",
                "timestamp": time.time(),
            }
        )

        with Session(engine) as db:
            # Preparar repositorios y validadores
            from features.content_repository import UnifiedContentRepository
            from features.best_options.repository import BestOptionRepository as BestOptionRepo

            content_repo = UnifiedContentRepository(db)

            class BestOptionContentValidator:
                def __init__(self, best_option_repo):
                    self.best_option_repo = best_option_repo

                def is_content_learned(self, content_id: int, user_id: int) -> bool:
                    return self.best_option_repo.is_best_option_learned(content_id, user_id)

            content_validator = BestOptionContentValidator(BestOptionRepo(db))

            # Ejecutar acciones
            from core.explore.explore_actions import ExploreActions
            explore_actions = ExploreActions(
                db,
                content_repo=content_repo,
                content_validator=content_validator
            )

            status, buffer_ids, buffer_pos = explore_actions.execute_actions(
                user_id=user_id,
                actions=actions,
                content_type=ContentType.BEST_OPTIONS,
                resolve_queue_item_id=resolve_queue_item_id,
                limit=limit,
                buffer_delivery_ids=buffer_delivery_ids,
                buffer_position=buffer_position,
            )

            logger.info(
                f"[explore_best_options_task] Acciones completadas para user {user_id}: "
                f"status={status}, buffer_size={len(buffer_ids)}, position={buffer_pos}"
            )

            # Construir datos de best options (opcional, si quieres incluir detalles en el evento)
            best_options_data = []
            if buffer_ids:
                logger.debug(f"[explore_best_options_task] Building best_options_data for buffer_ids: {buffer_ids}")
                try:
                    delivery_service = DeliveryService(db)
                    delivery_items = delivery_service.get_delivery_items_by_ids(buffer_ids, user_id)
                    logger.debug(f"[explore_best_options_task] Retrieved {len(delivery_items)} delivery items")

                    delivery_item_map = {item.id: item for item in delivery_items}

                    response_builder = BestOptionsResponseBuilder(db)
                    best_options_data = response_builder.build_best_options_response(
                        buffer_ids, delivery_item_map, user_id
                    )
                    logger.debug(f"[explore_best_options_task] Built best_options_data with {len(best_options_data)} best options")

                    # Log a sample of the data to verify structure
                    if best_options_data:
                        import json as json_module
                        sample = best_options_data[0] if best_options_data else {}
                        logger.debug(f"[explore_best_options_task] Sample best_option_data: {json_module.dumps(sample, default=str)}")
                except Exception as e:
                    logger.error(f"[explore_best_options_task] Error building best_options_data: {e}", exc_info=True)
                    best_options_data = []

            # Publicar evento de completación con datos de best options
            try:
                event_data = {
                    "request_id": request_id,
                    "status": status,
                    "buffer_delivery_ids": buffer_ids,
                    "buffer_position": buffer_pos,
                    "best_options": best_options_data,  # Incluir datos completos de best options
                    "best_options_count": len(best_options_data),
                    "timestamp": time.time(),
                }
                logger.info(
                    f"[explore_best_options_task] Event data before publishing: "
                    f"buffer_ids={buffer_ids}, buffer_position={buffer_pos}, best_options_count={len(best_options_data)}, "
                    f"status={status}, request_id={request_id}"
                )
                logger.debug(f"[explore_best_options_task] Full event_data: {event_data}")
                logger.debug(f"[explore_best_options_task] Publishing explore.completed with {len(best_options_data)} best options")
                realtime_bus.publish(
                    channel=f"user:{user_id}:best_options_explore.completed",
                    data=event_data
                )
            except Exception as e:
                logger.error(f"[explore_best_options_task] Error publishing explore.completed event: {e}", exc_info=True)
                # Publish without best_options if serialization fails
                fallback_event_data = {
                    "request_id": request_id,
                    "status": status,
                    "buffer_delivery_ids": buffer_ids,
                    "buffer_position": buffer_pos,
                    "best_options_count": 0,
                    "error": str(e),
                    "timestamp": time.time(),
                }
                logger.info(
                    f"[explore_best_options_task] Fallback event data: "
                    f"buffer_ids={buffer_ids}, buffer_position={buffer_pos}, status={status}"
                )
                realtime_bus.publish(
                    channel=f"user:{user_id}:best_options_explore.completed",
                    data=fallback_event_data
                )

            logger.info(
                f"[explore_best_options_task] Evento completado publicado para user {user_id}: "
                f"request_id={request_id}"
            )

    except Exception as e:
        logger.error(
            f"[explore_best_options_task] Error durante exploración para user {user_id}: {str(e)}",
            exc_info=True,
        )

        # Publicar evento de error
        realtime_bus.publish(
            channel=f"user:{user_id}:best_options_explore.failed",
            data={
                "request_id": request_id,
                "error": str(e),
                "timestamp": time.time(),
            }
        )
