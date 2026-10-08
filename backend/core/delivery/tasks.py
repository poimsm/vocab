# backend/core/delivery/tasks.py
from sqlmodel import Session
from db import engine
from celery_app import celery_app
from core.delivery.repository import DeliveryRepository
from core.delivery.wheel_manager import WheelManager
from core.delivery.service import DeliveryService
from core.event_bus import subscribe_to_background
from core.celery_queues import CeleryQueue
from core.enums import ContentType, ContentSourceType
from logging_client import logger
from typing import Optional


@subscribe_to_background('word.boosted')
@celery_app.task(name="delivery.on_word_boosted", queue=CeleryQueue.BACKGROUND)
def add_word_to_wheel_task(user_id: int, word_id: int, **kwargs):
    """
    Suscriptor al evento 'event.word.boosted'.
    1. Agrega la palabra a la rueda circular de distribución de contenido
    2. Limpia items antiguos de learning_path que sean sobre esta palabra boosteada
    """
    logger.info(f"[DeliveryTask] Procesando boost para user_id={user_id}, word_id={word_id}")

    with Session(engine) as session:
        from sqlmodel import select
        from core.delivery.models import DeliveryBuffer
        from core.enums import ContentSourceType
        from core.delivery.enums import DeliveryStatus

        wheel_manager = WheelManager(session)

        # Agregar a la rueda para cada tipo de contenido
        for content_type in [ContentType.EXAMPLE, ContentType.BEST_OPTIONS]:
            wheel_manager.add_word_to_wheel(user_id, content_type, word_id)
            logger.info(
                f"[DeliveryTask] Added word_id={word_id} to wheel "
                f"for user {user_id} (content_type={content_type.value})"
            )

        # CLEANUP: Marca items de learning_path sobre esta palabra como DISPATCHED
        # Agnóstico a tipos de contenido - usa directamente word_id en DeliveryBuffer
        learning_buffer_items = session.exec(
            select(DeliveryBuffer).where(
                DeliveryBuffer.user_id == user_id,
                DeliveryBuffer.word_id == word_id,
                DeliveryBuffer.source_type == ContentSourceType.LEARNING_PATH,
                DeliveryBuffer.status == DeliveryStatus.PENDING
            )
        ).all()

        if learning_buffer_items:
            for item in learning_buffer_items:
                item.status = DeliveryStatus.DISPATCHED
                session.add(item)
            session.commit()

            logger.debug(
                f"[DeliveryTask] Cleaned up {len(learning_buffer_items)} old learning_path buffer items "
                f"about boosted word {word_id} for user {user_id}"
            )


@subscribe_to_background('word.unboosted')
@celery_app.task(name="delivery.on_word_unboosted", queue=CeleryQueue.BACKGROUND)
def remove_word_from_wheel_task(user_id: int, word_id: int, **kwargs):
    """
    Suscriptor al evento global 'event.word.unboosted'.
    Quita la palabra de la rueda circular y descarta su contenido.
    """
    logger.info(f"[DeliveryTask] Procesando unboost para user_id={user_id}, word_id={word_id}")

    with Session(engine) as session:
        wheel_manager = WheelManager(session)
        repository = DeliveryRepository(session)

        # Quitar de la rueda para cada tipo de contenido
        for content_type in [ContentType.EXAMPLE, ContentType.BEST_OPTIONS]:
            removed = wheel_manager.remove_word_from_wheel(user_id, content_type, word_id)
            if removed:
                logger.debug(
                    f"[DeliveryTask] Removed word_id={word_id} from wheel "
                    f"for user {user_id} (content_type={content_type.value})"
                )

        # Descartar contenido del buffer
        repository.discard_boost_word_items(user_id, word_id)
        logger.info(f"[DeliveryTask] Ítems descartados exitosamente para word_id={word_id}.")


@subscribe_to_background('boost.content.exhausted')
@celery_app.task(name="delivery.on_boost_content_exhausted", queue=CeleryQueue.BACKGROUND)
def on_boost_content_exhausted_task(user_id: int, word_id: int, content_type: str, **kwargs) -> None:
    """
    Suscriptor al evento 'boost.content.exhausted'.
    Actualiza el estado del nodo de la rueda a GENERATING cuando una palabra no tiene contenido.
    """
    logger.info(
        f"[DeliveryTask] Processing boost.content.exhausted for user {user_id}, "
        f"word_id={word_id}, content_type={content_type}"
    )

    with Session(engine) as session:
        try:
            from core.delivery.enums import RoundRobinWheelNodeStatus
            from core.enums import ContentType as ContentTypeEnum

            wheel_manager = WheelManager(session)
            content_type_enum = ContentTypeEnum(content_type)

            # Encontrar el nodo correspondiente a esta palabra
            node = wheel_manager.get_node_by_word_id(user_id, content_type_enum, word_id)

            if node:
                wheel_manager.update_node_status(node.id, RoundRobinWheelNodeStatus.GENERATING)
                logger.info(
                    f"[DeliveryTask] Updated wheel node {node.id} to GENERATING for word {word_id}"
                )
            else:
                logger.warning(
                    f"[DeliveryTask] No wheel node found for user {user_id}, word_id={word_id}"
                )

        except Exception as e:
            logger.error(
                f"[DeliveryTask] Error processing boost.content.exhausted: {e}",
                exc_info=True
            )


@subscribe_to_background('learning_path.generation.completed')
@celery_app.task(name="delivery.on_learning_path_generation_completed", queue=CeleryQueue.BACKGROUND)
def on_learning_path_generation_completed_task(user_id: int, content_type: str, **kwargs) -> None:
    """
    Suscriptor al evento 'learning_path.generation.completed'.
    Después de que la generación termina, actualiza los nodos learning_slot:
    - Si hay contenido nuevo → READY
    - Si no hay contenido → EXHAUSTED
    """
    logger.info(
        f"[DeliveryTask] Processing learning_path.generation.completed for user {user_id}, "
        f"content_type={content_type}"
    )

    with Session(engine) as session:
        try:
            from core.delivery.enums import RoundRobinWheelNodeStatus
            from core.enums import ContentType as ContentTypeEnum

            wheel_manager = WheelManager(session)
            repository = DeliveryRepository(session)
            content_type_enum = ContentTypeEnum(content_type)

            # Obtener todos los nodos learning_slot del usuario
            learning_nodes = wheel_manager.get_learning_slot_nodes(user_id, content_type_enum)

            if not learning_nodes:
                logger.warning(f"[DeliveryTask] No learning slot nodes found for user {user_id}")
                return

            # Verificar si hay contenido PENDING de learning_path en DeliveryBuffer
            pending_content = repository.get_pending_learning_path_content(user_id, content_type_enum)

            if pending_content:
                # Hay contenido nuevo generado → actualizar nodos a READY
                for node in learning_nodes:
                    wheel_manager.update_node_status(node.id, RoundRobinWheelNodeStatus.READY)
                logger.info(
                    f"[DeliveryTask] Updated {len(learning_nodes)} learning slot nodes to READY "
                    f"(found {len(pending_content)} pending items)"
                )
            else:
                # No hay contenido → actualizar a EXHAUSTED
                for node in learning_nodes:
                    wheel_manager.update_node_status(node.id, RoundRobinWheelNodeStatus.EXHAUSTED)
                logger.info(
                    f"[DeliveryTask] Updated {len(learning_nodes)} learning slot nodes to EXHAUSTED "
                    f"(no content available after generation)"
                )

        except Exception as e:
            logger.error(
                f"[DeliveryTask] Error processing learning_path.generation.completed: {e}",
                exc_info=True
            )


@subscribe_to_background('learning_path.generation.failed')
@celery_app.task(name="delivery.on_learning_path_generation_failed", queue=CeleryQueue.BACKGROUND)
def on_learning_path_generation_failed_task(user_id: int, content_type: str, error_message: str = None, **kwargs) -> None:
    """
    Suscriptor al evento 'learning_path.generation.failed'.
    Cuando la generación falla, marca los nodos learning_slot como EXHAUSTED.
    """
    logger.info(
        f"[DeliveryTask] Processing learning_path.generation.failed for user {user_id}, "
        f"content_type={content_type}. Error: {error_message}"
    )

    with Session(engine) as session:
        try:
            from core.delivery.enums import RoundRobinWheelNodeStatus
            from core.enums import ContentType as ContentTypeEnum

            wheel_manager = WheelManager(session)
            content_type_enum = ContentTypeEnum(content_type)

            # Obtener todos los nodos learning_slot del usuario
            learning_nodes = wheel_manager.get_learning_slot_nodes(user_id, content_type_enum)

            if not learning_nodes:
                logger.warning(f"[DeliveryTask] No learning slot nodes found for user {user_id}")
                return

            # Marcar como EXHAUSTED (generación falló)
            for node in learning_nodes:
                wheel_manager.update_node_status(node.id, RoundRobinWheelNodeStatus.EXHAUSTED)

            logger.info(
                f"[DeliveryTask] Updated {len(learning_nodes)} learning slot nodes to EXHAUSTED "
                f"due to generation failure"
            )

        except Exception as e:
            logger.error(
                f"[DeliveryTask] Error processing learning_path.generation.failed: {e}",
                exc_info=True
            )


@subscribe_to_background('content.generated')
@celery_app.task(name="delivery.on_content_generated", queue=CeleryQueue.BACKGROUND)
def on_content_generated(
    user_id: int,
    word_id: Optional[int],
    content_id: int,
    queue_item_id: Optional[int],
    content_type: str,
    content_source_type: str,
    status: str,
    **kwargs
) -> None:
    """
    Suscriptor al evento 'content.generated'.
    Solo procesa contenido BOOST e ingresa al delivery buffer.
    LEARNING_PATH content es manejado on-demand por get_prioritized_content.
    """
    # Solo procesar si es del módulo boost
    if content_source_type != ContentSourceType.BOOST.value:
        return

    logger.info(
        f"[DeliveryTask] Content generated event received for BOOST word_id={word_id}, "
        f"content_type={content_type}, status={status}"
    )

    with Session(engine) as session:
        try:
            delivery_service = DeliveryService(session)
            content_type_enum = ContentType(content_type)

            # Registrar el contenido generado en el delivery buffer
            delivery_service.register_generated_content(
                user_id=user_id,
                content_id=content_id,
                source_type=ContentSourceType.BOOST,
                content_type=content_type_enum,
                word_id=word_id,
                learning_path_queue_id=None,
            )

            logger.info(
                f"[DeliveryTask] Successfully registered BOOST content_id={content_id} "
                f"for word {word_id} in delivery buffer"
            )

        except Exception as e:
            logger.error(
                f"[DeliveryTask] Error processing content.generated for BOOST: {e}",
                exc_info=True
            )