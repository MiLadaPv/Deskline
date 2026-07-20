"""Detect PC sleep / long suspend gaps between tracker ticks."""

from __future__ import annotations

# Wall-clock gap larger than this between ticks ⇒ machine was asleep / suspended.
DEFAULT_SLEEP_GAP_SEC = 120.0


def is_sleep_gap(dt_sec: float, threshold_sec: float = DEFAULT_SLEEP_GAP_SEC) -> bool:
    """True when elapsed wall time between polls implies sleep/hibernate."""
    return dt_sec >= float(threshold_sec)
