"""Detect PC sleep / long suspend gaps between tracker ticks."""

from __future__ import annotations

import time

# Wall-clock gap larger than this between ticks ⇒ machine was asleep / suspended.
DEFAULT_SLEEP_GAP_SEC = 120.0


def is_sleep_gap(dt_sec: float, threshold_sec: float = DEFAULT_SLEEP_GAP_SEC) -> bool:
    """True when elapsed wall time between polls implies sleep/hibernate."""
    return dt_sec >= float(threshold_sec)


def system_boot_time() -> float:
    """Approximate OS boot as a Unix timestamp (Windows GetTickCount64)."""
    try:
        import ctypes

        ms = int(ctypes.windll.kernel32.GetTickCount64())
        return time.time() - (ms / 1000.0)
    except Exception:
        # Unknown platform / API: treat "boot" as now so we do not rewrite history.
        return time.time()
