from __future__ import annotations

import ctypes
from ctypes import wintypes

# Apps where low keyboard/mouse input is normal (calls, presentations).
MEETING_APPS = {
    "teams.exe",
    "ms-teams.exe",
    "zoom.exe",
    "skype.exe",
    "webex.exe",
    "ciscowebexstart.exe",
    "slack.exe",  # huddles / calls
}


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


def seconds_since_last_input() -> float:
    """Seconds since the last keyboard/mouse input (Windows GetLastInputInfo)."""
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        tick = ctypes.windll.kernel32.GetTickCount()
        # Handle 49.7-day tick wrap
        idle_ms = (tick - info.dwTime) & 0xFFFFFFFF
        return idle_ms / 1000.0
    except Exception:
        return 0.0


def is_idle(
    idle_after_sec: float,
    app_name: str | None = None,
    *,
    meeting_idle_after_sec: float | None = None,
) -> bool:
    """True when no input for longer than the threshold (longer for meeting apps)."""
    threshold = float(idle_after_sec)
    app = (app_name or "").strip().lower()
    if app in MEETING_APPS:
        threshold = float(meeting_idle_after_sec if meeting_idle_after_sec is not None else max(threshold, 900.0))
    if threshold <= 0:
        return False
    return seconds_since_last_input() >= threshold
