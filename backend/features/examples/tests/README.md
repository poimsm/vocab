# Unit Tests for Examples Module

Tests unitarios para el endpoint `explore` y funciones relacionadas del módulo de ejemplos.

## Estructura

```
examples/
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Fixtures compartidas
│   ├── test_example_routes.py # Tests para explore endpoint
│   └── README.md
├── example_routes.py
├── example_repository.py
└── ...
```

## Setup

Instalar pytest y dependencias de testing:

```bash
# Dentro del entorno (después de: sh bin/enter_backend.sh)
pip install -r requirements-test.txt
```

## Ejecutar Tests

Todos los comandos asumen que estás dentro del entorno (`sh bin/enter_backend.sh`).

### Todos los tests de examples:
```bash
pytest examples/tests/ -v
```

### Todos los tests del proyecto:
```bash
pytest -v
```

### Con coverage:
```bash
pytest examples/tests/ --cov=examples --cov-report=html
```

### Modo watch (ejecuta tests al guardar):
```bash
pytest-watch examples/tests/ -- -v
```

### Un test específico:
```bash
pytest examples/tests/test_example_routes.py::TestActionNext::test_next_clears_buffer_and_loads_new -v
```

### Una clase de tests:
```bash
pytest examples/tests/test_example_routes.py::TestActionNext -v
```

## Fixtures Disponibles

Todos definidos en `conftest.py`:

- **`db_engine`**: Motor SQLite en memoria
- **`db_session`**: Sesión de BD para tests (auto-rollback)
- **`current_user`**: Usuario de prueba creado
- **`test_words`**: 3 palabras de prueba (hello, world, learned)
- **`test_examples`**: 3 ejemplos de prueba
- **`test_word_statistics`**: Estadísticas asociadas (NEW, LEARNING, LEARNED)
- **`test_content_queue`**: 3 items en la cola de contenido

## Casos de Prueba

### Helpers Internos (Utilidades)

#### `TestIsQueueItemWithLearnedWord` - Validación de palabras LEARNED
- ✓ Retorna False para palabras NEW
- ✓ Retorna True para palabras LEARNED
- ✓ Retorna True para ejemplos inexistentes

#### `TestValidateBufferAndGetValidIds` - Validación de buffer
- ✓ Mantiene items válidos
- ✓ Remueve items con palabras LEARNED
- ✓ Remueve items inexistentes

#### `TestAdjustPositionAfterRemovals` - Ajuste de posición
- ✓ Posición sin cambios cuando no hay remociones
- ✓ Ajusta cuando items removidos antes de posición
- ✓ Clamp a último item
- ✓ Maneja buffer vacío

#### `TestRefillBufferToLimit` - Refill de buffer
- ✓ No refill si está al límite
- ✓ Refill si está debajo del límite
- ✓ Valida items nuevos

#### `TestBuildExamplesResponse` - Construcción de respuesta
- ✓ Retorna vacío para buffer vacío
- ✓ Construye respuesta con segmentación

### Acciones del Endpoint

#### `TestActionResolve` - Acción "resolve"
- ✓ Marca item como consumido y registra exposición
- ✓ Retorna False para items inexistentes
- ✓ Idempotente (True si ya resuelto)

#### `TestActionSync` - Acción "sync"
- ✓ Actualiza posición sin modificar buffer
- ✓ Retorna "ok" status

#### `TestActionSyncBuffer` - Acción "sync-buffer"
- ✓ Valida y refill buffer
- ✓ Llama helpers en orden correcto

#### `TestActionResume` - Acción "resume"
- ✓ Retorna vacío cuando no hay sesión
- ✓ Carga nuevo batch cuando todos visitados
- ✓ Retorna "ok" status

#### `TestActionNext` - Acción "next"
- ✓ Limpia buffer y carga nuevos items
- ✓ Retorna "generating" cuando ContentQueue vacío
- ✓ Retorna "no_words" cuando todas palabras LEARNED

## Técnicas de Testing

### Mocking
- Usa `unittest.mock.patch` para aislar componentes
- Mocks para `ContentQueueManager`, `LearningTracker`, `UserExampleSessionRepository`
- Permite testear lógica sin BD real

### Fixtures
- SQLite en memoria para rapidez
- Auto-cleanup entre tests (session rollback)
- Datos consistentes reutilizables

### Assertions
- Assertions simples con `assert`
- `.assert_called_once()` para verificar calls
- `.assert_called_with()` para verificar argumentos

## Tips

1. **Ejecutar un único test durante desarrollo:**
   ```bash
   pytest examples/tests/test_example_routes.py::TestActionNext::test_next_clears_buffer_and_loads_new -v
   ```

2. **Ver logs de tests:**
   ```bash
   pytest examples/tests/ -v -s
   ```

3. **Generar coverage visual:**
   ```bash
   pytest examples/tests/ --cov=examples --cov-report=html
   # Luego abrir htmlcov/index.html
   ```

4. **Fallar rápido en primer error:**
   ```bash
   pytest examples/tests/ -x
   ```

## Información Adicional

- Tests siguen patrón **Arrange-Act-Assert**
- Cada test es independiente (no depende de otros)
- Usar fixtures en lugar de setUp/tearDown
- Mocks para componentes externos
- Tests verifican comportamiento, no implementación
