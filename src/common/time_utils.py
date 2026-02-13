from __future__ import annotations

from datetime import date


def iso_week_label(d: date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def iso_date(d: date) -> str:
    return d.isoformat()
