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
    app_path: str | None = None


def get_active_window() -> ActiveWindow | None:
    """Return foreground window process name, path, and title on Windows."""
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

        path = _process_path(pid)
        name = (path.rsplit("\\", 1)[-1] if path else None) or _process_name_toolhelp(pid)
        app_name = (name or "unknown.exe").lower()
        return ActiveWindow(
            app_name=app_name,
            window_title=title,
            pid=pid,
            app_path=path,
        )
    except Exception:
        return None


def _process_path(pid: int) -> str | None:
    """Best-effort full image path for a process."""
    # PROCESS_QUERY_LIMITED_INFORMATION, PROCESS_QUERY_INFORMATION
    for access in (0x1000, 0x0400):
        path = _query_full_image_name(pid, access)
        if path:
            return path
    path = _module_file_name(pid)
    if path:
        return path
    return None


def _query_full_image_name(pid: int, access: int) -> str | None:
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value or None
    finally:
        kernel32.CloseHandle(handle)
    return None


def _module_file_name(pid: int) -> str | None:
    """Fallback via GetModuleFileNameEx (needs QUERY + VM_READ)."""
    if not win32process:
        return None
    try:
        import win32api
        import win32con

        access = win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ
        handle = win32api.OpenProcess(access, False, pid)
        try:
            return win32process.GetModuleFileNameEx(handle, 0) or None
        finally:
            win32api.CloseHandle(handle)
    except Exception:
        return None


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def _process_name_toolhelp(pid: int) -> str | None:
    """Process exe name without needing OpenProcess (works when path query is denied)."""
    TH32CS_SNAPPROCESS = 0x00000002
    kernel32 = ctypes.windll.kernel32
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == ctypes.c_void_p(-1).value or snap == -1:
        return None
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snap, ctypes.byref(entry)):
            return None
        while True:
            if int(entry.th32ProcessID) == int(pid):
                name = entry.szExeFile
                return name or None
            if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snap)
    return None


def _process_name(pid: int) -> str | None:
    path = _process_path(pid)
    if path:
        return path.rsplit("\\", 1)[-1]
    return _process_name_toolhelp(pid)


@dataclass(frozen=True)
class WindowInfo:
    app_name: str
    window_title: str
    pid: int
    class_name: str = ""
    app_path: str | None = None


def _window_class_name(hwnd: int) -> str:
    try:
        buf = ctypes.create_unicode_buffer(256)
        if ctypes.windll.user32.GetClassNameW(hwnd, buf, 256):
            return buf.value or ""
    except Exception:
        pass
    return ""


def _window_title(hwnd: int) -> str:
    try:
        if win32gui:
            return win32gui.GetWindowText(hwnd) or ""
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or ""
    except Exception:
        return ""


def _window_pid(hwnd: int) -> int:
    try:
        if win32process:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return int(pid)
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)
    except Exception:
        return 0


def iter_top_level_windows(*, visible_only: bool = True) -> list[WindowInfo]:
    """Enumerate top-level windows (for background call detection)."""
    out: list[WindowInfo] = []
    user32 = ctypes.windll.user32

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _enum(hwnd: int, _lparam: int) -> bool:
        try:
            if visible_only and not user32.IsWindowVisible(hwnd):
                return True
            # Skip tiny tool windows / cloaked empty shells.
            if user32.GetWindow(hwnd, 4):  # GW_OWNER
                return True
            title = _window_title(hwnd)
            class_name = _window_class_name(hwnd)
            if not title and not class_name:
                return True
            pid = _window_pid(hwnd)
            if not pid:
                return True
            path = _process_path(pid)
            name = (path.rsplit("\\", 1)[-1] if path else None) or _process_name_toolhelp(pid)
            app_name = (name or "unknown.exe").lower()
            out.append(
                WindowInfo(
                    app_name=app_name,
                    window_title=title,
                    pid=pid,
                    class_name=class_name,
                    app_path=path,
                )
            )
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(_enum, 0)
    except Exception:
        return []
    return out
