"""Case service module for managing security investigation cases.

This module provides functionality for creating, updating, retrieving, and managing
cases - collections of security alerts and investigation data organized by analysts.
"""

from typing import Any, overload

from prometheus_client import Counter

import howler.services.event_service as event_service
from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.common.loader import APP_NAME, datastore
from howler.common.logging import get_logger
from howler.datastore.exceptions import DataStoreException
from howler.odm.models.case import Case, CaseItem, CaseItemTypes, CaseLog
from howler.odm.models.hit import Hit
from howler.odm.models.observable import Observable
from howler.odm.models.user import User

logger = get_logger(__file__)

CREATED_CASES = Counter(f"{APP_NAME.replace('-', '_')}_created_cases_total", "The number of created cases")


@overload
def create_case(*, case: Case) -> dict[str, Any]: ...


@overload
def create_case(title: str, summary: str, user: str = "") -> dict[str, Any]: ...


def create_case(title: str = "", summary: str = "", user: str = "", *, case: Case | None = None) -> dict[str, Any]:  # type: ignore
    """Create a new case in the datastore.

    Args:
        title: Title of the case
        summary: Short summary of the case
        user: Username to record in the creation log
        case: Pre-built Case object (if provided, title and summary are ignored)

    Returns:
        dict: The created case as a primitives dictionary

    Raises:
        ResourceExists: If a case with the same ID already exists
    """
    if case is None:
        case = Case({"title": title, "summary": summary})
        items = []
    else:
        items = list(case.items)
        case.items = []

    case.log = [CaseLog({"timestamp": "NOW", "explanation": "Case created", "user": user or "system"})]

    CREATED_CASES.inc()
    datastore().case.save(case.case_id, case)

    for item in items:
        append_case_item(case.case_id, item=item)

    if items:
        return datastore().case.get_if_exists(case.case_id, as_obj=False)
    return case.as_primitives()


def hide_cases(case_ids: set[str], user: str) -> None:
    """Hide a set of cases by marking them and their references as not visible.

    Sets visible=False on all matching cases, and also sets visible=False on any
    CaseItem in other cases that references one of the hidden cases.

    Args:
        case_ids (set[str]): The IDs of the cases to hide
        user (str): The username performing the hide action
    """
    ds = datastore()

    items_query = f"items.id:({' OR '.join(case_ids)})"
    for case in ds.case.stream_search(items_query, as_obj=False):
        related_case_id = case["case_id"]
        if related_case_id in case_ids:
            continue

        related_case = ds.case.get_if_exists(related_case_id, as_obj=True)
        if related_case:
            hidden_ids: list[str] = []
            for item in related_case.items:
                if item.id in case_ids:
                    item.visible = False
                    hidden_ids.append(item.id)
            if hidden_ids:
                related_case.log.append(
                    CaseLog(
                        {
                            "timestamp": "NOW",
                            "user": user,
                            "explanation": f"Referenced case(s) hidden: {', '.join(hidden_ids)}",
                        }
                    )
                )
                ds.case.save(related_case_id, related_case)

    for case_id in case_ids:
        case = ds.case.get_if_exists(case_id, as_obj=True)
        if case:
            case.visible = False
            case.log.append(
                CaseLog(
                    {
                        "timestamp": "NOW",
                        "user": user,
                        "explanation": "Case set to hidden",
                    }
                )
            )
            ds.case.save(case_id, case)
        else:
            logger.warning(f"Case {case_id} not found when attempting to hide")


def delete_cases(case_ids: set[str]) -> bool:
    """Delete a set of cases from the datastore.

    Also removes any CaseItem references to the deleted cases from other cases.

    Args:
        case_ids (set[str]): The IDs of the cases to delete

    Returns:
        bool: Was the deletion successful?
    """
    ds = datastore()

    items_query = f"items.id:({' OR '.join(case_ids)})"
    for case in ds.case.stream_search(items_query, as_obj=False):
        related_case_id = case["case_id"]
        if related_case_id in case_ids:
            continue

        related_case = ds.case.get_if_exists(related_case_id, as_obj=True)
        if related_case:
            related_case.items = [item for item in related_case.items if item.id not in case_ids]
            ds.case.save(related_case_id, related_case)

    return ds.case.delete_by_query(f"case_id:({' OR '.join(case_ids)})")


def update_case(case_id: str, case_data: dict[str, Any], user: User) -> Case:
    """Update one or more properties of a case in the database.

    This function validates the provided fields, applies changes to the case object,
    appends a CaseLog entry for each changed property.

    Args:
        case_id: Unique identifier of the case to update
        case_data: Dictionary containing fields to update
        user: User object representing the requesting user

    Returns:
        Updated Case object

    Raises:
        NotFoundException: If the case doesn't exist
        InvalidDataException: If invalid or immutable fields are provided
    """
    ds = datastore()

    case = ds.case.get_if_exists(case_id, as_obj=True)
    if case is None:
        raise NotFoundException(f"Case {case_id} does not exist")

    immutable_fields = {"case_id", "created", "updated"}
    compound_fields = {"items", "enrichments", "rules", "tasks"}

    immutable_violations = set(case_data.keys()) & immutable_fields
    if immutable_violations:
        raise InvalidDataException(f"Cannot modify immutable field(s): {', '.join(immutable_violations)}")

    updatable = {k: v for k, v in case_data.items() if k not in immutable_fields}
    if not updatable:
        raise InvalidDataException("No valid fields provided for update")

    for key, new_value in updatable.items():
        previous_value = getattr(case, key, None)

        if key in compound_fields:
            explanation = f"Updated {key}"
            prev_str = None
            new_str = None
        elif isinstance(previous_value, list) and isinstance(new_value, list):
            prev_set = set(str(v) for v in previous_value)
            new_set = set(str(v) for v in new_value)
            added = sorted(new_set - prev_set)
            removed = sorted(prev_set - new_set)

            parts: list[str] = []
            if added:
                parts.append(f"added [{', '.join(added)}]")
            if removed:
                parts.append(f"removed [{', '.join(removed)}]")

            explanation = f"Updated {key}: {'; '.join(parts)}" if parts else f"Updated {key} (no changes)"
            prev_str = ", ".join(str(v) for v in previous_value) or None
            new_str = ", ".join(str(v) for v in new_value) or None
        else:
            explanation = f"Updated {key} from '{previous_value}' to '{new_value}'"
            prev_str = str(previous_value) if previous_value is not None else None
            new_str = str(new_value) if new_value is not None else None

        case.log.append(
            CaseLog(
                {
                    "timestamp": "NOW",
                    "key": key,
                    "previous_value": prev_str,
                    "new_value": new_str,
                    "user": user.uname,
                    "explanation": explanation,
                }
            )
        )
        setattr(case, key, new_value)

    case.updated = "NOW"
    ds.case.save(case_id, case)

    return case


@overload
def append_case_item(case_id: str, item: CaseItem): ...


@overload
def append_case_item(
    case_id: str, item: None = None, item_type: str = ..., item_value: str = ..., item_path: str = ...
): ...


def append_case_item(  # noqa: C901
    case_id: str,
    item: CaseItem | None = None,
    item_type: str | None = None,
    item_value: str | None = None,
    item_path: str = "related/",
):
    """Append an item to a case, dispatching to the appropriate handler based on item type.

    Can be called either with a pre-built CaseItem object or with individual
    item_type, item_value, and item_path parameters to construct one.

    Args:
        case_id: Unique identifier of the case to append the item to.
        item: A pre-built CaseItem object. If provided, item_type, item_value,
            and item_path are ignored.
        item_type: The type of item to append (e.g. "hit", "observable", "case",
            "table", "lead", "reference"). Required if item is not provided.
        item_value: The value/identifier of the item to append. Required if item
            is not provided.
        item_path: Optional path prefix for organizing the item within the case.
            A trailing "/" is appended automatically if not present.

    Raises:
        InvalidDataException: If item is not provided and item_type or item_value
            are missing, or if item_type is not a valid CaseItemTypes value.
    """
    _case, _version = Case.objects.get_if_exists(key=case_id, as_obj=True, version=True)

    if _case is None:
        raise NotFoundException(f"Case {case_id} does not exist")

    if item is None:
        if not all([item_type, item_value]):
            raise InvalidDataException("item_type and item_value are required if item is not provided")

        if item_type not in CaseItemTypes:
            raise InvalidDataException(f"Invalid item type: {item_type}, valid types are: {', '.join(CaseItemTypes)}")

        if not item_path:
            item_path = "related/"

        item = CaseItem({"type": item_type, "value": item_value, "path": item_path})

    match item.type:
        case CaseItemTypes.HIT:
            append_hit(_case, item)
        case CaseItemTypes.OBSERVABLE:
            append_observable(_case, item)
        case CaseItemTypes.CASE:
            append_case(_case, item)
        case CaseItemTypes.TABLE:
            append_table(_case, item)
        case CaseItemTypes.LEAD:
            append_lead(_case, item)
        case CaseItemTypes.REFERENCE:
            append_reference(_case, item)
        case _:
            raise InvalidDataException(f"Unsupported item type: {item_type}")

    event_service.emit("cases", {"case": _case.as_primitives(), "version": _version})


def append_hit(_case: Case, item: CaseItem):
    """Append a hit item to a case and create a back-reference on the hit.

    Validates that the hit exists and is not already present in the case. Sets
    the item's path based on the hit's analytic and ID, appends it to the case,
    persists the case, and adds a back-reference from the hit to the case.

    Args:
        _case: The Case object to append the hit to.
        item: A CaseItem whose ``value`` is the ID of an existing hit.

    Raises:
        InvalidDataException: If the hit is already present in the case.
        NotFoundException: If no hit with ``item.value`` exists in the datastore.
        DataStoreException: If saving the updated case fails.
    """
    if any(item.value == case_item["value"] for case_item in _case.items):
        raise InvalidDataException(f"Hit {item.value} already exists in case {_case.case_id}")

    hit: Hit = Hit.objects.get_if_exists(key=item.value, as_obj=True)

    if hit is None:
        raise NotFoundException(f"Hit {item.value} not found, cannot be added to case")

    item.id = item.value

    if item.path == "related/":
        item.path = f"alerts/{hit.howler.analytic} ({hit.howler.id})"

    _case.items.append(item)

    if not _case.save():
        raise DataStoreException(f"Failed to save {_case.case_id} with new item {item.value}")

    add_backreference(hit, _case.case_id)


def append_observable(_case: Case, item: CaseItem):
    """Append an observable item to a case and create a back-reference on the observable.

    Validates that the observable exists and is not already present in the case.
    Sets the item's path based on the observable's ID, appends it to the case,
    persists the case, and adds a back-reference from the observable to the case.

    Args:
        _case: The Case object to append the observable to.
        item: A CaseItem whose ``value`` is the ID of an existing observable.

    Raises:
        InvalidDataException: If the observable is already present in the case.
        NotFoundException: If no observable with ``item.value`` exists in the datastore.
        DataStoreException: If saving the updated case fails.
    """
    if any(item.value == case_item["value"] for case_item in _case.items):
        raise InvalidDataException(f"Observable {item.value} already exists in case {_case.case_id}")

    observable: Observable = Observable.objects.get_if_exists(key=item.value, as_obj=True)

    if observable is None:
        raise NotFoundException(f"Observable {item.value} not found, cannot be added to case")

    item.id = item.value

    if item.path == "related/":
        item.path = f"observables/{observable.howler.id}"

    _case.items.append(item)

    if not _case.save():
        raise DataStoreException(f"Failed to save {_case.case_id} with new item {item.value}")

    add_backreference(observable, _case.case_id)


def append_case(_case: Case, item: CaseItem):
    """Append a case reference item to a case.

    Validates that the referenced case exists and is not already present in the
    parent case. Sets the item's path using the referenced case's ID, appends
    it to the parent case, and persists the updated case.

    Args:
        _case: The parent Case object to append the reference to.
        item: A CaseItem whose ``value`` is the ID of an existing case to reference.

    Raises:
        InvalidDataException: If the referenced case is already present in the parent case.
        NotFoundException: If no case with ``item.value`` exists in the datastore.
        DataStoreException: If saving the updated case fails.
    """
    if any(item.value == case_item["value"] for case_item in _case.items):
        raise InvalidDataException(f"Observable {item.value} already exists in case {_case.case_id}")

    referenced_case: Case = Case.objects.get_if_exists(key=item.value, as_obj=True)

    if referenced_case is None:
        raise NotFoundException(f"Referenced case {item.value} not found, cannot be added to case")

    item.id = item.value

    if item.path == "related/":
        item.path = "cases/"

    item.path += f"{referenced_case.case_id}"

    _case.items.append(item)

    if not _case.save():
        raise DataStoreException(f"Failed to save {_case.case_id} with new item {item.value}")


def append_table(_case: Case, item: CaseItem):
    """Append a table item to a case.

    Not yet implemented.

    Args:
        _case: The Case object to append the table to.
        item: A CaseItem representing the table to append.

    Raises:
        NotImplementedError: Always raised; this feature is not yet implemented.
    """
    raise NotImplementedError


def append_lead(_case: Case, item: CaseItem):
    """Append a lead item to a case.

    Not yet implemented.

    Args:
        _case: The Case object to append the lead to.
        item: A CaseItem representing the lead to append.

    Raises:
        NotImplementedError: Always raised; this feature is not yet implemented.
    """
    raise NotImplementedError


def append_reference(_case: Case, item: CaseItem):
    """Append an external reference item to a case.

    Not yet implemented.

    Args:
        _case: The Case object to append the reference to.
        item: A CaseItem representing the external reference to append.

    Raises:
        NotImplementedError: Always raised; this feature is not yet implemented.
    """
    raise NotImplementedError


def add_backreference(backing_obj: Hit | Observable, case_id: str):
    """Add a back-reference from a hit or observable to a case.

    Records the case ID in the backing object's ``howler.related_ids`` set so
    that the relationship can be traversed from the hit/observable side. If the
    back-reference already exists, the call is a no-op.

    Args:
        backing_obj: The Hit or Observable object to add the back-reference to.
        case_id: Unique identifier of the case to reference.

    Raises:
        InvalidDataException: If backing_obj is None or case_id is empty/falsy.
    """
    if backing_obj is None:
        raise InvalidDataException("Cannot add back reference on a nonexistent object")

    if not case_id:
        raise InvalidDataException("Missing back reference case_id")

    if any(case_id == related_id for related_id in backing_obj.howler.related):
        return

    backing_obj.howler.related.append(case_id)
    datastore()[backing_obj.__class__.__name__.lower()].save(backing_obj.howler.id, backing_obj)


def remove_backreference(backing_obj: Hit | Observable, case_id: str):
    """Remove a back-reference from a hit or observable to a case.

    Removes the case ID from the backing object's ``howler.related`` list
    and persists the change. If the case ID is not present in the list,
    the call is a no-op.

    Args:
        backing_obj: The Hit or Observable object to remove the back-reference from.
        case_id: Unique identifier of the case reference to remove.

    Raises:
        InvalidDataException: If backing_obj is None or case_id is empty/falsy.
    """
    if backing_obj is None:
        raise InvalidDataException("Cannot remove back reference on a nonexisting object")

    if not case_id:
        raise InvalidDataException("Missing back reference case_id")

    if case_id in backing_obj.howler.related:
        backing_obj.howler.related.remove(case_id)
        datastore()[backing_obj.__class__.__name__.lower()].save(backing_obj.howler.id, backing_obj)


def remove_case_item(case_id: str, item_value: str):
    """Remove an item from a case and clean up any associated back-references.

    Locates the item within the case by its value, removes it from the case's
    items list, persists the updated case, and removes the back-reference from
    the backing hit or observable if applicable.

    Args:
        case_id: Unique identifier of the case to remove the item from.
        item_value: The value/identifier of the item to remove.

    Raises:
        NotFoundException: If the case does not exist.
        DataStoreException: If saving the updated case fails.
    """
    ds = datastore()

    _case = ds.case.get(key=case_id, as_obj=True)

    if not _case:
        raise NotFoundException(f"Case {case_id} does not exist")

    case_item = next((item for item in _case.items if item["value"] == item_value), None)
    if not case_item:
        raise NotFoundException(f"Case item {item_value} does not exist")

    backing_obj: Hit | Observable | None = None
    match case_item.type:
        case CaseItemTypes.HIT:
            backing_obj = datastore().hit.get(case_item.id)
        case CaseItemTypes.OBSERVABLE:
            backing_obj = datastore().observable.get(case_item.id)

    _case.items.remove(case_item)

    if not datastore().case.save(_case.case_id, _case):
        raise DataStoreException("Failed to save case after item removal")

    if backing_obj:
        remove_backreference(backing_obj, _case.case_id)
