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


def calculate_overdue_days(due_date, as_of=None):
    """Return integer days overdue as of a given reference date (defaults to library_today)."""
    if due_date is None:
        return 0
    ref_date = as_of or library_today()
    return max(0, (ref_date - due_date).days)


def estimate_late_fine(due_date, daily_rate=None, as_of=None):
    """Calculate estimated late fine for a given due date and daily fine rate."""
    days = calculate_overdue_days(due_date, as_of=as_of)
    if days == 0:
        return 0.0
    if daily_rate is None:
        daily_rate = float(current_app.config.get("FINE_PER_DAY", 1.00))
    return round(days * float(daily_rate), 2)

