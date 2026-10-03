# backend/core/event_bus.py
"""
Event Bus para arquitectura pub/sub con Celery y RabbitMQ.
Permite que múltiples módulos se suscriban a eventos globales sin acoplamiento.

Uso:
    # En tasks.py
    @subscribe_to('event.word.unboosted')
    def handle_word_unboosted_task(user_id: int, word_id: int):
        # Tu lógica aquí
        pass

    # En service.py
    publish_event('event.word.unboosted', user_id=1, word_id=5)
"""

from typing import Dict, List, Callable, Any
from kombu import Exchange, Queue
from logging_client import logger


# Registro global de suscriptores
# Estructura: {'event.nombre': [{'task_name': 'delivery.handler', 'queue_name': 'delivery_queue'}, ...]}
_subscribers: Dict[str, List[Dict[str, str]]] = {}


def subscribe_to(event_name: str, queue_name: str = None):
    """
    Decorador para suscribir una tarea Celery a un evento global.

    Args:
        event_name: Nombre del evento (ej: 'event.word.unboosted')
        queue_name: Nombre de la cola (si no se proporciona, se deduce del módulo)

    Example:
        @subscribe_to('event.word.unboosted')
        @celery_app.task(name='delivery.on_word_unboosted')
        def handle_word_unboosted(user_id: int, word_id: int):
            pass
    """
    def decorator(func):
        # Obtener el nombre de la tarea del decorator de celery_app.task
        task_name = func.name if hasattr(func, 'name') else func.__name__

        # Deducir nombre de la cola (ej: 'delivery' de 'delivery.on_word_unboosted')
        if queue_name is None:
            queue_name_deduced = task_name.split('.')[0] + '_queue'
        else:
            queue_name_deduced = queue_name

        # Registrar en el registro global
        if event_name not in _subscribers:
            _subscribers[event_name] = []

        _subscribers[event_name].append({
            'task_name': task_name,
            'queue_name': queue_name_deduced,
        })

        logger.info(f"[EventBus] Tarea '{task_name}' suscrita a evento '{event_name}' (cola: {queue_name_deduced})")

        return func

    return decorator


def get_event_queues() -> List[Queue]:
    """
    Genera las colas de RabbitMQ basadas en las suscripciones registradas.
    Se ejecuta cuando se inicializa Celery.

    Returns:
        Lista de objetos Queue listos para usar en celery_app.conf.task_queues
    """
    app_events_exchange = Exchange('app_events', type='topic', durable=True)
    queues = {}  # Dict para evitar duplicados

    for event_name, subscribers in _subscribers.items():
        for subscriber in subscribers:
            queue_name = subscriber['queue_name']

            # Si la cola ya existe, solo agregamos el nuevo routing_key
            if queue_name not in queues:
                queues[queue_name] = Queue(
                    name=queue_name,
                    exchange=app_events_exchange,
                    routing_keys=[event_name],
                    durable=True,
                )
            else:
                # Agregar este event_name al routing de la cola existente
                if event_name not in queues[queue_name].routing_keys:
                    queues[queue_name].routing_keys.append(event_name)

    result = list(queues.values())
    logger.info(f"[EventBus] Generadas {len(result)} colas para {len(_subscribers)} eventos")
    return result


def publish_event(event_name: str, **kwargs) -> None:
    """
    Publica un evento a todos los suscriptores.

    Args:
        event_name: Nombre del evento (ej: 'event.word.unboosted')
        **kwargs: Parámetros a pasar a las tareas suscriptoras

    Example:
        publish_event('event.word.unboosted', user_id=1, word_id=5)
    """
    from celery_app import celery_app

    if event_name not in _subscribers:
        logger.warning(f"[EventBus] Evento '{event_name}' publicado pero no tiene suscriptores")
        return

    subscribers = _subscribers[event_name]
    logger.info(f"[EventBus] Publicando evento '{event_name}' a {len(subscribers)} suscriptor(es)")

    # Publicar a todos los suscriptores
    for subscriber in subscribers:
        task_name = subscriber['task_name']
        queue_name = subscriber['queue_name']

        celery_app.send_task(
            task_name,
            kwargs=kwargs,
            queue=queue_name,
            exchange='app_events',
            routing_key=event_name,
        )
        logger.info(f"[EventBus] Evento '{event_name}' enviado a tarea '{task_name}'")


def get_subscribers_for_event(event_name: str) -> List[str]:
    """
    Retorna la lista de nombres de tareas suscritas a un evento.
    Útil para debugging/monitoring.
    """
    if event_name not in _subscribers:
        return []
    return [sub['task_name'] for sub in _subscribers[event_name]]
