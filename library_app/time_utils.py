"""Calendar dates for the library's configured local timezone."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import current_app


def library_today(at=None):
    """Return today's date where the library operates, not where its server runs."""
    instant = at or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("library_today requires a timezone-aware datetime.")
    zone = ZoneInfo(current_app.config.get("LIBRARY_TIMEZONE", "Asia/Kolkata"))
    return instant.astimezone(zone).date()
