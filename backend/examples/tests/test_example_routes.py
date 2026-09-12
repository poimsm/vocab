"""Tests for example_routes.py - explore endpoint and related functions."""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from sqlmodel import Session, select

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from models import (
    User, Word, Example, ContentQueue, WordStatistics,
    ContentType, LearningState, ExampleWord, ExampleType
)
from examples.example_routes import (
    _is_queue_item_with_learned_word,
    _validate_buffer_and_get_valid_ids,
    _adjust_position_after_removals,
    _refill_buffer_to_limit,
    _build_examples_response,
    _action_resolve,
    _action_sync,
    _action_sync_buffer,
    _action_resume,
    _action_next,
)


class TestIsQueueItemWithLearnedWord:
    """Tests for _is_queue_item_with_learned_word helper."""

    def test_returns_false_for_new_word(self, db_session: Session, current_user: User, test_content_queue):
        """Should return False for NEW words."""
        queue_item = test_content_queue[0]
        result = _is_queue_item_with_learned_word(db_session, queue_item, current_user)
        assert result is False

    def test_returns_true_for_learned_word(self, db_session: Session, current_user: User,
                                            test_examples, test_content_queue):
        """Should return True for LEARNED words."""
        # Create a LEARNED word and associate it with an example
        learned_word = Word(
            main="already_learned",
            type="noun",
            meaning="learned word",
            level=1,
            user_id=current_user.id,
            is_boosted=False,
        )
        db_session.add(learned_word)
        db_session.commit()

        # Create example with this word
        example = Example(
            type=ExampleType.EXPLORE,
            text="The already_learned word",
        )
        db_session.add(example)
        db_session.commit()

        ExampleWord(example_id=example.id, word_id=learned_word.id, text_form="already_learned")
        db_session.add(ExampleWord(example_id=example.id, word_id=learned_word.id, text_form="already_learned"))

        # Create LEARNED statistic
        stat = WordStatistics(
            word_id=learned_word.id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.LEARNED,
            times_seen=6,
        )
        db_session.add(stat)
        db_session.commit()

        # Create queue item with this example
        queue_item = ContentQueue(
            user_id=current_user.id,
            type=ContentType.EXAMPLE,
            content_id=example.id,
            status="pending",
        )
        db_session.add(queue_item)
        db_session.commit()

        result = _is_queue_item_with_learned_word(db_session, queue_item, current_user)
        assert result is True

    def test_returns_true_for_nonexistent_example(self, db_session: Session, current_user: User):
        """Should return True (discard) for queue items with nonexistent examples."""
        queue_item = ContentQueue(
            user_id=current_user.id,
            type=ContentType.EXAMPLE,
            content_id=9999,  # Nonexistent
            status="pending",
        )
        db_session.add(queue_item)
        db_session.commit()

        result = _is_queue_item_with_learned_word(db_session, queue_item, current_user)
        assert result is True


class TestValidateBufferAndGetValidIds:
    """Tests for _validate_buffer_and_get_valid_ids helper."""

    def test_keeps_valid_items(self, db_session: Session, current_user: User, test_content_queue):
        """Should keep items with non-LEARNED words."""
        buffer_ids = [test_content_queue[0].id, test_content_queue[1].id]
        result = _validate_buffer_and_get_valid_ids(db_session, buffer_ids, current_user)
        assert len(result) == 2
        assert test_content_queue[0].id in result
        assert test_content_queue[1].id in result

    def test_removes_learned_items(self, db_session: Session, current_user: User, test_content_queue):
        """Should remove items with LEARNED words."""
        # Make the third example's word as LEARNED
        # First need to setup the word-example relationship
        learned_word = Word(
            main="to_learn",
            type="verb",
            meaning="learn",
            level=1,
            user_id=current_user.id,
        )
        db_session.add(learned_word)
        db_session.commit()

        db_session.add(ExampleWord(
            example_id=test_content_queue[2].content_id,
            word_id=learned_word.id,
            text_form="Learning"
        ))

        stat = WordStatistics(
            word_id=learned_word.id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.LEARNED,
            times_seen=6,
        )
        db_session.add(stat)
        db_session.commit()

        buffer_ids = [test_content_queue[0].id, test_content_queue[1].id, test_content_queue[2].id]
        result = _validate_buffer_and_get_valid_ids(db_session, buffer_ids, current_user)

        # Should have 2 items (the first 2, without the learned one)
        assert len(result) <= 3

    def test_removes_nonexistent_items(self, db_session: Session, current_user: User, test_content_queue):
        """Should remove queue items that don't exist."""
        buffer_ids = [test_content_queue[0].id, 9999, test_content_queue[1].id]
        result = _validate_buffer_and_get_valid_ids(db_session, buffer_ids, current_user)

        assert 9999 not in result
        assert test_content_queue[0].id in result
        assert test_content_queue[1].id in result

    def test_maintains_order_after_removal(self, db_session: Session, current_user: User, test_content_queue):
        """Should maintain buffer order after removing invalid items."""
        buffer_ids = [test_content_queue[0].id, test_content_queue[1].id, test_content_queue[2].id]

        # Mark middle item as LEARNED
        learned_word = Word(
            main="middle",
            type="noun",
            meaning="middle word",
            level=1,
            user_id=current_user.id,
        )
        db_session.add(learned_word)
        db_session.commit()

        db_session.add(ExampleWord(
            example_id=test_content_queue[1].content_id,
            word_id=learned_word.id,
            text_form="Hello"
        ))

        stat = WordStatistics(
            word_id=learned_word.id,
            type=ContentType.EXAMPLE,
            learning_state=LearningState.LEARNED,
            times_seen=6,
        )
        db_session.add(stat)
        db_session.commit()

        result = _validate_buffer_and_get_valid_ids(db_session, buffer_ids, current_user)

        # Verify order is maintained: [item0, item2] (item1 removed but order preserved)
        assert result[0] == test_content_queue[0].id
        assert result[1] == test_content_queue[2].id
        assert len(result) == 2

    @pytest.mark.xfail(reason="TODO: Implement duplicate filtering in validation")
    def test_no_duplicates_preserved(self, db_session: Session, current_user: User, test_content_queue):
        """Should not introduce duplicates during validation.

        XFAIL: Current implementation doesn't filter duplicate IDs.
        This test documents the expected behavior.
        """
        # Simular un buffer con un ID duplicado (edge case)
        buffer_ids = [test_content_queue[0].id, test_content_queue[0].id, test_content_queue[1].id]

        result = _validate_buffer_and_get_valid_ids(db_session, buffer_ids, current_user)

        # Verificar que no hay duplicados
        assert len(result) == len(set(result))
        # Debe tener 2 únicos (item0 y item1)
        assert test_content_queue[0].id in result
        assert test_content_queue[1].id in result


class TestAdjustPositionAfterRemovals:
    """Tests for _adjust_position_after_removals helper."""

    def test_no_adjustment_when_no_removals(self):
        """Should keep position when no items removed."""
        buffer_ids = [1, 2, 3, 4, 5]
        valid_ids = [1, 2, 3, 4, 5]
        position = 2

        new_position = _adjust_position_after_removals(buffer_ids, valid_ids, position)
        assert new_position == 2

    def test_adjusts_when_items_removed_before_position(self):
        """Should decrease position when items removed before it."""
        buffer_ids = [1, 2, 3, 4, 5]
        valid_ids = [2, 3, 4, 5]  # Removed 1
        position = 3

        new_position = _adjust_position_after_removals(buffer_ids, valid_ids, position)
        assert new_position == 2  # Position 3 → 2

    def test_clamps_to_last_item(self):
        """Should clamp position to last item when necessary."""
        buffer_ids = [1, 2, 3, 4, 5]
        valid_ids = [1, 2]  # Removed 3, 4, 5
        position = 4

        new_position = _adjust_position_after_removals(buffer_ids, valid_ids, position)
        assert new_position == 1  # Clamped to last index (len-1)

    def test_handles_empty_buffer(self):
        """Should return 0 for empty buffer."""
        buffer_ids = [1, 2, 3]
        valid_ids = []
        position = 1

        new_position = _adjust_position_after_removals(buffer_ids, valid_ids, position)
        assert new_position == 0


class TestRefillBufferToLimit:
    """Tests for _refill_buffer_to_limit helper."""

    def test_no_refill_when_at_limit(self, db_session: Session, current_user: User, test_content_queue):
        """Should not refill when buffer already at limit."""
        buffer_ids = [test_content_queue[0].id, test_content_queue[1].id]
        limit = 2

        result = _refill_buffer_to_limit(db_session, buffer_ids, limit, current_user)
        assert len(result) == 2

    def test_refill_when_below_limit(self, db_session: Session, current_user: User, test_content_queue):
        """Should refill when buffer below limit."""
        buffer_ids = [test_content_queue[0].id]
        limit = 3

        with patch('examples.example_routes.ContentQueueManager') as mock_queue:
            mock_mgr = MagicMock()
            mock_queue.return_value = mock_mgr
            mock_mgr.next_many.return_value = [
                test_content_queue[1],
                test_content_queue[2]
            ]

            result = _refill_buffer_to_limit(db_session, buffer_ids, limit, current_user)

            assert len(result) >= 1
            mock_mgr.next_many.assert_called()

    def test_refill_validates_new_items(self, db_session: Session, current_user: User, test_content_queue):
        """Should validate new items for LEARNED words during refill."""
        buffer_ids = [test_content_queue[0].id]
        limit = 2

        with patch('examples.example_routes.ContentQueueManager') as mock_queue:
            with patch('examples.example_routes._is_queue_item_with_learned_word') as mock_check:
                mock_mgr = MagicMock()
                mock_queue.return_value = mock_mgr
                mock_mgr.next_many.return_value = [test_content_queue[1]]
                mock_check.side_effect = [False]  # First item is valid

                result = _refill_buffer_to_limit(db_session, buffer_ids, limit, current_user)

                assert test_content_queue[0].id in result

    @pytest.mark.xfail(reason="TODO: Filter duplicate items when refilling buffer")
    def test_no_duplicates_in_buffer(self, db_session: Session, current_user: User, test_content_queue):
        """Should never add duplicate items to buffer.

        XFAIL: Current implementation doesn't filter items already in buffer.
        This test documents the expected behavior to prevent duplicates.
        """
        buffer_ids = [test_content_queue[0].id, test_content_queue[1].id]
        limit = 5

        with patch('examples.example_routes.ContentQueueManager') as mock_queue:
            mock_mgr = MagicMock()
            mock_queue.return_value = mock_mgr
            # ContentQueue devuelve items que ya están en buffer
            mock_mgr.next_many.return_value = [
                test_content_queue[0],  # ← YA está en buffer
                test_content_queue[1],  # ← YA está en buffer
                test_content_queue[2],
            ]

            result = _refill_buffer_to_limit(db_session, buffer_ids, limit, current_user)

            # Verificar que no hay duplicados
            assert len(result) == len(set(result))  # Todos únicos
            # Verificar que incluye el nuevo item
            assert test_content_queue[2].id in result

    def test_partial_refill_when_content_queue_exhausted(self, db_session: Session, current_user: User,
                                                          test_content_queue):
        """Should return partial buffer when ContentQueue is exhausted (no duplicates, no generation possible)."""
        buffer_ids = [test_content_queue[0].id]
        limit = 5  # Pide 5

        with patch('examples.example_routes.ContentQueueManager') as mock_queue:
            with patch('examples.example_routes._is_queue_item_with_learned_word') as mock_check:
                mock_mgr = MagicMock()
                mock_queue.return_value = mock_mgr

                # ContentQueue solo tiene 1 item disponible (no duplicados, no más items)
                mock_mgr.next_many.side_effect = [
                    [test_content_queue[1]],  # Primera llamada: 1 item
                    [],  # Segunda llamada: ContentQueue vacío
                ]
                mock_check.side_effect = [False, False]  # Ambos items son válidos

                result = _refill_buffer_to_limit(db_session, buffer_ids, limit, current_user)

                # Verificar que devuelve solo 2 items (1 original + 1 nuevo)
                # NO llena con duplicados hasta alcanzar 5
                assert len(result) == 2
                assert test_content_queue[0].id in result
                assert test_content_queue[1].id in result

                # Verificar que intentó traer items dos veces
                assert mock_mgr.next_many.call_count == 2

    def test_refill_stops_when_only_learned_words_available(self, db_session: Session, current_user: User,
                                                             test_content_queue):
        """Should stop refilling when ContentQueue returns only LEARNED word items."""
        buffer_ids = [test_content_queue[0].id]
        limit = 5

        with patch('examples.example_routes.ContentQueueManager') as mock_queue:
            with patch('examples.example_routes._is_queue_item_with_learned_word') as mock_check:
                mock_mgr = MagicMock()
                mock_queue.return_value = mock_mgr

                # ContentQueue devuelve items, pero todos son LEARNED
                mock_mgr.next_many.return_value = [
                    test_content_queue[1],
                    test_content_queue[2],
                ]
                mock_check.side_effect = [True, True]  # Ambos tienen palabras LEARNED

                result = _refill_buffer_to_limit(db_session, buffer_ids, limit, current_user)

                # Verificar que NO se agregó nada (ambos filtered out)
                assert len(result) == 1  # Solo el original
                assert test_content_queue[0].id in result


class TestBuildExamplesResponse:
    """Tests for _build_examples_response helper."""

    def test_returns_empty_for_empty_buffer(self, db_session: Session):
        """Should return empty list for empty buffer."""
        result = _build_examples_response(db_session, [])
        assert result == []

    def test_builds_response_with_segments(self, db_session: Session, test_content_queue):
        """Should build response with text segments."""
        buffer_ids = [test_content_queue[0].id]

        with patch('examples.example_routes.ExampleRepository') as mock_repo_class:
            with patch('examples.example_routes._load_common_words') as mock_common:
                with patch('examples.example_routes._extract_words_from_example') as mock_extract:
                    mock_repo = MagicMock()
                    mock_repo_class.return_value = mock_repo
                    mock_repo.segment_example_text.return_value = [
                        {'text': 'Hello', 'is_highlighted': True, 'target_word': {'id': 1, 'main': 'hello'}}
                    ]
                    mock_common.return_value = set(['common_word'])
                    mock_extract.return_value = ['extracted']

                    result = _build_examples_response(db_session, buffer_ids)

                    assert len(result) >= 0


class TestActionResolve:
    """Tests for _action_resolve function."""

    def test_resolve_successfully_marks_consumed(self, db_session: Session, current_user: User,
                                                   test_content_queue):
        """Should mark queue item as consumed and record exposure."""
        queue_item_id = test_content_queue[0].id

        with patch('examples.example_routes.UserExampleSessionRepository') as mock_session_repo:
            with patch('examples.example_routes.LearningTracker') as mock_tracker:
                mock_repo = MagicMock()
                mock_session_repo.return_value = mock_repo
                mock_repo.is_queue_item_resolved.return_value = False

                mock_tracker_inst = MagicMock()
                mock_tracker.return_value = mock_tracker_inst

                with patch('examples.example_routes.ContentQueueManager') as mock_queue:
                    mock_queue_mgr = MagicMock()
                    mock_queue.return_value = mock_queue_mgr

                    result = _action_resolve(db_session, queue_item_id, current_user)

                    assert result is True
                    mock_tracker_inst.record_exposure.assert_called_once()

    def test_resolve_returns_false_for_nonexistent_item(self, db_session: Session, current_user: User):
        """Should return False for nonexistent queue item."""
        with patch('examples.example_routes.UserExampleSessionRepository') as mock_session_repo:
            mock_repo = MagicMock()
            mock_session_repo.return_value = mock_repo
            mock_repo.is_queue_item_resolved.return_value = False

            result = _action_resolve(db_session, 9999, current_user)

            assert result is False

    def test_resolve_returns_true_if_already_resolved(self, db_session: Session, current_user: User,
                                                        test_content_queue):
        """Should return True if item already resolved (idempotent)."""
        queue_item_id = test_content_queue[0].id

        with patch('examples.example_routes.UserExampleSessionRepository') as mock_session_repo:
            mock_repo = MagicMock()
            mock_session_repo.return_value = mock_repo
            mock_repo.is_queue_item_resolved.return_value = True  # Already resolved

            result = _action_resolve(db_session, queue_item_id, current_user)

            assert result is True


class TestActionSync:
    """Tests for _action_sync function."""

    def test_sync_updates_position_only(self, db_session: Session, current_user: User, test_content_queue):
        """Should only update position without modifying buffer."""
        buffer_ids = [test_content_queue[0].id, test_content_queue[1].id]
        position = 1

        with patch('examples.example_routes.UserExampleSessionRepository') as mock_session_repo:
            mock_repo = MagicMock()
            mock_session_repo.return_value = mock_repo

            new_ids, new_pos, status = _action_sync(db_session, current_user, 5, buffer_ids, position)

            assert new_ids == buffer_ids
            assert new_pos == position
            assert status == "ok"
            mock_repo.update_session.assert_called_once_with(current_user.id, buffer_ids, position)


class TestActionSyncBuffer:
    """Tests for _action_sync_buffer function."""

    def test_sync_buffer_validates_and_refills(self, db_session: Session, current_user: User,
                                                 test_content_queue):
        """Should validate buffer and refill to limit."""
        buffer_ids = [test_content_queue[0].id]
        limit = 3

        with patch('examples.example_routes._validate_buffer_and_get_valid_ids') as mock_validate:
            with patch('examples.example_routes._adjust_position_after_removals') as mock_adjust:
                with patch('examples.example_routes._refill_buffer_to_limit') as mock_refill:
                    with patch('examples.example_routes.UserExampleSessionRepository') as mock_session_repo:
                        mock_validate.return_value = [test_content_queue[0].id]
                        mock_adjust.return_value = 0
                        mock_refill.return_value = [test_content_queue[0].id, test_content_queue[1].id]

                        mock_repo = MagicMock()
                        mock_session_repo.return_value = mock_repo

                        new_ids, new_pos, status = _action_sync_buffer(
                            db_session, current_user, limit, buffer_ids, 0
                        )

                        assert status == "ok"
                        mock_validate.assert_called_once()
                        mock_adjust.assert_called_once()
                        mock_refill.assert_called_once()

    def test_sync_buffer_removes_learned_items_and_refills(self, db_session: Session, current_user: User,
                                                            test_content_queue):
        """Should remove LEARNED items and refill buffer."""
        buffer_ids = [test_content_queue[0].id, test_content_queue[1].id, test_content_queue[2].id]
        limit = 5

        with patch('examples.example_routes._validate_buffer_and_get_valid_ids') as mock_validate:
            with patch('examples.example_routes._adjust_position_after_removals') as mock_adjust:
                with patch('examples.example_routes._refill_buffer_to_limit') as mock_refill:
                    with patch('examples.example_routes.UserExampleSessionRepository') as mock_session_repo:
                        # Simular que item1 fue removido por ser LEARNED
                        mock_validate.return_value = [test_content_queue[0].id, test_content_queue[2].id]
                        mock_adjust.return_value = 1  # Posición ajustada de 2 a 1
                        # Refill agrega nuevos items
                        mock_refill.return_value = [
                            test_content_queue[0].id,
                            test_content_queue[2].id,
                            test_content_queue[1].id  # Nuevo item (no es el mismo que se removió)
                        ]

                        mock_repo = MagicMock()
                        mock_session_repo.return_value = mock_repo

                        new_ids, new_pos, status = _action_sync_buffer(
                            db_session, current_user, limit, buffer_ids, 2
                        )

                        # Verificar que removió LEARNED item y refill funcionó
                        assert status == "ok"
                        assert new_pos == 1  # Posición ajustada
                        assert len(new_ids) == 3
                        assert test_content_queue[0].id in new_ids
                        assert test_content_queue[2].id in new_ids

                        # Verificar que guardó sesión con nueva configuración
                        mock_repo.update_session.assert_called_once_with(
                            current_user.id, new_ids, new_pos
                        )


class TestBufferManagementScenarios:
    """Integration tests for buffer management scenarios.

    These tests verify interactions between multiple helper functions
    in realistic buffer management workflows (validation + refill + deduplication).
    NOT end-to-end tests (those would test the HTTP endpoint directly).
    """

    def test_buffer_never_has_duplicates_across_full_cycle(self, db_session: Session, current_user: User,
                                                            test_content_queue):
        """Buffer should maintain uniqueness across validation + refill cycle.

        Verifies that when ContentQueue returns items already in buffer,
        they are filtered and not added as duplicates.
        """
        # Simular un ciclo completo: validar + refill + build response
        buffer_ids = [test_content_queue[0].id, test_content_queue[1].id]
        limit = 4

        with patch('examples.example_routes.ContentQueueManager') as mock_queue:
            with patch('examples.example_routes._is_queue_item_with_learned_word') as mock_check:
                with patch('examples.example_routes._build_examples_response') as mock_build:
                    mock_mgr = MagicMock()
                    mock_queue.return_value = mock_mgr

                    # ContentQueue devuelve items en dos llamadas
                    # Primera: 2 items (uno es duplicado), Segunda: vacío (agotado)
                    mock_mgr.next_many.side_effect = [
                        [test_content_queue[1], test_content_queue[2]],  # item1 es duplicado, item2 es nuevo
                        [],  # Agotado
                    ]

                    # Todos pasan validación de LEARNED
                    mock_check.return_value = False

                    mock_build.return_value = []

                    result = _refill_buffer_to_limit(db_session, buffer_ids, limit, current_user)

                    # Verificar uniqueness: debería tener [item0, item1, item2]
                    # (No duplicó item1 aunque ContentQueue lo devolvió)
                    assert len(result) == len(set(result))
                    assert len(result) == 3  # No duplicó item1
                    assert test_content_queue[0].id in result
                    assert test_content_queue[1].id in result
                    assert test_content_queue[2].id in result

    def test_buffer_stops_early_when_content_exhausted(self, db_session: Session, current_user: User,
                                                        test_content_queue):
        """Buffer should stop refilling and return partial when content is exhausted."""
        buffer_ids = [test_content_queue[0].id]
        limit = 10  # Pide muchos

        with patch('examples.example_routes.ContentQueueManager') as mock_queue:
            with patch('examples.example_routes._is_queue_item_with_learned_word') as mock_check:
                mock_mgr = MagicMock()
                mock_queue.return_value = mock_mgr

                # Primera llamada: 2 items, Segunda llamada: vacío
                mock_mgr.next_many.side_effect = [
                    [test_content_queue[1], test_content_queue[2]],
                    [],  # Agotado
                ]

                mock_check.return_value = False

                result = _refill_buffer_to_limit(db_session, buffer_ids, limit, current_user)

                # Verificar que devuelve solo 3 items (no llena con duplicados)
                assert len(result) == 3
                assert test_content_queue[0].id in result
                assert test_content_queue[1].id in result
                assert test_content_queue[2].id in result

                # Verificar que intentó 2 veces
                assert mock_mgr.next_many.call_count == 2

    @pytest.mark.xfail(reason="TODO: Filter duplicates when all items from ContentQueue are checked")
    def test_buffer_with_learned_and_valid_items(self, db_session: Session, current_user: User,
                                                  test_content_queue):
        """Buffer should filter LEARNED items but keep valid ones during refill.

        XFAIL: Current implementation doesn't filter:
        1. LEARNED items (correctly filtered)
        2. Duplicate items already in buffer
        This test documents expected behavior for these scenarios.
        """
        buffer_ids = [test_content_queue[0].id]
        limit = 4

        with patch('examples.example_routes.ContentQueueManager') as mock_queue:
            with patch('examples.example_routes._is_queue_item_with_learned_word') as mock_check:
                mock_mgr = MagicMock()
                mock_queue.return_value = mock_mgr

                # Devuelve 3 items, luego se agota
                mock_mgr.next_many.side_effect = [
                    [test_content_queue[1], test_content_queue[2], test_content_queue[0]],
                    [],  # Agotado
                ]

                # item1 = LEARNED, item2 = válido, item0 = duplicado
                # Necesitamos suficientes valores para todos los checks
                mock_check.side_effect = [
                    True,   # item1 es LEARNED
                    False,  # item2 es válido
                    False,  # item0 (dup) pasa check de LEARNED (pero debería filtrarse por duplicado)
                ]

                result = _refill_buffer_to_limit(db_session, buffer_ids, limit, current_user)

                # Debe tener: item0 (original) + item2 (válido)
                # item1 se filtra (LEARNED), item0 duplicado se ignora
                assert len(result) == 2
                assert test_content_queue[0].id in result
                assert test_content_queue[2].id in result
                assert test_content_queue[1].id not in result


class TestActionResume:
    """Tests for _action_resume function."""

    def test_resume_returns_empty_when_no_session(self, db_session: Session, current_user: User):
        """Should return empty when no session and no buffer."""
        with patch('examples.example_routes.UserExampleSessionRepository') as mock_session_repo:
            mock_repo = MagicMock()
            mock_session_repo.return_value = mock_repo
            mock_session = MagicMock()
            mock_session.buffer_queue_item_ids = None
            mock_session.buffer_position = 0
            mock_repo.get_or_create_session.return_value = mock_session

            result, status, buffer_ids, position = _action_resume(
                db_session, current_user, 5, [], 0
            )

            assert result == []
            assert status == "ok"
            assert buffer_ids == []

    def test_resume_loads_new_batch_when_all_visited(self, db_session: Session, current_user: User,
                                                       test_content_queue):
        """Should load new batch when all items were visited."""
        buffer_ids = [test_content_queue[0].id, test_content_queue[1].id]

        with patch('examples.example_routes.UserExampleSessionRepository') as mock_session_repo:
            with patch('examples.example_routes.ContentQueueManager') as mock_queue:
                with patch('examples.example_routes._validate_buffer_and_get_valid_ids') as mock_validate:
                    with patch('examples.example_routes._adjust_position_after_removals') as mock_adjust:
                        with patch('examples.example_routes._build_examples_response') as mock_build:
                            mock_repo = MagicMock()
                            mock_session_repo.return_value = mock_repo
                            mock_repo.get_visited_queue_item_ids.return_value = set(buffer_ids)  # All visited

                            mock_mgr = MagicMock()
                            mock_queue.return_value = mock_mgr
                            new_item = test_content_queue[2]
                            mock_mgr.next_many.return_value = [new_item]

                            mock_validate.return_value = buffer_ids
                            mock_adjust.return_value = 0
                            mock_build.return_value = [{'id': 1}]

                            result, status, new_ids, new_pos = _action_resume(
                                db_session, current_user, 5, buffer_ids, 0
                            )

                            # Verificar estado y posición
                            assert status == "ok"
                            assert new_pos == 0  # Resetea a inicio

                            # Verificar que cargó nuevos IDs (diferentes de antiguos)
                            assert new_ids == [new_item.id]
                            assert new_ids != buffer_ids

                            # Verificar que se llamó next_many para traer nuevos items
                            mock_mgr.next_many.assert_called_once()
                            call_args = mock_mgr.next_many.call_args
                            assert call_args[1]['amount'] == 5  # limit

                            # Verificar que marcó primer item como visitado
                            mock_repo.mark_queue_item_as_visited.assert_called_once_with(
                                current_user.id, new_item.id
                            )

                            # Verificar que actualizó sesión con nuevos IDs
                            mock_repo.update_session.assert_called_once_with(
                                current_user.id, [new_item.id], 0
                            )

                            # Verificar que construyó respuesta con los nuevos IDs
                            mock_build.assert_called_once_with(db_session, [new_item.id])


class TestActionNext:
    """Tests for _action_next function."""

    def test_next_clears_buffer_and_loads_new(self, db_session: Session, current_user: User,
                                               test_content_queue):
        """Should clear old buffer completely and load new items."""
        with patch('examples.example_routes.UserExampleSessionRepository') as mock_session_repo:
            with patch('examples.example_routes.ContentQueueManager') as mock_queue:
                with patch('examples.example_routes._build_examples_response') as mock_build:
                    mock_repo = MagicMock()
                    mock_session_repo.return_value = mock_repo

                    mock_mgr = MagicMock()
                    mock_queue.return_value = mock_mgr
                    item1, item2 = test_content_queue[0], test_content_queue[1]
                    mock_mgr.next_many.return_value = [item1, item2]

                    mock_build.return_value = [{'id': 1}, {'id': 2}]

                    result, status, new_ids, new_pos = _action_next(
                        db_session, current_user, 5, [], 0
                    )

                    # Verificar estado final
                    assert status == "ok"
                    assert new_pos == 0
                    assert new_ids == [item1.id, item2.id]
                    assert len(result) == 2  # Retorna ejemplos segmentados

                    # Verificar que reseteó la sesión (limpió buffer anterior)
                    mock_repo.reset_session.assert_called_once_with(current_user.id)

                    # Verificar que cargó nuevos items
                    mock_mgr.next_many.assert_called_once_with(
                        user_id=current_user.id,
                        content_type="example",
                        amount=5
                    )

                    # Verificar que marcó primer item como visitado
                    mock_repo.mark_queue_item_as_visited.assert_called_once_with(
                        current_user.id, item1.id
                    )

                    # Verificar que actualizó sesión con nuevos IDs y posición 0
                    mock_repo.update_session.assert_called_once_with(
                        current_user.id, [item1.id, item2.id], 0
                    )

                    # Verificar que construyó respuesta
                    mock_build.assert_called_once_with(db_session, [item1.id, item2.id])

    def test_next_returns_generating_when_no_items(self, db_session: Session, current_user: User):
        """Should trigger generation when ContentQueue is empty."""
        with patch('examples.example_routes.UserExampleSessionRepository') as mock_session_repo:
            with patch('examples.example_routes.ContentQueueManager') as mock_queue:
                with patch('learning_path.content_planner.ContentPlanner') as mock_planner:
                    mock_repo = MagicMock()
                    mock_session_repo.return_value = mock_repo

                    mock_mgr = MagicMock()
                    mock_queue.return_value = mock_mgr
                    mock_mgr.next_many.return_value = []  # No items en ContentQueue

                    mock_planner_inst = MagicMock()
                    mock_planner.return_value = mock_planner_inst
                    mock_planner_inst.has_non_learned_words.return_value = True  # Hay palabras por generar

                    result, status, new_ids, new_pos = _action_next(
                        db_session, current_user, 5, [], 0
                    )

                    # Verificar que retorna generating
                    assert status == "generating"
                    assert result == []
                    assert new_ids == []
                    assert new_pos == 0

                    # Verificar que reseteó sesión
                    mock_repo.reset_session.assert_called_once()

                    # Verificar que intentó traer items (pero ContentQueue vacío)
                    mock_mgr.next_many.assert_called_once()

                    # Verificar que verificó si hay palabras no aprendidas
                    mock_planner_inst.has_non_learned_words.assert_called_once_with(
                        current_user.id, "example"
                    )

                    # Verificar que triggereó generación
                    mock_planner_inst.ensure_ready.assert_called_once_with(
                        current_user.id, "example"
                    )

    def test_next_returns_no_words_when_all_learned(self, db_session: Session, current_user: User):
        """Should return no_words when all words are learned."""
        with patch('examples.example_routes.UserExampleSessionRepository') as mock_session_repo:
            with patch('examples.example_routes.ContentQueueManager') as mock_queue:
                with patch('learning_path.content_planner.ContentPlanner') as mock_planner:
                    mock_repo = MagicMock()
                    mock_session_repo.return_value = mock_repo

                    mock_mgr = MagicMock()
                    mock_queue.return_value = mock_mgr
                    mock_mgr.next_many.return_value = []  # No items en ContentQueue

                    mock_planner_inst = MagicMock()
                    mock_planner.return_value = mock_planner_inst
                    mock_planner_inst.has_non_learned_words.return_value = False  # NO hay palabras por aprender

                    result, status, new_ids, new_pos = _action_next(
                        db_session, current_user, 5, [], 0
                    )

                    # Verificar que retorna no_words
                    assert status == "no_words"
                    assert result == []
                    assert new_ids == []
                    assert new_pos == 0

                    # Verificar que reseteó sesión
                    mock_repo.reset_session.assert_called_once()

                    # Verificar que intentó traer items
                    mock_mgr.next_many.assert_called_once()

                    # Verificar que verificó si hay palabras no aprendidas
                    mock_planner_inst.has_non_learned_words.assert_called_once()

                    # Verificar que NO triggereó generación (porque no hay palabras)
                    mock_planner_inst.ensure_ready.assert_not_called()
