from __future__ import annotations

from datetime import datetime, timezone

import pytest

from deskline.db import parse_iso_datetime


def test_parse_iso_datetime_accepts_trailing_z() -> None:
    dt = parse_iso_datetime("2026-07-22T12:30:00.000Z")
    assert dt.tzinfo is not None
    assert dt.astimezone(timezone.utc).hour == 12
    assert dt.astimezone(timezone.utc).minute == 30


def test_parse_iso_datetime_accepts_offset() -> None:
    dt = parse_iso_datetime("2026-07-22T15:30:00+03:00")
    assert dt.utcoffset().total_seconds() == 3 * 3600


def test_parse_iso_datetime_date_only_is_aware() -> None:
    dt = parse_iso_datetime("2026-07-22")
    assert dt.tzinfo is not None
    assert dt.year == 2026 and dt.month == 7 and dt.day == 22


def test_parse_iso_datetime_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_iso_datetime("not-a-date")
