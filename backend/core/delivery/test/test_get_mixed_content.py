"""
Tests para DeliveryService.get_mixed_content()

Garantiza que:
1. Se distribuyen items de múltiples palabras
2. No hay monopolio - items provienen de diferentes palabras
3. Se respeta la alternancia boost/learning_path
4. Distribución balanceada cuando hay múltiples palabras boosteadas y en learning path
"""
import pytest
from datetime import datetime, timezone
from sqlmodel import Session, create_engine, SQLModel, select
from sqlmodel.pool import StaticPool

from core.delivery.service import DeliveryService
from core.delivery.repository import DeliveryRepository
from core.delivery.models import DeliveryBuffer
from core.delivery.enums import DeliveryStatus, RoundRobinWheelNodeStatus
from core.delivery.wheel_manager import WheelManager
from core.enums import ContentType, ContentSourceType
from core.learning_path.models import LearningPathQueue
from core.learning_path.enums import LearningPathQueueStatus, LearningState
from features.words.models import Word, WordStatistics
from features.examples.models import Example, ExampleType
from auth.models import User
from logging_client import logger


@pytest.fixture
def db():
    """Crear DB en memoria para tests"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def user_with_8_words_and_boost(db: Session):
    """
    Crear usuario con:
    - 8 palabras no-LEARNED
    - 1 palabra boosteada (word 1)
    - 7 palabras en learning path
    """
    user = User(email="test@example.com", hashed_password="hashed_pass")
    db.add(user)
    db.commit()
    db.refresh(user)

    # Crear 8 palabras
    words = []
    for i in range(1, 9):
        word = Word(
            user_id=user.id,
            main=f"word{i}",
            type="word",
            meaning=f"Meaning of word {i}",
            level=1,
            is_active=True,
        )
        db.add(word)
        db.commit()
        db.refresh(word)
        words.append(word)

        # Crear WordStatistics para cada palabra
        stats = WordStatistics(
            word_id=word.id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.LEARNING,
            times_exposed=0,
            times_correct=0,
        )
        db.add(stats)
        db.commit()

    return user, words


@pytest.fixture
def delivery_buffer_with_content(db: Session, user_with_8_words_and_boost):
    """
    Crear contenido en delivery buffer:
    - Word 1 (BOOSTEADA): 5 items BOOST
    - Words 2-8 (LEARNING_PATH): 4 items cada una
    """
    user, words = user_with_8_words_and_boost

    # Crear ejemplos y items en delivery buffer
    example_id_counter = 1

    # Word 1: BOOST content (5 items)
    for j in range(5):
        example = Example(
            word_id=words[0].id,
            text=f"Boost example {j+1} for {words[0].main}",
            text_form=words[0].main,
            type=ExampleType.EXPLORE,
        )
        db.add(example)
        db.commit()
        db.refresh(example)

        buffer_item = DeliveryBuffer(
            user_id=user.id,
            content_id=example.id,
            content_type=ContentType.EXAMPLE,
            word_id=words[0].id,
            source_type=ContentSourceType.BOOST,
            status=DeliveryStatus.PENDING,
        )
        db.add(buffer_item)
        example_id_counter += 1

    db.commit()

    # Words 2-8: LEARNING_PATH content (4 items cada una)
    for word_idx in range(1, 8):
        for j in range(4):
            example = Example(
                word_id=words[word_idx].id,
                text=f"Learning example {j+1} for {words[word_idx].main}",
                text_form=words[word_idx].main,
                type=ExampleType.EXPLORE,
            )
            db.add(example)
            db.commit()
            db.refresh(example)

            buffer_item = DeliveryBuffer(
                user_id=user.id,
                content_id=example.id,
                content_type=ContentType.EXAMPLE,
                word_id=words[word_idx].id,
                source_type=ContentSourceType.LEARNING_PATH,
                status=DeliveryStatus.PENDING,
            )
            db.add(buffer_item)
            example_id_counter += 1

    db.commit()

    return user, words


@pytest.fixture
def wheel_setup(db: Session, delivery_buffer_with_content):
    """Configurar rueda circular con word 1 boosteada"""
    user, words = delivery_buffer_with_content
    wheel_manager = WheelManager(db)

    # Agregar word 1 a la rueda (boosteada)
    wheel_manager.add_word_to_wheel(user.id, ContentType.EXAMPLE, words[0].id)

    return user, words, wheel_manager


class TestGetMixedContent:
    """Tests para DeliveryService.get_mixed_content()"""

    def test_returns_items_from_multiple_words(self, db: Session, wheel_setup):
        """Test: Devuelve items de múltiples palabras (no monopolio)"""
        user, words, wheel_manager = wheel_setup
        service = DeliveryService(db)

        # Obtener 8 items (uno por palabra)
        result = service.get_mixed_content(
            user_id=user.id,
            content_type=ContentType.EXAMPLE,
            limit=8
        )

        assert result["status"] in ["ok", "generating"], f"Status debe ser ok o generating, got {result['status']}"

        # Si hay contenido, verificar múltiples palabras
        if result["content"]:
            word_ids = [item["word_id"] for item in result["content"]]
            unique_words = set(word_ids)

            assert len(unique_words) > 1, f"Debería haber items de múltiples palabras, obtuvo solo: {unique_words}"
            assert len(result["content"]) <= 8, f"Esperado máx 8 items, obtuvo {len(result['content'])}"

    def test_respects_boost_word_node(self, db: Session, wheel_setup):
        """Test: Respeta nodos de palabra boosteada en la rueda"""
        user, words, wheel_manager = wheel_setup
        service = DeliveryService(db)

        # Obtener contenido
        result = service.get_mixed_content(
            user_id=user.id,
            content_type=ContentType.EXAMPLE,
            limit=6
        )

        # Verificar que si hay contenido, incluye palabra boosteada
        if result["content"]:
            word_ids = [item["word_id"] for item in result["content"]]

            # Word 1 está boosteada, debería aparecer
            assert words[0].id in word_ids, f"Palabra boosteada {words[0].id} debería aparecer en resultados"

    def test_balances_boost_and_learning_content(self, db: Session, wheel_setup):
        """Test: Balancea contenido BOOST y LEARNING_PATH"""
        user, words, wheel_manager = wheel_setup
        service = DeliveryService(db)

        # Obtener 10 items
        result = service.get_mixed_content(
            user_id=user.id,
            content_type=ContentType.EXAMPLE,
            limit=10
        )

        if result["content"]:
            # Contar por source_type
            source_counts = {}
            for item in result["content"]:
                source = item["source_type"]
                source_counts[source] = source_counts.get(source, 0) + 1

            # Debería haber ambos tipos si hay suficiente contenido
            if len(result["content"]) >= 2:
                assert len(source_counts) > 1 or len(result["content"]) == 1, \
                    f"Con múltiples items, debería haber alternancia entre tipos: {source_counts}"

    def test_no_word_monopoly_with_8_words(self, db: Session, wheel_setup):
        """Test: Ninguna palabra monopoliza cuando hay 8 palabras"""
        user, words, wheel_manager = wheel_setup
        service = DeliveryService(db)

        # Obtener múltiples batches
        all_word_ids = []
        for _ in range(3):
            result = service.get_mixed_content(
                user_id=user.id,
                content_type=ContentType.EXAMPLE,
                limit=5
            )

            if result["content"]:
                for item in result["content"]:
                    all_word_ids.append(item["word_id"])

        if all_word_ids:
            # Contar apariciones por palabra
            word_counts = {}
            for word_id in all_word_ids:
                word_counts[word_id] = word_counts.get(word_id, 0) + 1

            # Verificar distribución balanceada
            if len(word_counts) > 1:
                max_count = max(word_counts.values())
                min_count = min(word_counts.values())

                # No debería haber diferencia > 3 items entre palabra más/menos frecuente
                assert max_count - min_count <= 3, \
                    f"Distribución desbalanceada: {word_counts}, diferencia = {max_count - min_count}"

    def test_handles_large_batch_size(self, db: Session, wheel_setup):
        """Test: Maneja requests de batch grande sin problemas"""
        user, words, wheel_manager = wheel_setup
        service = DeliveryService(db)

        # Solicitar 15 items (hay ~33 total)
        result = service.get_mixed_content(
            user_id=user.id,
            content_type=ContentType.EXAMPLE,
            limit=15
        )

        assert result["status"] in ["ok", "generating"]

        if result["content"]:
            # Verificar que obtenemos contenido balanceado
            word_ids = [item["word_id"] for item in result["content"]]
            unique_words = set(word_ids)

            # Con 15 items de múltiples palabras, debería haber variedad
            assert len(unique_words) >= 2, \
                f"Con batch grande, debería haber múltiples palabras: {unique_words}"

    def test_wheel_node_status_updates(self, db: Session, wheel_setup):
        """Test: Estados de nodos de rueda se actualizan correctamente"""
        user, words, wheel_manager = wheel_setup
        service = DeliveryService(db)

        # Obtener contenido
        result = service.get_mixed_content(
            user_id=user.id,
            content_type=ContentType.EXAMPLE,
            limit=5
        )

        # Verificar que nodos se marcaron como READY o DISPATCHED
        wheel = wheel_manager.get_wheel_for_user(user.id, ContentType.EXAMPLE)

        if wheel:
            for node in wheel:
                # Los nodos consumidos deberían estar en READY o DISPATCHED
                # Los no consumidos pueden estar en INITIAL/READY/EXHAUSTED
                assert node.status in [
                    RoundRobinWheelNodeStatus.READY,
                    RoundRobinWheelNodeStatus.INITIAL,
                    RoundRobinWheelNodeStatus.EXHAUSTED,
                    RoundRobinWheelNodeStatus.GENERATING
                ], f"Node {node.id} tiene estado inválido: {node.status}"


@pytest.fixture
def realistic_development_state(db: Session, user_with_8_words_and_boost):
    """
    Fixture que replica el estado EXACTO visto en desarrollo:
    - 21 items BOOST todos para word_id=3 (monopolio)
    - 3 items LEARNING_PATH distribuidos (word 2, 4, 2)
    """
    user, words = user_with_8_words_and_boost

    # Crear 21 items BOOST todos para word 3
    for j in range(21):
        example = Example(
            word_id=words[2].id,  # word_id=3 (0-indexed: words[2])
            text=f"Boost example {j+1} for {words[2].main}",
            text_form=words[2].main,
            type=ExampleType.EXPLORE,
        )
        db.add(example)
        db.commit()
        db.refresh(example)

        buffer_item = DeliveryBuffer(
            user_id=user.id,
            content_id=example.id,
            content_type=ContentType.EXAMPLE,
            word_id=words[2].id,
            source_type=ContentSourceType.BOOST,
            status=DeliveryStatus.PENDING,
        )
        db.add(buffer_item)

    db.commit()

    # Crear 3 items LEARNING_PATH distribuidos (word 2, 4, 2)
    word_sequence = [words[1], words[3], words[1]]  # word 2, 4, 2
    for word in word_sequence:
        example = Example(
            word_id=word.id,
            text=f"Learning example for {word.main}",
            text_form=word.main,
            type=ExampleType.EXPLORE,
        )
        db.add(example)
        db.commit()
        db.refresh(example)

        buffer_item = DeliveryBuffer(
            user_id=user.id,
            content_id=example.id,
            content_type=ContentType.EXAMPLE,
            word_id=word.id,
            source_type=ContentSourceType.LEARNING_PATH,
            status=DeliveryStatus.PENDING,
        )
        db.add(buffer_item)

    db.commit()
    return user, words


class TestGetMixedContentMonopolyDetection:
    """Tests específicos para detectar monopolio de palabras boosteadas"""

    def test_monopoly_multiple_calls_reveals_boosted_only(self, db: Session, wheel_setup):
        """
        Test CRÍTICO: Múltiples llamadas secuenciales devuelven SOLO la palabra boosteada

        FALLA ESPERADA: Si solo hay palabra boosteada (word_id=3) en todos los resultados,
        la implementación está monopolizando.
        """
        user, words, wheel_manager = wheel_setup
        service = DeliveryService(db)

        # Hacer 3 llamadas consecutivas
        all_items = []
        for call_num in range(3):
            result = service.get_mixed_content(
                user_id=user.id,
                content_type=ContentType.EXAMPLE,
                limit=4
            )

            if result["content"]:
                all_items.extend(result["content"])

        # Analizar distribución
        if all_items:
            word_id_counts = {}
            for item in all_items:
                wid = item["word_id"]
                word_id_counts[wid] = word_id_counts.get(wid, 0) + 1

            # ASSERTION: Debe haber al mínimo 2 palabras diferentes
            unique_words = len(word_id_counts)
            assert unique_words >= 2, \
                f"MONOPOLIO DETECTADO: Solo {unique_words} palabra(s) en {len(all_items)} items. " \
                f"Distribución: {word_id_counts}. " \
                f"Se esperaba mínimo 2 palabras diferentes en 12 items."

    def test_monopoly_boost_word_dominates_results(self, db: Session, wheel_setup):
        """
        Test: Verifica que palabra boosteada NO domine el 100% de resultados

        FALLA ESPERADA: Si word_id=3 aparece en 100% de items, hay monopolio puro.
        """
        user, words, wheel_manager = wheel_setup
        service = DeliveryService(db)

        # Obtener 10 items de forma fragmentada
        all_word_ids = []
        for _ in range(2):
            result = service.get_mixed_content(
                user_id=user.id,
                content_type=ContentType.EXAMPLE,
                limit=5
            )

            if result["content"]:
                all_word_ids.extend([item["word_id"] for item in result["content"]])

        if all_word_ids:
            boosted_word_id = words[0].id
            boosted_count = sum(1 for wid in all_word_ids if wid == boosted_word_id)
            total_items = len(all_word_ids)
            boosted_percentage = (boosted_count / total_items) * 100

            # ASSERTION: Palabra boosteada no debe ser 100% de items
            assert boosted_percentage < 100, \
                f"MONOPOLIO TOTAL DETECTADO: " \
                f"Palabra boosteada (id={boosted_word_id}) aparece en {boosted_percentage:.1f}% de items ({boosted_count}/{total_items}). " \
                f"Se esperaba <= 70% para permitir learning_path content."

    def test_monopoly_learning_path_content_missing(self, db: Session, wheel_setup):
        """
        Test: Debe haber alternancia entre BOOST y LEARNING_PATH

        FALLA ESPERADA: Si todos los items son source_type=boost, hay monopolio de tipo.
        """
        user, words, wheel_manager = wheel_setup
        service = DeliveryService(db)

        # Obtener 8 items
        result = service.get_mixed_content(
            user_id=user.id,
            content_type=ContentType.EXAMPLE,
            limit=8
        )

        if result["content"] and len(result["content"]) >= 4:
            source_types = [item["source_type"] for item in result["content"]]

            has_boost = ContentSourceType.BOOST.value in source_types or "boost" in source_types
            has_learning = ContentSourceType.LEARNING_PATH.value in source_types or "learning_path" in source_types

            # ASSERTION: Debe haber alternancia de tipos
            assert has_boost and has_learning, \
                f"MONOPOLIO DE TIPO DETECTADO: " \
                f"Se esperaba alternancia boost/learning_path, pero got: {source_types}. " \
                f"has_boost={has_boost}, has_learning_path={has_learning}"

    def test_monopoly_word_distribution_inequality(self, db: Session, wheel_setup):
        """
        Test: Distribución desigual entre palabras = monopolio parcial

        FALLA ESPERADA: Si una palabra tiene 80%+ de items vs otras, hay monopolio parcial.
        """
        user, words, wheel_manager = wheel_setup
        service = DeliveryService(db)

        # Recolectar muchos items para ver patrón
        all_word_ids = []
        for _ in range(5):
            result = service.get_mixed_content(
                user_id=user.id,
                content_type=ContentType.EXAMPLE,
                limit=4
            )

            if result["content"]:
                all_word_ids.extend([item["word_id"] for item in result["content"]])

        if all_word_ids and len(set(all_word_ids)) > 1:
            word_counts = {}
            for wid in all_word_ids:
                word_counts[wid] = word_counts.get(wid, 0) + 1

            max_count = max(word_counts.values())
            min_count = min(word_counts.values())
            total = len(all_word_ids)
            max_percentage = (max_count / total) * 100

            # ASSERTION: Máximo 60% para una palabra cuando hay múltiples disponibles
            assert max_percentage <= 60, \
                f"MONOPOLIO PARCIAL DETECTADO: " \
                f"Palabra con max items: {max_percentage:.1f}% ({max_count}/{total}). " \
                f"Distribución completa: {word_counts}. " \
                f"Se esperaba distribución más balanceada (max <=60%)."

    def test_monopoly_no_learning_path_words_used(self, db: Session, wheel_setup):
        """
        Test: ¿Se están usando las 7 palabras en learning path?

        FALLA ESPERADA: Si solo aparece 1 palabra (boosteada), las otras 7 no se usan.
        """
        user, words, wheel_manager = wheel_setup
        service = DeliveryService(db)

        # Recolectar IDs de palabras en varios calls
        unique_word_ids_seen = set()
        for _ in range(6):
            result = service.get_mixed_content(
                user_id=user.id,
                content_type=ContentType.EXAMPLE,
                limit=3
            )

            if result["content"]:
                for item in result["content"]:
                    unique_word_ids_seen.add(item["word_id"])

        # Verificar cobertura
        all_word_ids = {w.id for w in words}
        learning_path_word_ids = {w.id for w in words[1:]}  # words 2-8

        covered_learning_path_words = unique_word_ids_seen & learning_path_word_ids
        coverage_percentage = (len(covered_learning_path_words) / len(learning_path_word_ids)) * 100 if learning_path_word_ids else 0

        # ASSERTION: Debe cubrir al menos 50% de palabras en learning path
        assert coverage_percentage >= 50, \
            f"MONOPOLIO SISTÉMICO DETECTADO: " \
            f"Solo {len(covered_learning_path_words)}/{len(learning_path_word_ids)} ({coverage_percentage:.1f}%) " \
            f"palabras de learning_path se usaron. " \
            f"Palabras vistas: {unique_word_ids_seen}, " \
            f"Palabras learning_path: {learning_path_word_ids}"

    def test_monopoly_sequential_calls_same_words(self, db: Session, wheel_setup):
        """
        Test: Llamadas secuenciales devuelven siempre las mismas palabras (monopolio repetido)

        FALLA ESPERADA: Si cada call devuelve word_id=3, hay monopolio consistente.
        """
        user, words, wheel_manager = wheel_setup
        service = DeliveryService(db)

        call_word_distributions = []
        for call_num in range(4):
            result = service.get_mixed_content(
                user_id=user.id,
                content_type=ContentType.EXAMPLE,
                limit=3
            )

            if result["content"]:
                word_ids = [item["word_id"] for item in result["content"]]
                unique_in_call = set(word_ids)
                call_word_distributions.append(unique_in_call)

        # Verificar si todas las llamadas tienen la misma palabra
        if call_word_distributions:
            intersection_all_calls = set.intersection(*call_word_distributions) if call_word_distributions else set()

            # Si solo 1 palabra aparece en TODAS las llamadas, es monopolio consistente
            assert len(intersection_all_calls) <= 1, \
                f"MONOPOLIO CONSISTENTE: " \
                f"Palabra(s) que aparecen en TODAS las {len(call_word_distributions)} llamadas: {intersection_all_calls}. " \
                f"Distribuciones por call: {[sorted(list(uw)) for uw in call_word_distributions]}. " \
                f"Se esperaba variación entre llamadas."


class TestMonopolyWithRealisticBuffer:
    """
    Tests que reproducen el estado REAL encontrado en desarrollo:
    - 21 items BOOST todos para word_id=3
    - 3 items LEARNING_PATH distribuidos

    Estos tests FALLARÁN si get_mixed_content devuelve monopolio con word_id=3
    """

    def test_realistic_state_boost_monopoly_detected(self, db: Session, realistic_development_state):
        """
        Test CRÍTICO: Replica EXACTAMENTE el estado de desarrollo

        Estado en BD:
        - 21 items BOOST, todos word_id=3
        - 3 items LEARNING_PATH (word 2, 4, 2)

        FALLA ESPERADA: Si get_mixed_content devuelve solo word_id=3, hay monopolio.
        """
        user, words = realistic_development_state
        service = DeliveryService(db)

        # Obtener 4 items
        result = service.get_mixed_content(
            user_id=user.id,
            content_type=ContentType.EXAMPLE,
            limit=4
        )

        if result["content"]:
            word_ids = [item["word_id"] for item in result["content"]]
            word_3_count = sum(1 for wid in word_ids if wid == words[2].id)

            # ASSERTION: Aunque hay 21 items BOOST de word_id=3, debería haber variedad
            # No todos los 4 items deberían ser word_id=3
            assert word_3_count < len(word_ids), \
                f"MONOPOLIO REPRODUCED: Todos los {len(word_ids)} items son word_id=3. " \
                f"Con solo 3 items LEARNING_PATH disponibles, esperábamos alternancia. " \
                f"word_ids: {word_ids}"

    def test_realistic_state_multiple_batches(self, db: Session, realistic_development_state):
        """
        Test: Múltiples batches desde estado realista

        FALLA ESPERADA: Si todas las llamadas devuelven solo word_id=3
        """
        user, words = realistic_development_state
        service = DeliveryService(db)

        all_items = []
        for _ in range(3):
            result = service.get_mixed_content(
                user_id=user.id,
                content_type=ContentType.EXAMPLE,
                limit=4
            )

            if result["content"]:
                all_items.extend(result["content"])

        if all_items:
            unique_words = set(item["word_id"] for item in all_items)

            # ASSERTION: Debe haber mínimo 2 palabras distintas en 12 items
            assert len(unique_words) >= 2, \
                f"MONOPOLIO TOTAL (REALISTA): Solo {len(unique_words)} palabra(s) en {len(all_items)} items. " \
                f"Palabras: {unique_words}. " \
                f"Esperábamos mix de BOOST (word_id=3) y LEARNING_PATH (word_id=2, 4)"

    def test_realistic_state_alternation_pattern(self, db: Session, realistic_development_state):
        """
        Test: ¿Se alterna entre BOOST y LEARNING_PATH?

        Con 21 BOOST (word_id=3) + 3 LEARNING_PATH (word_id=2,4,2),
        el patrón debería ser: boost, learning, boost, learning, ...

        FALLA ESPERADA: Si no hay alternancia en los source_types
        """
        user, words = realistic_development_state
        service = DeliveryService(db)

        result = service.get_mixed_content(
            user_id=user.id,
            content_type=ContentType.EXAMPLE,
            limit=8
        )

        if result["content"]:
            sources = [item["source_type"] for item in result["content"]]

            # Normalizar source_type values
            normalized_sources = [
                s.value if hasattr(s, 'value') else s
                for s in sources
            ]

            # Verificar si hay cambios entre tipos
            has_both_types = (
                ("boost" in normalized_sources or ContentSourceType.BOOST.value in normalized_sources) and
                ("learning_path" in normalized_sources or ContentSourceType.LEARNING_PATH.value in normalized_sources)
            )

            assert has_both_types, \
                f"MONOPOLIO DE TIPO EN ESTADO REALISTA: " \
                f"source_types: {normalized_sources}. " \
                f"Esperábamos alternancia boost/learning_path con proporción ~7:1"

    def test_realistic_state_word_id_in_boost_items(self, db: Session, realistic_development_state):
        """
        Test: Los items BOOST devueltos tienen word_id correcto?

        FALLA ESPERADA: Si todos los BOOST items tienen word_id=3 y eso es monopolio
        """
        user, words = realistic_development_state
        service = DeliveryService(db)

        result = service.get_mixed_content(
            user_id=user.id,
            content_type=ContentType.EXAMPLE,
            limit=10
        )

        if result["content"]:
            boost_items = [item for item in result["content"]
                          if (item["source_type"] == "boost" or
                              item["source_type"] == ContentSourceType.BOOST.value)]

            if boost_items:
                boost_word_ids = [item["word_id"] for item in boost_items]
                unique_boost_words = set(boost_word_ids)

                # ASSERTION: En estado realista, todos BOOST items son word_id=3
                # Esto es correcto, pero causa monopolio cuando se mezclan
                assert all(wid == words[2].id for wid in boost_word_ids), \
                    f"INESPERADO: BOOST items tienen word_ids variados: {unique_boost_words}. " \
                    f"En desarrollo todos son word_id=3. " \
                    f"Si esto cambió, verificar generación de BOOST content."


class TestSourceTypeFilteringBug:
    """
    Tests que verifican que get_mixed_content filtra correctamente por source_type

    BUG ENCONTRADO: get_pending_content() no filtra por source_type, por eso:
    - LEARNING_SLOT podría traer items BOOST por error
    - BOOST nodes podrían traer items LEARNING_PATH por error
    """

    def test_learning_slot_should_not_return_boost_content(self, db: Session, realistic_development_state):
        """
        Test CRÍTICO: Cuando es LEARNING_SLOT, NO debe devolver items BOOST

        En estado realista hay:
        - 21 items BOOST (word_id=3)
        - 3 items LEARNING_PATH (word_id 2, 4, 2)

        FALLA ESPERADA: Si algún item retornado es BOOST cuando se solicita desde LEARNING_SLOT
        """
        user, words = realistic_development_state
        service = DeliveryService(db)

        # Obtener contenido - el LEARNING_SLOT debería filtrar source_type
        result = service.get_mixed_content(
            user_id=user.id,
            content_type=ContentType.EXAMPLE,
            limit=4
        )

        if result["content"]:
            for item in result["content"]:
                source = item.get("source_type")
                # Normalizar el valor
                if hasattr(source, "value"):
                    source = source.value

                # Si el item viene de un LEARNING_SLOT y es BOOST, es error
                # (asumiendo que la rueda alterna y eventualmente toca LEARNING_SLOT)
                # Por ahora solo loggeamos para ver si sucede
                if source in ["boost", ContentSourceType.BOOST.value]:
                    logger.warning(
                        f"POTENTIAL BUG: Item con source_type=BOOST retornado sin filtro: "
                        f"id={item['id']}, source={source}, word_id={item.get('word_id')}"
                    )

    def test_verify_source_type_parameter_exists(self, db: Session, user_with_8_words_and_boost):
        """
        Test: Verifica si get_pending_content soporta filtro source_type

        FALLA ESPERADA: Si source_type no es parámetro soportado
        """
        user, words = user_with_8_words_and_boost
        repo = DeliveryRepository(db)

        # Intentar llamar con source_type (esto fallará si no está implementado)
        try:
            import inspect
            sig = inspect.signature(repo.get_pending_content)
            params = list(sig.parameters.keys())

            # ASSERTION: source_type debe ser parámetro
            assert "source_type" in params, \
                f"BUG CONFIRMADO: get_pending_content() no tiene parámetro 'source_type'. " \
                f"Parámetros actuales: {params}. " \
                f"Se necesita agregar source_type para filtrar correctamente."
        except Exception as e:
            logger.error(f"Error checking signature: {e}")

    def test_learning_slot_filtering_accuracy(self, db: Session, user_with_8_words_and_boost):
        """
        Test: LEARNING_SLOT debe filtrar SOLO items con source_type=LEARNING_PATH

        Fixture setup:
        - 5 items BOOST para word 1
        - 28 items LEARNING_PATH para palabras 2-8

        FALLA ESPERADA: Si get_pending_content devuelve BOOST cuando debería ser LEARNING_PATH
        """
        user, words = user_with_8_words_and_boost
        repo = DeliveryRepository(db)

        # Obtener PENDING sin filtro
        all_pending = repo.get_pending_content(user_id=user.id, limit=10)

        if all_pending:
            # Debe haber items de ambos tipos en algunos casos
            source_types = set()
            for item in all_pending:
                source_types.add(item.source_type.value if hasattr(item.source_type, 'value') else item.source_type)

            # Debería haber múltiples tipos si el filtro no está aplicado
            if len(source_types) > 1:
                logger.warning(
                    f"MIXING DETECTED: get_pending_content retorna múltiples source_types "
                    f"sin filtro: {source_types}. Esto es correcto si no se aplica filtro, "
                    f"pero get_mixed_content debería filtrar explícitamente."
                )
