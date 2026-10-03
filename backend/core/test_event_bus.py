# backend/core/test_event_bus.py
"""
Script de prueba para el Event Bus.
Ejecutar: python -c "from core.test_event_bus import test_event_bus; test_event_bus()"
"""

from core.event_bus import (
    _subscribers,
    get_subscribers_for_event,
    get_event_queues,
    publish_event,
)


def test_event_bus():
    """Verifica que el Event Bus está funcionando correctamente"""
    print("\n" + "=" * 80)
    print("TEST: EVENT BUS SYSTEM")
    print("=" * 80)

    # Test 1: Verificar que hay suscriptores registrados
    print("\n[TEST 1] Verificar suscriptores registrados:")
    if not _subscribers:
        print("  ❌ ERROR: No hay suscriptores registrados")
        print("     Asegúrate de que celery_app.autodiscover_tasks() se ejecutó")
        return False

    print(f"  ✅ {len(_subscribers)} evento(s) registrado(s):")
    for event_name, subs in _subscribers.items():
        print(f"     - {event_name}: {len(subs)} suscriptor(es)")
        for sub in subs:
            print(f"       └─ {sub['task_name']} (cola: {sub['queue_name']})")

    # Test 2: Verificar evento específico 'event.word.unboosted'
    print("\n[TEST 2] Verificar evento 'event.word.unboosted':")
    if 'event.word.unboosted' not in _subscribers:
        print("  ❌ ERROR: Evento 'event.word.unboosted' no registrado")
        return False

    subs = _subscribers['event.word.unboosted']
    if not subs:
        print("  ❌ ERROR: No hay suscriptores para 'event.word.unboosted'")
        return False

    print(f"  ✅ Encontrados {len(subs)} suscriptor(es):")
    for sub in subs:
        print(f"     - {sub['task_name']}")

    # Test 3: Usar get_subscribers_for_event()
    print("\n[TEST 3] Usar get_subscribers_for_event():")
    task_names = get_subscribers_for_event('event.word.unboosted')
    if not task_names:
        print("  ❌ ERROR: get_subscribers_for_event() retornó vacío")
        return False

    print(f"  ✅ get_subscribers_for_event() retornó {len(task_names)} tareas:")
    for task_name in task_names:
        print(f"     - {task_name}")

    # Test 4: Generar colas
    print("\n[TEST 4] Generar colas con get_event_queues():")
    queues = get_event_queues()
    if not queues:
        print("  ❌ ERROR: No se generaron colas")
        return False

    print(f"  ✅ Se generaron {len(queues)} cola(s):")
    for queue in queues:
        print(f"     - Nombre: {queue.name}")
        print(f"       Routing Keys: {queue.routing_keys}")
        print(f"       Durable: {queue.durable}")

    # Test 5: Validar estructura de colas
    print("\n[TEST 5] Validar estructura de colas:")
    valid = True
    for queue in queues:
        if not queue.name:
            print(f"  ❌ Cola sin nombre")
            valid = False
        if not queue.routing_keys:
            print(f"  ❌ Cola '{queue.name}' sin routing_keys")
            valid = False

    if valid:
        print(f"  ✅ Todas las colas tienen estructura válida")

    # Test 6: Publicar evento (dry run)
    print("\n[TEST 6] Publicar evento (prueba):")
    try:
        publish_event('event.word.unboosted', user_id=1, word_id=5)
        print("  ✅ publish_event() ejecutado sin errores")
    except Exception as e:
        print(f"  ❌ ERROR al publicar: {e}")
        return False

    # Resumen
    print("\n" + "=" * 80)
    print("✅ TODOS LOS TESTS PASARON")
    print("=" * 80)
    print("\nEl Event Bus está listo para usar. Ejemplo:")
    print("  from core.event_bus import publish_event")
    print("  publish_event('event.word.unboosted', user_id=1, word_id=5)")
    print("=" * 80 + "\n")
    return True


def debug_event_bus():
    """Imprime información de debugging del Event Bus"""
    print("\n" + "=" * 80)
    print("DEBUG: EVENT BUS INFORMATION")
    print("=" * 80)

    print("\n📋 TODOS LOS EVENTOS Y SUSCRIPTORES:")
    if not _subscribers:
        print("  (No hay suscriptores registrados)")
    else:
        for event_name, subs in _subscribers.items():
            print(f"\n  {event_name}")
            for i, sub in enumerate(subs, 1):
                print(f"    {i}. {sub['task_name']}")
                print(f"       → Cola: {sub['queue_name']}")

    print("\n\n📡 COLAS GENERADAS:")
    queues = get_event_queues()
    if not queues:
        print("  (No se generaron colas)")
    else:
        for queue in queues:
            print(f"\n  Cola: {queue.name}")
            print(f"    Routing keys: {queue.routing_keys}")
            print(f"    Durable: {queue.durable}")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        debug_event_bus()
    else:
        test_event_bus()
