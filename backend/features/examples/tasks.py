from typing import List, Optional
from sqlmodel import Session, select
from logging_client import logger
from celery_app import celery_app
from core.celery_queues import CeleryQueue
from sqlalchemy.exc import IntegrityError
import ai
import time
from features.examples.helpers import approximate_text_form
from features.examples.repository import ExampleRepository
from core.generation_ai.repository import GenerationAIRepository
from core.generation_ai.enums import GenerationAIStatus
from core.event_bus import subscribe_to_ai, publish_event_ai, publish_event_background
from core.enums import ContentType, ContentSourceType
from db import engine
from features.words.models import Word
from features.examples.models import Example, ExampleType
from core.explore.explore_actions import ExploreActions
from features.examples.explore_response_builder import ExploreResponseBuilder
from core.delivery.service import DeliveryService


@subscribe_to_ai('generation.content_requested')
@celery_app.task(name="tasks.examples.generate_simple", queue=CeleryQueue.AI)
def generate_simple_examples_task(
    user_id: int,
    word_ids: List[int],
    content_type: str = ContentType.EXAMPLE.value,
    amount: int = 1,
    queue_item_id: Optional[int] = None,
    content_source_type: str = ContentSourceType.LEARNING_PATH.value,
    **kwargs
) -> None:
    """
    Genera contenido (examples) basado en el tipo de contenido solicitado.

    Solo procesa si content_type es EXAMPLE. Otros tipos de contenido serán
    manejados por tasks específicas en sus respectivos módulos.

    Flujo:
    1. Buscar ejemplos pregenerados no consumidos en LearningPathQueue
    2. Transferirlos a DeliveryBuffer
    3. Si no hay suficientes, generar nuevos con AI
    """
    logger.debug(
        f"[ExampleGenerator] Task started: user_id={user_id}, word_ids={word_ids}, "
        f"content_type={content_type}, amount={amount}, queue_item_id={queue_item_id}, "
        f"content_source_type={content_source_type}"
    )

    # Fallback: si central_queue_id viene en kwargs (por compatibilidad), usarlo
    if 'central_queue_id' in kwargs and not queue_item_id:
        queue_item_id = kwargs.pop('central_queue_id')
        logger.debug(
            f"[ExampleGenerator] Fallback: Using central_queue_id from kwargs as queue_item_id={queue_item_id}"
        )

    # Log de kwargs inesperados (para debugging)
    if kwargs:
        logger.debug(f"[ExampleGenerator] Unexpected kwargs received: {kwargs}")

    # Validar que sea del tipo EXAMPLE
    if content_type != ContentType.EXAMPLE.value:
        logger.info(
            f"[ExampleGenerator] Skipping: content_type '{content_type}' is not EXAMPLE. "
            f"This event is for EXAMPLE content only."
        )
        return

    if not word_ids:
        logger.warning(f"[ExampleGenerator] No words provided for user {user_id}")
        return

    logger.info(
        f"[ExampleGenerator] Generating simple examples for {len(word_ids)} words (user {user_id})"
    )

    try:
        with Session(engine) as db:
            # ✅ NOTA: Ejemplos pregenerados se transfieren bajo demanda por DeliveryService
            # usando el priority engine para distribuir inteligentemente
            logger.debug(
                f"[ExampleGenerator] Pregenerated examples will be transferred on-demand "
                f"by DeliveryService for user {user_id}"
            )

            # ✅ Validar cuota de ejemplos
            from config import QuotaValidator
            try:
                QuotaValidator.validate_max_examples_per_user(db, user_id)
            except Exception as quota_error:
                logger.warning(
                    f"[ExampleGenerator] Quota exceeded for user {user_id}: {quota_error}"
                )
                return

            # Cargar palabras por sus IDs
            words = db.exec(
                select(Word).where(Word.id.in_(word_ids), Word.user_id == user_id)
            ).all()

            if not words:
                logger.warning(f"[ExampleGenerator] Words not found for user {user_id}")
                return

            # Obtener el máximo sequence actual para continuar secuencia
            from sqlalchemy import func as sql_func
            max_sequence = db.exec(
                select(sql_func.max(Example.sequence))
            ).first() or 0

            sequence_counter = max_sequence + 1
            successfully_created = 0
            generated_examples = []  # List of {'content_id': int, 'word_id': int}

            # Generar ejemplos para cada palabra
            example_repo = ExampleRepository(db)
            for word in words:
                try:
                    # Verificar cuántos ejemplos disponibles hay para esta palabra
                    available_count = example_repo.count_available_examples_for_word(word.id)

                    # Si hay suficientes ejemplos disponibles, no generar
                    if available_count >= 3:
                        if content_source_type == ContentSourceType.BOOST.value:
                            # Para boost, publicar eventos para que delivery/tasks.py ingrese al buffer
                            logger.info(
                                f"[ExampleGenerator] Word {word.id} already has {available_count} examples for boost, "
                                f"publishing content.generated events"
                            )

                            # Obtener ejemplos disponibles para esta palabra (que no estén encolados)
                            available_examples = db.exec(
                                select(Example)
                                .where(
                                    Example.word_id == word.id,
                                    Example.type == ExampleType.EXPLORE,
                                    Example.enqueued == False,
                                )
                                .limit(5)
                            ).all()

                            for example in available_examples:
                                # Publicar evento para que delivery/tasks.py lo ingrese al buffer
                                generated_examples.append({
                                    'content_id': example.id,
                                    'word_id': word.id,
                                })
                                successfully_created += 1
                                logger.debug(
                                    f"[ExampleGenerator] Prepared existing example {example.id} for word {word.id} "
                                    f"for delivery buffer (boost event will be published)"
                                )
                        else:
                            logger.info(
                                f"[ExampleGenerator] Word {word.id} already has {available_count} available examples, skipping generation"
                            )
                        continue

                    # Generar nuevos ejemplos con IA solo si hace falta
                    logger.info(
                        f"[ExampleGenerator] Word {word.id} has only {available_count} available examples, generating new ones..."
                    )
                    raw_examples = ai.generate_examples_for_single_word(word, amount, db)
                    logger.debug(f"[ExampleGenerator] Generated new examples for word {word.id}")

                    if not raw_examples:
                        logger.warning(
                            f"[ExampleGenerator] No examples available for word {word.id}"
                        )
                        continue

                    # Deduplicar ejemplos por normalized (evitar IntegrityError)
                    seen_normalized = set()
                    filtered_examples = []
                    for idx, example_text in enumerate(raw_examples):
                        normalized = example_text.lower().strip()
                        if normalized and normalized not in seen_normalized:
                            seen_normalized.add(normalized)
                            filtered_examples.append((idx, example_text))

                    # Verificar cuáles normalizados ya existen en BD
                    existing_normalized = set(
                        db.exec(
                            select(Example.normalized)
                            .where(Example.normalized.in_(list(seen_normalized)))
                        ).all()
                    )

                    # Todos los ejemplos generados por IA son EXPLORE
                    word_examples_count = 0
                    for idx, example_text in filtered_examples:
                        normalized = example_text.lower().strip()

                        # Saltar si ya existe en BD
                        if normalized in existing_normalized:
                            logger.debug(
                                f"[ExampleGenerator] Example already in DB for word {word.id} "
                                f"(normalized: '{normalized}'), skipping..."
                            )
                            continue

                        try:
                            example_type = ExampleType.EXPLORE

                            # Usar el word.main como text_form y aproximar si es necesario
                            text_form = approximate_text_form(example_text, word.main)
                            if not text_form:
                                text_form = word.main

                            # Crear el Example con word_id y text_form
                            example = Example(
                                type=example_type,
                                text=example_text,
                                text_form=text_form,
                                word_id=word.id,
                                normalized=normalized,
                                sequence=sequence_counter,
                                enqueued=False,
                            )
                            db.add(example)
                            db.commit()
                            generated_examples.append({
                                'content_id': example.id,
                                'word_id': word.id,
                            })
                            word_examples_count += 1
                            sequence_counter += 1

                        except Exception as e:
                            logger.error(
                                f"[ExampleGenerator] Error creating example for word {word.id}: {e}",
                                exc_info=True,
                            )
                            db.rollback()
                            continue

                    if word_examples_count > 0:
                        successfully_created += word_examples_count
                        logger.debug(f"[ExampleGenerator] Created {word_examples_count} examples for word {word.id}")

                except Exception as e:
                    logger.error(
                        f"[ExampleGenerator] Error generating examples for word {word.id}: {e}",
                        exc_info=True,
                    )
                    db.rollback()  # Limpiar sesión en error outer también
                    continue

            logger.info(
                f"[ExampleGenerator] Successfully created {successfully_created} examples for user {user_id}"
            )

            # ✅ Contar ejemplos creados
            if successfully_created > 0:
                from config import UserProfileManager
                UserProfileManager.increment_examples(db, user_id, amount=successfully_created)
                logger.debug(
                    f"[ExampleGenerator] Counted {successfully_created} examples for user {user_id}"
                )

            # Publicar evento por cada contenido generado
            for example in generated_examples:
                publish_event_background(
                    'content.generated',
                    user_id=user_id,
                    word_id=example['word_id'],
                    content_id=example['content_id'],
                    queue_item_id=queue_item_id,
                    content_type=ContentType.EXAMPLE.value,
                    content_source_type=content_source_type,
                    status=GenerationAIStatus.COMPLETED.value,
                )

            if queue_item_id:
                gen_repo = GenerationAIRepository(db)
                gen_repo.mark_as_completed(queue_item_id)

    except Exception as e:
        logger.error(
            f"[ExampleGenerator] Error generating simple examples for user {user_id}: {e}",
            exc_info=True,
        )

        if queue_item_id:
            with Session(engine) as error_db:
                gen_repo = GenerationAIRepository(error_db)
                gen_repo.mark_as_failed(queue_item_id, error_message=str(e))


def _transfer_pregenerated_examples(
    db: Session,
    user_id: int,
    content_type: str,
) -> int:
    """
    Busca ejemplos pregenerados en estado PENDING en LearningPathQueue
    y los transfiere a DeliveryBuffer, cambiando su status a TRANSFERRED.

    Flujo:
    - Filtra por status=PENDING
    - Crea item en DeliveryBuffer
    - Marca queue_item status como TRANSFERRED
    - El estado CONSUMED se actualiza cuando se despacha desde DeliveryBuffer al usuario

    Retorna: cantidad de ejemplos transferidos
    """
    from core.learning_path.models import LearningPathQueue
    from core.learning_path.enums import LearningPathQueueStatus
    from core.delivery.repository import DeliveryRepository

    # Obtener items PENDING de LearningPathQueue para este usuario
    pending_items = db.exec(
        select(LearningPathQueue).where(
            LearningPathQueue.user_id == user_id,
            LearningPathQueue.content_type == content_type,
            LearningPathQueue.status == LearningPathQueueStatus.PENDING,
        )
    ).all()

    if not pending_items:
        logger.debug(
            f"[ExampleGenerator._transfer_pregenerated_examples] "
            f"No pregenerated examples found for user {user_id} ({content_type})"
        )
        return 0

    transferred_count = 0
    delivery_repo = DeliveryRepository(db)

    for queue_item in pending_items:
        try:
            # Transferir a DeliveryBuffer
            delivery_repo.push_to_buffer(
                user_id=user_id,
                content_id=queue_item.content_id,
                source_type=ContentSourceType.LEARNING_PATH,
                content_type=ContentType(content_type),
                word_id=queue_item.word_id,
                learning_path_queue_id=queue_item.id,
            )

            # Marcar como TRANSFERRED en LearningPathQueue
            queue_item.status = LearningPathQueueStatus.TRANSFERRED
            db.add(queue_item)
            db.commit()

            transferred_count += 1
            logger.debug(
                f"[ExampleGenerator._transfer_pregenerated_examples] "
                f"Transferred queue_item {queue_item.id} (example {queue_item.content_id}) to DeliveryBuffer"
            )

        except Exception as e:
            logger.error(
                f"[ExampleGenerator._transfer_pregenerated_examples] "
                f"Error transferring queue_item {queue_item.id}: {e}",
                exc_info=True,
            )
            continue

    logger.info(
        f"[ExampleGenerator._transfer_pregenerated_examples] "
        f"Transferred {transferred_count} pregenerated examples for user {user_id}"
    )

    return transferred_count


@celery_app.task(name="tasks.examples.explore_examples", queue=CeleryQueue.BACKGROUND)
def explore_examples_task(
    user_id: int,
    request_id: str,
    actions: List[str],
    resolve_queue_item_id: Optional[int] = None,
    limit: int = 5,
    buffer_delivery_ids: List[int] = None,
    buffer_position: int = 0,
) -> None:
    """
    Task de background que procesa acciones de explore y publica eventos en tiempo real.

    Flujo:
    1. Recibe solicitud de explore con acciones
    2. Ejecuta acciones usando ExploreActions
    3. Publica eventos en RealtimeEventBus para transmitir al frontend vía SSE
    4. Eventos: explore.started, explore.processing, explore.completed, explore.failed

    Los datos se transmiten en tiempo real a través de /explore-stream (SSE).
    """
    from core.realtime_event_bus import get_realtime_bus

    realtime_bus = get_realtime_bus()
    buffer_delivery_ids = buffer_delivery_ids or []

    logger.info(
        f"[explore_examples_task] Iniciando exploración para user {user_id}: "
        f"request_id={request_id}, actions={actions}"
    )

    try:
        realtime_bus.publish(
            channel=f"user:{user_id}:explore.processing",
            data={
                "request_id": request_id,
                "message": "Processing explore actions...",
                "timestamp": time.time(),
            }
        )

        # ⚠️ TESTING: Simular latencia para acción 'next' (10 segundos)
        # if 'next' in actions:
        #     logger.info(f"[explore_examples_task] TESTING: Introduciendo latencia de 10 segundos para acción 'next'")
        #     time.sleep(60*1)
        #     logger.info(f"[explore_examples_task] TESTING: Latencia completada, continuando...")

        with Session(engine) as db:
            # Preparar repositorios y validadores
            from features.content_repository import UnifiedContentRepository
            content_repo = UnifiedContentRepository(db)

            class ExampleContentValidator:
                def __init__(self, example_repo):
                    self.example_repo = example_repo

                def is_content_learned(self, content_id: int, user_id: int) -> bool:
                    return self.example_repo.is_example_learned(content_id, user_id)

            content_validator = ExampleContentValidator(ExampleRepository(db))

            # Ejecutar acciones
            explore_actions = ExploreActions(
                db,
                content_repo=content_repo,
                content_validator=content_validator
            )

            status, buffer_ids, buffer_pos = explore_actions.execute_actions(
                user_id=user_id,
                actions=actions,
                content_type=ContentType.EXAMPLE,
                resolve_queue_item_id=resolve_queue_item_id,
                limit=limit,
                buffer_delivery_ids=buffer_delivery_ids,
                buffer_position=buffer_position,
            )

            logger.info(
                f"[explore_examples_task] Acciones completadas para user {user_id}: "
                f"status={status}, buffer_size={len(buffer_ids)}, position={buffer_pos}"
            )

            # Construir datos de ejemplo (opcional, si quieres incluir detalles en el evento)
            examples_data = []
            if buffer_ids:
                logger.debug(f"[explore_examples_task] Building examples_data for buffer_ids: {buffer_ids}")
                try:
                    delivery_service = DeliveryService(db)
                    delivery_items = delivery_service.get_delivery_items_by_ids(buffer_ids, user_id)
                    logger.debug(f"[explore_examples_task] Retrieved {len(delivery_items)} delivery items")

                    delivery_item_map = {item.id: item for item in delivery_items}

                    response_builder = ExploreResponseBuilder(db)
                    examples_data = response_builder.build_examples_response(
                        buffer_ids, delivery_item_map, user_id
                    )
                    logger.debug(f"[explore_examples_task] Built examples_data with {len(examples_data)} examples")

                    # Log a sample of the data to verify structure
                    if examples_data:
                        import json as json_module
                        sample = examples_data[0] if examples_data else {}
                        logger.debug(f"[explore_examples_task] Sample example_data: {json_module.dumps(sample, default=str)}")
                except Exception as e:
                    logger.error(f"[explore_examples_task] Error building examples_data: {e}", exc_info=True)
                    examples_data = []

            # Publicar evento de completación con datos de ejemplos
            try:
                event_data = {
                    "request_id": request_id,
                    "status": status,
                    "buffer_delivery_ids": buffer_ids,
                    "buffer_position": buffer_pos,
                    "examples": examples_data,  # Incluir datos completos de ejemplos
                    "examples_count": len(examples_data),
                    "timestamp": time.time(),
                }
                logger.info(
                    f"[explore_examples_task] Event data before publishing: "
                    f"buffer_ids={buffer_ids}, buffer_position={buffer_pos}, examples_count={len(examples_data)}, "
                    f"status={status}, request_id={request_id}"
                )
                logger.debug(f"[explore_examples_task] Full event_data: {event_data}")
                logger.debug(f"[explore_examples_task] Publishing explore.completed with {len(examples_data)} examples")
                realtime_bus.publish(
                    channel=f"user:{user_id}:explore.completed",
                    data=event_data
                )
            except Exception as e:
                logger.error(f"[explore_examples_task] Error publishing explore.completed event: {e}", exc_info=True)
                # Publish without examples if serialization fails
                fallback_event_data = {
                    "request_id": request_id,
                    "status": status,
                    "buffer_delivery_ids": buffer_ids,
                    "buffer_position": buffer_pos,
                    "examples_count": 0,
                    "error": str(e),
                    "timestamp": time.time(),
                }
                logger.info(
                    f"[explore_examples_task] Fallback event data: "
                    f"buffer_ids={buffer_ids}, buffer_position={buffer_pos}, status={status}"
                )
                realtime_bus.publish(
                    channel=f"user:{user_id}:explore.completed",
                    data=fallback_event_data
                )

            logger.info(
                f"[explore_examples_task] Evento completado publicado para user {user_id}: "
                f"request_id={request_id}"
            )

    except Exception as e:
        logger.error(
            f"[explore_examples_task] Error durante exploración para user {user_id}: {str(e)}",
            exc_info=True,
        )

        # Publicar evento de error
        realtime_bus.publish(
            channel=f"user:{user_id}:explore.failed",
            data={
                "request_id": request_id,
                "error": str(e),
                "timestamp": time.time(),
            }
        )
