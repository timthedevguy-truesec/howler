from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.odm.models.case import Case
from howler.services import case_service

# ---------------------------------------------------------------------------
# create_case()
# ---------------------------------------------------------------------------


class TestCreateCase:
    """Tests for case_service.create_case."""

    @patch("howler.services.case_service.datastore")
    def test_create_case_saves_to_datastore(self, mock_ds_fn):
        """create_case constructs a Case from title/summary and saves it."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_service.create_case("New Case", "A summary", user="admin")

        mock_ds.case.save.assert_called_once()
        saved_id, saved_case = mock_ds.case.save.call_args[0]
        assert saved_id == saved_case.case_id
        assert saved_case.title == "New Case"
        assert saved_case.summary == "A summary"

    @patch("howler.services.case_service.datastore")
    def test_create_case_generates_unique_id(self, mock_ds_fn):
        """create_case auto-generates a unique UUID for each case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_service.create_case("Title A", "Summary A", user="admin")
        case_service.create_case("Title B", "Summary B", user="admin")

        calls = mock_ds.case.save.call_args_list
        id_a = calls[0][0][0]
        id_b = calls[1][0][0]
        assert id_a != id_b

    @patch("howler.services.case_service.datastore")
    def test_create_case_returns_primitives_dict(self, mock_ds_fn):
        """create_case returns the created case as a plain dict."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        result = case_service.create_case("Title", "Summary", user="admin")

        assert isinstance(result, dict)
        assert result["title"] == "Title"
        assert result["summary"] == "Summary"
        assert "case_id" in result

    @patch("howler.services.case_service.datastore")
    def test_create_case_sets_log_entry(self, mock_ds_fn):
        """create_case adds a creation log entry for the given user."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_service.create_case("Title", "Summary", user="admin")

        _, saved_case = mock_ds.case.save.call_args[0]
        assert len(saved_case.log) == 1
        assert saved_case.log[0].user == "admin"

    @patch("howler.services.case_service.datastore")
    def test_create_case_no_user_defaults_to_system(self, mock_ds_fn):
        """create_case uses 'system' as the log user when user='' (the default)."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        case_service.create_case("Title", "Summary")

        _, saved_case = mock_ds.case.save.call_args[0]
        assert len(saved_case.log) == 1
        assert saved_case.log[0].user == "system"

    @patch("howler.services.case_service.datastore")
    def test_create_case_with_case_object(self, mock_ds_fn):
        """create_case accepts a pre-built Case object."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        my_case = Case({"title": "Pre-built Case", "summary": "Pre-built summary"})
        case_service.create_case(case=my_case)

        mock_ds.case.save.assert_called_once()
        saved_id, saved_case = mock_ds.case.save.call_args[0]
        assert saved_id == saved_case.case_id
        assert saved_case.title == "Pre-built Case"
        assert saved_case.summary == "Pre-built summary"


# ---------------------------------------------------------------------------
# update_case()
# ---------------------------------------------------------------------------


class TestUpdateCase:
    """Tests for case_service.update_case."""

    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_not_found(self, mock_ds_fn):
        """update_case raises NotFoundException when case does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = None

        mock_user = MagicMock()
        mock_user.uname = "analyst"

        with pytest.raises(NotFoundException):
            case_service.update_case("case-missing", {"title": "Updated"}, mock_user)

    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_invalid_data_for_immutable_field(self, mock_ds_fn):
        """update_case raises InvalidDataException when an immutable field is supplied."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = Case(
            {
                "case_id": "case-001",
                "title": "T",
                "summary": "S",
                "overview": "O",
                "escalation": "low",
            }
        )

        mock_user = MagicMock()
        mock_user.uname = "analyst"

        with pytest.raises(InvalidDataException):
            case_service.update_case("case-001", {"case_id": "new-id"}, mock_user)

    @patch("howler.services.case_service.datastore")
    def test_update_case_updates_title(self, mock_ds_fn):
        """update_case saves the updated case and returns it."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = Case(
            {
                "case_id": "case-001",
                "title": "Old Title",
                "summary": "S",
                "overview": "O",
                "escalation": "low",
            }
        )

        mock_user = MagicMock()
        mock_user.uname = "analyst"

        result = case_service.update_case("case-001", {"title": "New Title"}, mock_user)

        mock_ds.case.save.assert_called_once()
        assert result.title == "New Title"
        assert result.updated is not None
        assert len(result.log) == 1
        assert result.log[0].key == "title"
        assert result.log[0].user == "analyst"
        assert result.log[0].previous_value == "Old Title"
        assert result.log[0].new_value == "New Title"

    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_invalid_for_updated_field(self, mock_ds_fn):
        """update_case raises InvalidDataException when the immutable 'updated' field is supplied."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = Case(
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"}
        )
        mock_user = MagicMock()
        mock_user.uname = "analyst"

        with pytest.raises(InvalidDataException):
            case_service.update_case("case-001", {"updated": "2024-01-01T00:00:00Z"}, mock_user)

    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_invalid_for_items_field(self, mock_ds_fn):
        """update_case accepts 'items' as a compound field (not immutable) and does not raise."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = Case(
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"}
        )
        mock_user = MagicMock()
        mock_user.uname = "analyst"

        # items is now a compound field — update must succeed without raising
        result = case_service.update_case("case-001", {"items": []}, mock_user)
        assert result is not None
        mock_ds.case.save.assert_called_once()

    @patch("howler.services.case_service.datastore")
    def test_update_case_raises_invalid_when_no_updatable_fields(self, mock_ds_fn):
        """update_case raises InvalidDataException when the update dict is empty."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.get_if_exists.return_value = Case(
            {"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"}
        )
        mock_user = MagicMock()
        mock_user.uname = "analyst"

        with pytest.raises(InvalidDataException):
            case_service.update_case("case-001", {}, mock_user)


# ---------------------------------------------------------------------------
# hide_cases()
# ---------------------------------------------------------------------------


class TestHideCases:
    """Tests for case_service.hide_cases."""

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_sets_visible_false_on_target(self, mock_ds_fn):
        """hide_cases sets visible=False and saves each target case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_ds.case.stream_search.return_value = iter([])

        case_obj = MagicMock()
        case_obj.items = []
        mock_ds.case.get_if_exists.return_value = case_obj

        case_service.hide_cases({"case-001"}, user="analyst")

        mock_ds.case.get_if_exists.assert_called_with("case-001", as_obj=True)
        assert case_obj.visible is False
        mock_ds.case.save.assert_called_with("case-001", case_obj)

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_marks_related_items_not_visible(self, mock_ds_fn):
        """Items in other cases that reference a hidden case ID get visible=False."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        # stream_search returns a related case that is NOT in the hidden set
        mock_ds.case.stream_search.return_value = iter([{"case_id": "case-other"}])

        # The related case has an item pointing to the hidden case ID
        related_item = MagicMock()
        related_item.id = "case-001"
        related_item.visible = True

        unrelated_item = MagicMock()
        unrelated_item.id = "something-else"
        unrelated_item.visible = True

        related_case_obj = MagicMock()
        related_case_obj.items = [related_item, unrelated_item]

        # The target case itself
        target_case_obj = MagicMock()
        target_case_obj.items = []

        mock_ds.case.get_if_exists.side_effect = lambda case_id, as_obj=False: (
            related_case_obj if case_id == "case-other" else target_case_obj
        )

        case_service.hide_cases({"case-001"}, user="analyst")

        # The matching item's visible flag must be set to False
        assert related_item.visible is False
        # The unrelated item must be untouched
        assert unrelated_item.visible is True
        # The related case must be saved with the update
        mock_ds.case.save.assert_any_call("case-other", related_case_obj)
        # A log entry must have been appended to the related case documenting the hidden reference
        related_case_obj.log.append.assert_called_once()
        appended_log = related_case_obj.log.append.call_args[0][0]
        assert "case-001" in appended_log.explanation

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_does_not_save_related_case_when_no_items_match(self, mock_ds_fn):
        """hide_cases does NOT save a related case when none of its items match the hidden IDs."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        # stream_search returns a case whose items don't actually match (stale index)
        mock_ds.case.stream_search.return_value = iter([{"case_id": "case-other"}])

        non_matching_item = MagicMock()
        non_matching_item.id = "unrelated-id"

        related_case_obj = MagicMock()
        related_case_obj.items = [non_matching_item]

        target_case_obj = MagicMock()
        target_case_obj.items = []

        mock_ds.case.get_if_exists.side_effect = lambda case_id, as_obj=False: (
            related_case_obj if case_id == "case-other" else target_case_obj
        )

        case_service.hide_cases(["case-001"], user="analyst")

        # No matching items → related case must NOT be saved
        saved_ids = [call[0][0] for call in mock_ds.case.save.call_args_list]
        assert "case-other" not in saved_ids
        # The target case itself must still be saved
        assert "case-001" in saved_ids

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_skips_case_that_is_itself_being_hidden(self, mock_ds_fn):
        """stream_search results whose case_id is in the hidden set are skipped."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        # stream_search returns the case being hidden itself
        mock_ds.case.stream_search.return_value = iter([{"case_id": "case-001"}])

        case_obj = MagicMock()
        case_obj.items = []
        mock_ds.case.get_if_exists.return_value = case_obj

        case_service.hide_cases({"case-001"}, user="analyst")

        # stream_search returned "case-001" but the loop must have skipped it (continue).
        # The only get_if_exists call should be from the direct hide loop that runs afterwards.
        mock_ds.case.get_if_exists.assert_called_once_with("case-001", as_obj=True)

    @patch("howler.services.case_service.logger")
    @patch("howler.services.case_service.datastore")
    def test_hide_cases_logs_warning_when_case_not_found(self, mock_ds_fn, mock_logger):
        """hide_cases logs a warning when a target case_id does not exist."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_ds.case.stream_search.return_value = iter([])
        mock_ds.case.get_if_exists.return_value = None

        case_service.hide_cases({"case-missing"}, user="analyst")

        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "case-missing" in warning_msg

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_multiple_ids(self, mock_ds_fn):
        """hide_cases processes all supplied case IDs."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_ds.case.stream_search.return_value = iter([])

        case_a = MagicMock()
        case_a.items = []
        case_b = MagicMock()
        case_b.items = []

        mock_ds.case.get_if_exists.side_effect = lambda case_id, as_obj=False: case_a if case_id == "case-a" else case_b

        case_service.hide_cases({"case-a", "case-b"}, user="analyst")

        assert case_a.visible is False
        assert case_b.visible is False
        assert mock_ds.case.save.call_count == 2

    @patch("howler.services.case_service.datastore")
    def test_hide_cases_appends_log_to_hidden_case(self, mock_ds_fn):
        """hide_cases appends a CaseLog entry to each hidden case."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        mock_ds.case.stream_search.return_value = iter([])

        case_obj = MagicMock()
        case_obj.items = []
        case_obj.log = []  # use a real list so append actually works
        mock_ds.case.get_if_exists.return_value = case_obj

        case_service.hide_cases({"case-001"}, user="admin")

        assert len(case_obj.log) == 1
        assert case_obj.log[0].user == "admin"
        assert "hidden" in case_obj.log[0].explanation.lower()


# ---------------------------------------------------------------------------
# delete_cases()
# ---------------------------------------------------------------------------


class TestDeleteCases:
    """Tests for case_service.delete_cases."""

    @patch("howler.services.case_service.datastore")
    def test_delete_cases_calls_delete_by_query(self, mock_ds_fn):
        """delete_cases calls delete_by_query with a query covering all supplied case IDs."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.stream_search.return_value = iter([])

        case_service.delete_cases({"case-del"})

        mock_ds.case.delete_by_query.assert_called_once_with("case_id:(case-del)")

    @patch("howler.services.case_service.datastore")
    def test_delete_cases_removes_cross_case_item_references(self, mock_ds_fn):
        """delete_cases removes CaseItem entries that reference a deleted case from other cases."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.stream_search.return_value = iter([{"case_id": "case-other"}])

        matching_item = MagicMock()
        matching_item.id = "case-del"
        unrelated_item = MagicMock()
        unrelated_item.id = "other-id"

        related_case = MagicMock()
        related_case.items = [matching_item, unrelated_item]
        mock_ds.case.get_if_exists.return_value = related_case

        case_service.delete_cases({"case-del"})

        assert len(related_case.items) == 1
        assert related_case.items[0].id == "other-id"
        mock_ds.case.save.assert_called_once_with("case-other", related_case)

    @patch("howler.services.case_service.datastore")
    def test_delete_cases_skips_stream_results_in_delete_set(self, mock_ds_fn):
        """delete_cases does not attempt cross-reference cleanup on cases being deleted."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        # stream_search returns the very case being deleted
        mock_ds.case.stream_search.return_value = iter([{"case_id": "case-del"}])

        case_service.delete_cases({"case-del"})

        # The skip (continue) must prevent get_if_exists from being called
        mock_ds.case.get_if_exists.assert_not_called()

    @patch("howler.services.case_service.datastore")
    def test_delete_cases_returns_delete_by_query_result(self, mock_ds_fn):
        """delete_cases returns the boolean result of delete_by_query."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds
        mock_ds.case.stream_search.return_value = iter([])
        mock_ds.case.delete_by_query.return_value = True

        result = case_service.delete_cases({"case-del"})

        assert result is True


# ---------------------------------------------------------------------------
# append_case_item()
# ---------------------------------------------------------------------------


class TestAppendCaseItem:
    """Tests for case_service.append_case_item."""

    def _make_case(self, case_id="case-001"):
        return Case({"case_id": case_id, "title": "T", "summary": "S", "overview": "O", "escalation": "low"})

    @patch("howler.services.case_service.append_hit")
    @patch("howler.services.case_service.Case")
    def test_dispatches_to_append_hit(self, mock_case_cls, mock_append_hit):
        """append_case_item dispatches to append_hit for item_type='hit'."""
        _case = self._make_case()
        mock_case_cls.store.get_if_exists.return_value = (_case, "1")

        case_service.append_case_item("case-001", item_type="hit", item_value="hit-001")

        mock_append_hit.assert_called_once()
        item_arg = mock_append_hit.call_args[0][1]
        assert item_arg.value == "hit-001"
        assert item_arg.type == "hit"

    @patch("howler.services.case_service.append_observable")
    @patch("howler.services.case_service.Case")
    def test_dispatches_to_append_observable(self, mock_case_cls, mock_append_observable):
        """append_case_item dispatches to append_observable for item_type='observable'."""
        _case = self._make_case()
        mock_case_cls.store.get_if_exists.return_value = (_case, "1")

        case_service.append_case_item("case-001", item_type="observable", item_value="obs-001")

        mock_append_observable.assert_called_once()

    @patch("howler.services.case_service.append_case")
    @patch("howler.services.case_service.Case")
    def test_dispatches_to_append_case(self, mock_case_cls, mock_append_case):
        """append_case_item dispatches to append_case for item_type='case'."""
        _case = self._make_case()
        mock_case_cls.store.get_if_exists.return_value = (_case, "1")

        case_service.append_case_item("case-001", item_type="case", item_value="case-002")

        mock_append_case.assert_called_once()

    @patch("howler.services.case_service.Case")
    def test_raises_not_found_when_case_missing(self, mock_case_cls):
        """append_case_item raises NotFoundException when the case does not exist."""
        mock_case_cls.store.get_if_exists.return_value = (None, None)

        with pytest.raises(NotFoundException):
            case_service.append_case_item("case-missing", item_type="hit", item_value="hit-001")

    @patch("howler.services.case_service.Case")
    def test_raises_invalid_when_type_and_value_missing(self, mock_case_cls):
        """append_case_item raises InvalidDataException when both item_type and item_value are absent."""
        _case = self._make_case()
        mock_case_cls.store.get_if_exists.return_value = (_case, "1")

        with pytest.raises(InvalidDataException):
            case_service.append_case_item("case-001")

    @patch("howler.services.case_service.Case")
    def test_raises_invalid_for_unknown_item_type(self, mock_case_cls):
        """append_case_item raises InvalidDataException for an unrecognised item_type."""
        _case = self._make_case()
        mock_case_cls.store.get_if_exists.return_value = (_case, "1")

        with pytest.raises(InvalidDataException):
            case_service.append_case_item("case-001", item_type="bogus", item_value="val-001")

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.append_hit")
    @patch("howler.services.case_service.Case")
    def test_emits_cases_event_after_dispatch(self, mock_case_cls, mock_append_hit, mock_event_service):
        """append_case_item emits a 'cases' event after the handler succeeds."""
        _case = self._make_case()
        mock_case_cls.store.get_if_exists.return_value = (_case, "version-1")

        case_service.append_case_item("case-001", item_type="hit", item_value="hit-001")

        mock_event_service.emit.assert_called_once_with(
            "cases", {"case": _case.as_primitives(), "version": "version-1"}
        )

    @patch("howler.services.case_service.append_hit")
    @patch("howler.services.case_service.Case")
    def test_accepts_pre_built_case_item(self, mock_case_cls, mock_append_hit):
        """append_case_item accepts a pre-built CaseItem and skips construction."""
        from howler.odm.models.case import CaseItem

        _case = self._make_case()
        mock_case_cls.store.get_if_exists.return_value = (_case, "1")

        pre_built = CaseItem({"type": "hit", "value": "hit-001", "path": "custom/"})
        case_service.append_case_item("case-001", item=pre_built)

        mock_append_hit.assert_called_once_with(_case, pre_built)

    @patch("howler.services.case_service.Case")
    def test_uses_default_path_when_item_path_is_empty(self, mock_case_cls):
        """append_case_item falls back to 'ungrouped-related/' when item_path is falsy."""
        from howler.odm.models.case import CaseItem

        _case = self._make_case()
        mock_case_cls.store.get_if_exists.return_value = (_case, "1")

        original_ci = CaseItem

        with patch("howler.services.case_service.CaseItem", side_effect=lambda d: original_ci(d)) as mock_ci:
            with patch("howler.services.case_service.append_hit"):
                case_service.append_case_item("case-001", item_type="hit", item_value="hit-001", item_path="")
                call_kwargs = mock_ci.call_args[0][0]
                assert call_kwargs["path"] == "ungrouped-related/"


# ---------------------------------------------------------------------------
# append_hit()
# ---------------------------------------------------------------------------


class TestAppendHit:
    """Tests for case_service.append_hit."""

    def _make_case(self):
        return Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})

    def _make_item(self, value="hit-001", path="ungrouped-related/"):
        from howler.odm.models.case import CaseItem

        return CaseItem({"type": "hit", "value": value, "path": path})

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.Hit")
    def test_appends_hit_and_adds_backreference(self, mock_hit_cls, mock_backref, mock_event_service):
        """append_hit appends the item to the case, saves it, and creates a back-reference."""
        _case = self._make_case()
        _case.save = MagicMock(return_value=True)

        hit = MagicMock()
        hit.howler.analytic = "test-analytic"
        hit.howler.id = "hit-001"
        mock_hit_cls.store.get_if_exists.return_value = (hit, "v1")

        item = self._make_item()
        case_service.append_hit(_case, item)

        assert item in _case.items
        _case.save.assert_called_once()
        mock_backref.assert_called_once_with(hit, "case-001")

    @patch("howler.services.case_service.Hit")
    def test_raises_invalid_when_duplicate(self, mock_hit_cls):
        """append_hit raises InvalidDataException when the hit is already in the case."""
        from howler.odm.models.case import CaseItem

        _case = self._make_case()
        existing = CaseItem({"type": "hit", "value": "hit-001", "path": "alerts/"})
        _case.items.append(existing)

        item = self._make_item(value="hit-001")
        with pytest.raises(InvalidDataException):
            case_service.append_hit(_case, item)

    @patch("howler.services.case_service.Hit")
    def test_raises_not_found_when_hit_missing(self, mock_hit_cls):
        """append_hit raises NotFoundException when the hit does not exist."""
        _case = self._make_case()
        mock_hit_cls.store.get_if_exists.return_value = (None, None)

        item = self._make_item()
        with pytest.raises(NotFoundException):
            case_service.append_hit(_case, item)

    @patch("howler.services.case_service.Hit")
    def test_raises_invalid_for_wrong_item_type(self, mock_hit_cls):
        """append_hit raises InvalidDataException when item.type is not 'hit'."""
        from howler.odm.models.case import CaseItem

        _case = self._make_case()
        wrong_item = CaseItem({"type": "observable", "value": "obs-001", "path": "ungrouped-related/"})

        with pytest.raises(InvalidDataException):
            case_service.append_hit(_case, wrong_item)

    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.Hit")
    def test_raises_datastore_exception_when_save_fails(self, mock_hit_cls, mock_backref):
        """append_hit raises DataStoreException when case.save() returns False."""
        from howler.datastore.exceptions import DataStoreException

        _case = self._make_case()
        _case.save = MagicMock(return_value=False)

        hit = MagicMock()
        hit.howler.analytic = "analytic"
        hit.howler.id = "hit-001"
        mock_hit_cls.store.get_if_exists.return_value = (hit, "v1")

        item = self._make_item()
        with pytest.raises(DataStoreException):
            case_service.append_hit(_case, item)

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.Hit")
    def test_sets_path_from_analytic_when_ungrouped(self, mock_hit_cls, mock_backref, mock_event_service):
        """append_hit auto-sets item path from the hit's analytic when path is 'ungrouped-related/'."""
        _case = self._make_case()
        _case.save = MagicMock(return_value=True)

        hit = MagicMock()
        hit.howler.analytic = "my-analytic"
        hit.howler.id = "hit-001"
        mock_hit_cls.store.get_if_exists.return_value = (hit, "v1")

        item = self._make_item(path="ungrouped-related/")
        case_service.append_hit(_case, item)

        assert item.path == "alerts/my-analytic (hit-001)"

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.Hit")
    def test_preserves_custom_path(self, mock_hit_cls, mock_backref, mock_event_service):
        """append_hit does not override item path when a custom path is provided."""
        _case = self._make_case()
        _case.save = MagicMock(return_value=True)

        hit = MagicMock()
        hit.howler.analytic = "my-analytic"
        hit.howler.id = "hit-001"
        mock_hit_cls.store.get_if_exists.return_value = (hit, "v1")

        item = self._make_item(path="custom/path/")
        case_service.append_hit(_case, item)

        assert item.path == "custom/path/"

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.Hit")
    def test_emits_hits_event(self, mock_hit_cls, mock_backref, mock_event_service):
        """append_hit emits a 'hits' event after successfully appending."""
        _case = self._make_case()
        _case.save = MagicMock(return_value=True)

        hit = MagicMock()
        hit.howler.analytic = "analytic"
        hit.howler.id = "hit-001"
        mock_hit_cls.store.get_if_exists.return_value = (hit, "v1")

        item = self._make_item()
        case_service.append_hit(_case, item)

        mock_event_service.emit.assert_called_once_with("hits", {"hit": hit.as_primitives(), "version": "v1"})


# ---------------------------------------------------------------------------
# append_observable()
# ---------------------------------------------------------------------------


class TestAppendObservable:
    """Tests for case_service.append_observable."""

    def _make_case(self):
        return Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})

    def _make_item(self, value="obs-001", path="ungrouped-related/"):
        from howler.odm.models.case import CaseItem

        return CaseItem({"type": "observable", "value": value, "path": path})

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.Observable")
    def test_appends_observable_and_adds_backreference(self, mock_obs_cls, mock_backref, mock_event_service):
        """append_observable appends the item, saves the case, and creates a back-reference."""
        _case = self._make_case()
        _case.save = MagicMock(return_value=True)

        observable = MagicMock()
        observable.howler.id = "obs-001"
        mock_obs_cls.store.get_if_exists.return_value = (observable, "v1")

        item = self._make_item()
        case_service.append_observable(_case, item)

        assert item in _case.items
        _case.save.assert_called_once()
        mock_backref.assert_called_once_with(observable, "case-001")

    @patch("howler.services.case_service.Observable")
    def test_raises_invalid_when_duplicate(self, mock_obs_cls):
        """append_observable raises InvalidDataException when the observable is already in the case."""
        from howler.odm.models.case import CaseItem

        _case = self._make_case()
        existing = CaseItem({"type": "observable", "value": "obs-001", "path": "observables/"})
        _case.items.append(existing)

        item = self._make_item(value="obs-001")
        with pytest.raises(InvalidDataException):
            case_service.append_observable(_case, item)

    @patch("howler.services.case_service.Observable")
    def test_raises_not_found_when_observable_missing(self, mock_obs_cls):
        """append_observable raises NotFoundException when the observable does not exist."""
        _case = self._make_case()
        mock_obs_cls.store.get_if_exists.return_value = (None, None)

        item = self._make_item()
        with pytest.raises(NotFoundException):
            case_service.append_observable(_case, item)

    @patch("howler.services.case_service.Observable")
    def test_raises_invalid_for_wrong_item_type(self, mock_obs_cls):
        """append_observable raises InvalidDataException when item.type is not 'observable'."""
        from howler.odm.models.case import CaseItem

        _case = self._make_case()
        wrong_item = CaseItem({"type": "hit", "value": "hit-001", "path": "ungrouped-related/"})

        with pytest.raises(InvalidDataException):
            case_service.append_observable(_case, wrong_item)

    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.Observable")
    def test_raises_datastore_exception_when_save_fails(self, mock_obs_cls, mock_backref):
        """append_observable raises DataStoreException when case.save() returns False."""
        from howler.datastore.exceptions import DataStoreException

        _case = self._make_case()
        _case.save = MagicMock(return_value=False)

        observable = MagicMock()
        observable.howler.id = "obs-001"
        mock_obs_cls.store.get_if_exists.return_value = (observable, "v1")

        item = self._make_item()
        with pytest.raises(DataStoreException):
            case_service.append_observable(_case, item)

    @patch("howler.services.case_service.event_service")
    @patch("howler.services.case_service.add_backreference")
    @patch("howler.services.case_service.Observable")
    def test_sets_path_from_observable_id_when_ungrouped(self, mock_obs_cls, mock_backref, mock_event_service):
        """append_observable auto-sets item path from observable ID when path is 'ungrouped-related/'."""
        _case = self._make_case()
        _case.save = MagicMock(return_value=True)

        observable = MagicMock()
        observable.howler.id = "obs-001"
        mock_obs_cls.store.get_if_exists.return_value = (observable, "v1")

        item = self._make_item(path="ungrouped-related/")
        case_service.append_observable(_case, item)

        assert item.path == "observables/obs-001"


# ---------------------------------------------------------------------------
# append_case()
# ---------------------------------------------------------------------------


class TestAppendCaseRef:
    """Tests for case_service.append_case."""

    def _make_case(self, case_id="case-001"):
        return Case({"case_id": case_id, "title": "T", "summary": "S", "overview": "O", "escalation": "low"})

    def _make_item(self, value="case-002", path="ungrouped-related/"):
        from howler.odm.models.case import CaseItem

        return CaseItem({"type": "case", "value": value, "path": path})

    @patch("howler.services.case_service.Case")
    def test_appends_referenced_case(self, mock_case_cls):
        """append_case appends the referenced case item and saves the parent case."""
        parent = self._make_case("case-001")
        parent.save = MagicMock(return_value=True)

        referenced = self._make_case("case-002")
        mock_case_cls.store.get_if_exists.return_value = referenced

        item = self._make_item(value="case-002")
        case_service.append_case(parent, item)

        assert item in parent.items
        parent.save.assert_called_once()

    @patch("howler.services.case_service.Case")
    def test_raises_invalid_when_duplicate(self, mock_case_cls):
        """append_case raises InvalidDataException when the referenced case is already in the parent."""
        from howler.odm.models.case import CaseItem

        parent = self._make_case("case-001")
        existing = CaseItem({"type": "case", "value": "case-002", "path": "cases/"})
        parent.items.append(existing)

        item = self._make_item(value="case-002")
        with pytest.raises(InvalidDataException):
            case_service.append_case(parent, item)

    @patch("howler.services.case_service.Case")
    def test_raises_not_found_when_referenced_case_missing(self, mock_case_cls):
        """append_case raises NotFoundException when the referenced case does not exist."""
        parent = self._make_case("case-001")
        mock_case_cls.store.get_if_exists.return_value = None

        item = self._make_item(value="case-999")
        with pytest.raises(NotFoundException):
            case_service.append_case(parent, item)

    @patch("howler.services.case_service.Case")
    def test_raises_invalid_for_wrong_item_type(self, mock_case_cls):
        """append_case raises InvalidDataException when item.type is not 'case'."""
        from howler.odm.models.case import CaseItem

        parent = self._make_case("case-001")
        wrong_item = CaseItem({"type": "hit", "value": "hit-001", "path": "ungrouped-related/"})

        with pytest.raises(InvalidDataException):
            case_service.append_case(parent, wrong_item)

    @patch("howler.services.case_service.Case")
    def test_sets_path_from_referenced_case_id_when_ungrouped(self, mock_case_cls):
        """append_case builds item path from referenced case ID when path is 'ungrouped-related/'."""
        parent = self._make_case("case-001")
        parent.save = MagicMock(return_value=True)

        referenced = self._make_case("case-002")
        mock_case_cls.store.get_if_exists.return_value = referenced

        item = self._make_item(value="case-002", path="ungrouped-related/")
        case_service.append_case(parent, item)

        assert item.path == "cases/case-002"

    @patch("howler.services.case_service.Case")
    def test_raises_datastore_exception_when_save_fails(self, mock_case_cls):
        """append_case raises DataStoreException when case.save() returns False."""
        from howler.datastore.exceptions import DataStoreException

        parent = self._make_case("case-001")
        parent.save = MagicMock(return_value=False)

        referenced = self._make_case("case-002")
        mock_case_cls.store.get_if_exists.return_value = referenced

        item = self._make_item(value="case-002")
        with pytest.raises(DataStoreException):
            case_service.append_case(parent, item)


# ---------------------------------------------------------------------------
# append_table / append_lead / append_reference()
# ---------------------------------------------------------------------------


class TestAppendUnimplemented:
    """Tests for the not-yet-implemented append handlers."""

    def _make_case(self):
        return Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})

    def _make_item(self, item_type: str):
        from howler.odm.models.case import CaseItem

        return CaseItem({"type": item_type, "value": "val-001", "path": "ungrouped-related/"})

    def test_append_table_raises_not_implemented(self):
        """append_table always raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            case_service.append_table(self._make_case(), self._make_item("table"))

    def test_append_lead_raises_not_implemented(self):
        """append_lead always raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            case_service.append_lead(self._make_case(), self._make_item("lead"))

    def test_append_reference_raises_not_implemented(self):
        """append_reference always raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            case_service.append_reference(self._make_case(), self._make_item("reference"))

    def test_append_table_raises_invalid_for_wrong_type(self):
        """append_table raises InvalidDataException for a non-table item type."""
        with pytest.raises(InvalidDataException):
            case_service.append_table(self._make_case(), self._make_item("hit"))

    def test_append_lead_raises_invalid_for_wrong_type(self):
        """append_lead raises InvalidDataException for a non-lead item type."""
        with pytest.raises(InvalidDataException):
            case_service.append_lead(self._make_case(), self._make_item("hit"))

    def test_append_reference_raises_invalid_for_wrong_type(self):
        """append_reference raises InvalidDataException for a non-reference item type."""
        with pytest.raises(InvalidDataException):
            case_service.append_reference(self._make_case(), self._make_item("hit"))


# ---------------------------------------------------------------------------
# add_backreference()
# ---------------------------------------------------------------------------


class TestAddBackreference:
    """Tests for case_service.add_backreference."""

    @patch("howler.services.case_service.datastore")
    def test_adds_case_id_to_related(self, mock_ds_fn):
        """add_backreference appends the case_id to backing_obj.howler.related and saves."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        backing = MagicMock()
        backing.__class__.__name__ = "hit"
        backing.howler.related = []
        backing.howler.id = "hit-001"

        case_service.add_backreference(backing, "case-001")

        assert "case-001" in backing.howler.related
        mock_ds["hit"].save.assert_called_once_with("hit-001", backing)

    @patch("howler.services.case_service.datastore")
    def test_is_noop_when_backreference_already_exists(self, mock_ds_fn):
        """add_backreference does not save when the case_id is already in related."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        backing = MagicMock()
        backing.__class__.__name__ = "hit"
        backing.howler.related = ["case-001"]
        backing.howler.id = "hit-001"

        case_service.add_backreference(backing, "case-001")

        mock_ds["hit"].save.assert_not_called()

    def test_raises_invalid_when_backing_obj_is_none(self):
        """add_backreference raises InvalidDataException when backing_obj is None."""
        with pytest.raises(InvalidDataException):
            case_service.add_backreference(None, "case-001")

    def test_raises_invalid_when_case_id_is_empty(self):
        """add_backreference raises InvalidDataException when case_id is empty."""
        backing = MagicMock()
        backing.howler.related = []

        with pytest.raises(InvalidDataException):
            case_service.add_backreference(backing, "")

    @patch("howler.services.case_service.datastore")
    def test_uses_lowercase_class_name_as_index(self, mock_ds_fn):
        """add_backreference derives the datastore index from the backing object's class name."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        backing = MagicMock()
        backing.__class__.__name__ = "Observable"
        backing.howler.related = []
        backing.howler.id = "obs-001"

        case_service.add_backreference(backing, "case-001")

        mock_ds["Observable"].save.assert_called_once_with("obs-001", backing)


# ---------------------------------------------------------------------------
# remove_backreference()
# ---------------------------------------------------------------------------


class TestRemoveBackreference:
    """Tests for case_service.remove_backreference."""

    @patch("howler.services.case_service.datastore")
    def test_removes_case_id_from_related(self, mock_ds_fn):
        """remove_backreference removes the case_id from howler.related and saves."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        backing = MagicMock()
        backing.__class__.__name__ = "hit"
        backing.howler.related = ["case-001", "case-002"]
        backing.howler.id = "hit-001"

        case_service.remove_backreference(backing, "case-001")

        assert "case-001" not in backing.howler.related
        mock_ds["hit"].save.assert_called_once_with("hit-001", backing)

    @patch("howler.services.case_service.datastore")
    def test_is_noop_when_case_id_not_in_related(self, mock_ds_fn):
        """remove_backreference does not save when the case_id is not in related."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        backing = MagicMock()
        backing.__class__.__name__ = "hit"
        backing.howler.related = ["case-999"]
        backing.howler.id = "hit-001"

        case_service.remove_backreference(backing, "case-001")

        mock_ds["hit"].save.assert_not_called()

    def test_raises_invalid_when_backing_obj_is_none(self):
        """remove_backreference raises InvalidDataException when backing_obj is None."""
        with pytest.raises(InvalidDataException):
            case_service.remove_backreference(None, "case-001")

    def test_raises_invalid_when_case_id_is_empty(self):
        """remove_backreference raises InvalidDataException when case_id is empty."""
        backing = MagicMock()
        backing.howler.related = []

        with pytest.raises(InvalidDataException):
            case_service.remove_backreference(backing, "")


# ---------------------------------------------------------------------------
# remove_case_item()
# ---------------------------------------------------------------------------


class TestRemoveCaseItem:
    """Tests for case_service.remove_case_item."""

    def _make_case_with_item(self, item_type="hit", item_value="hit-001"):
        from howler.odm.models.case import CaseItem

        _case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        _case.save = MagicMock(return_value=True)

        case_item = CaseItem({"type": item_type, "value": item_value, "path": "alerts/"})
        case_item["id"] = item_value
        _case.items.append(case_item)
        return _case, case_item

    @patch("howler.services.case_service.remove_backreference")
    @patch("howler.services.case_service.datastore")
    @patch("howler.services.case_service.Case")
    def test_removes_item_and_cleans_backreference(self, mock_case_cls, mock_ds_fn, mock_remove_backref):
        """remove_case_item removes the item from the case and calls remove_backreference."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        _case, case_item = self._make_case_with_item()
        mock_case_cls.store.get_if_exists.return_value = _case

        backing = MagicMock()
        mock_ds.__getitem__.return_value.get_if_exists.return_value = backing

        case_service.remove_case_item("case-001", item_value="hit-001")

        assert case_item not in _case.items
        _case.save.assert_called_once()
        mock_remove_backref.assert_called_once_with(backing, "case-001")

    @patch("howler.services.case_service.Case")
    def test_raises_not_found_when_case_missing(self, mock_case_cls):
        """remove_case_item raises NotFoundException when the case does not exist."""
        mock_case_cls.store.get_if_exists.return_value = None

        with pytest.raises(NotFoundException):
            case_service.remove_case_item("case-missing", item_value="hit-001")

    @patch("howler.services.case_service.Case")
    def test_raises_not_found_when_item_missing(self, mock_case_cls):
        """remove_case_item raises NotFoundException when the item does not exist in the case."""
        _case = Case({"case_id": "case-001", "title": "T", "summary": "S", "overview": "O", "escalation": "low"})
        mock_case_cls.store.get_if_exists.return_value = _case

        with pytest.raises(NotFoundException):
            case_service.remove_case_item("case-001", item_value="nonexistent")

    @patch("howler.services.case_service.datastore")
    @patch("howler.services.case_service.Case")
    def test_raises_datastore_exception_when_save_fails(self, mock_case_cls, mock_ds_fn):
        """remove_case_item raises DataStoreException when case.save() returns False."""
        from howler.datastore.exceptions import DataStoreException

        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        _case, _ = self._make_case_with_item()
        _case.save = MagicMock(return_value=False)
        mock_case_cls.store.get_if_exists.return_value = _case
        mock_ds.__getitem__.return_value.get_if_exists.return_value = MagicMock()

        with pytest.raises(DataStoreException):
            case_service.remove_case_item("case-001", item_value="hit-001")

    @patch("howler.services.case_service.remove_backreference")
    @patch("howler.services.case_service.datastore")
    @patch("howler.services.case_service.Case")
    def test_skips_backreference_when_backing_obj_not_found(self, mock_case_cls, mock_ds_fn, mock_remove_backref):
        """remove_case_item skips remove_backreference when backing object no longer exists."""
        mock_ds = MagicMock()
        mock_ds_fn.return_value = mock_ds

        _case, _ = self._make_case_with_item()
        mock_case_cls.store.get_if_exists.return_value = _case
        mock_ds.__getitem__.return_value.get_if_exists.return_value = None

        case_service.remove_case_item("case-001", item_value="hit-001")

        mock_remove_backref.assert_not_called()
        _case.save.assert_called_once()
