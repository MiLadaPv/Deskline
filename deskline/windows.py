from __future__ import annotations

from dataclasses import dataclass

try:
    import win32gui
    import win32process
except ImportError:
    win32gui = None  # type: ignore
    win32process = None  # type: ignore

import ctypes
from ctypes import wintypes


@dataclass(frozen=True)
class ActiveWindow:
    app_name: str
    window_title: str
    pid: int


def get_active_window() -> ActiveWindow | None:
    """Return foreground window process name and title on Windows."""
    try:
        hwnd = win32gui.GetForegroundWindow() if win32gui else ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None
        if win32gui:
            title = win32gui.GetWindowText(hwnd) or ""
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        else:
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pid = int(pid.value)

        app_name = _process_name(pid) or "unknown.exe"
        return ActiveWindow(app_name=app_name.lower(), window_title=title, pid=pid)
    except Exception:
        return None


def _process_name(pid: int) -> str | None:
    # Prefer QueryFullProcessImageName via ctypes (no psutil required)
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            path = buf.value
            return path.rsplit("\\", 1)[-1]
    finally:
        kernel32.CloseHandle(handle)
    return None
