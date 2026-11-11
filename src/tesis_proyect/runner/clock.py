"""Runtime clock implementation."""

from datetime import UTC, datetime


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
