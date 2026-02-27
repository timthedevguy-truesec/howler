"""Utility functions for converting between ISO 8601 strings and datetime objects.

Provides helpers to get the current UTC time as an ISO 8601 string, convert
an existing :class:`datetime.datetime` to an ISO 8601 string, and parse an
ISO 8601 string back into a :class:`datetime.datetime` via the Lucene date
parser.
"""

import sys
from datetime import datetime

# DO NOT REMOVE!!! THIS IS MAGIC!
# strptime Thread safe fix... yeah ...
datetime.strptime("2000", "%Y")
# END OF MAGIC


def now_as_iso() -> str:
    """Get the current UTC time as an ISO 8601 formatted string.

    Returns:
        str: The current UTC timestamp in ISO 8601 format, ending with ``"Z"``
            (e.g. ``"2026-02-27T14:30:00.123456Z"``).
    """
    if sys.version_info.minor < 11:
        return f"{datetime.utcnow().isoformat()}Z"
    else:
        from datetime import UTC

        return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def now() -> datetime:
    """Get the current UTC time.

    Returns:
        str: The current UTC time.
    """
    if sys.version_info.minor < 11:
        return datetime.utcnow()
    else:
        from datetime import UTC

        return datetime.now(tz=UTC)


def to_iso(dt: datetime) -> str:
    """Convert a datetime object to an ISO 8601 formatted string.

    On Python < 3.11 the datetime's ``isoformat()`` output is used directly
    with ``"Z"`` appended.  On Python >= 3.11 the datetime is first converted
    to UTC before formatting so the result is always a UTC timestamp.

    Args:
        dt: The datetime to convert.

    Returns:
        str: The datetime in ISO 8601 format, ending with ``"Z"``
            (e.g. ``"2026-02-27T14:30:00.123456Z"``).
    """
    if sys.version_info.minor < 11:
        return f"{dt.isoformat()}Z"
    else:
        from datetime import UTC

        return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def from_iso(date: str) -> datetime:
    """Parse an ISO 8601 formatted string into a datetime object.

    Delegates to :func:`howler.utils.lucene.try_parse_date` which handles
    both strict ISO 8601 strings and Lucene-style date math expressions
    (e.g. ``"now-1d/d"``).

    Args:
        date: An ISO 8601 date/time string or Lucene date math expression.

    Returns:
        datetime: The parsed :class:`datetime.datetime` object.
    """
    try:
        # Check if the value is a ISO-formatted date
        if sys.version_info.major < 11:
            return datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            return datetime.fromisoformat(date)
    except (ValueError, TypeError):
        return None
