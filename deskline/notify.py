"""Windows notifications and styled dialogs for Deskline."""

from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
from ctypes import wintypes
from typing import Any, Literal

_lock = threading.Lock()
_icon: Any = None

StillWorkingAnswer = Literal["yes", "no", "timeout"]

_TD_CONTINUE = 101
_TD_PAUSE = 102


def set_tray_icon(icon: Any) -> None:
    global _icon
    with _lock:
        _icon = icon


def notify(title: str, message: str) -> None:
    """Show a non-blocking tray notification when possible."""
    with _lock:
        icon = _icon
    if icon is not None:
        try:
            icon.notify(message, title)
            return
        except Exception:
            pass
    _powershell_toast(title, message)


def _powershell_toast(title: str, message: str) -> None:
    try:
        t = title.replace("'", "''")
        m = message.replace("'", "''")
        script = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
            "ContentType = WindowsRuntime] > $null; "
            "$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
            "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
            "$text = $template.GetElementsByTagName('text'); "
            f"$text.Item(0).AppendChild($template.CreateTextNode('{t}')) | Out-Null; "
            f"$text.Item(1).AppendChild($template.CreateTextNode('{m}')) | Out-Null; "
            "$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Deskline')"
            ".Show($toast)"
        )
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass


def still_working_body(label: str) -> str:
    """Short body — actions are on the buttons themselves."""
    return (
        f"Нет клавиатуры и мыши уже некоторое время.\n"
        f"Сейчас открыто: {label}\n\n"
        f"Продолжить — вы за ПК, учёт идёт дальше.\n"
        f"На паузу — перерыв, Deskline останавливает запись."
    )


def ask_yes_no(title: str, message: str) -> bool:
    return ask_still_working(title, message) == "yes"


def ask_still_working(
    title: str,
    message: str,
    *,
    timeout_sec: float = 45.0,
) -> StillWorkingAnswer:
    """
    Still-working dialog with explicit Continue / Pause actions.
    Returns yes / no / timeout. Timeout keeps tracking (does NOT pause).
    """
    # 1) Own process with Tk — reliable UI thread (fixes Да/Нет MessageBox fallback)
    try:
        return _subprocess_still_working(title, message, timeout_sec=timeout_sec)
    except Exception:
        pass
    # 2) In-process TaskDialog with custom button labels
    try:
        return _taskdialog_still_working(title, message)
    except Exception:
        pass
    # 3) Last resort MessageBox — map Да/Нет in the text itself (cannot rename buttons)
    try:
        return _messagebox_still_working(title, message)
    except Exception:
        return "yes"


def _subprocess_still_working(
    title: str, message: str, *, timeout_sec: float
) -> StillWorkingAnswer:
    creation = 0
    # Do NOT use CREATE_NO_WINDOW — dialog must be visible.
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "deskline.still_working_dialog",
            title or "Deskline",
            message,
            str(timeout_sec),
        ],
        capture_output=True,
        timeout=max(30.0, timeout_sec + 30.0),
        creationflags=creation,
    )
    code = int(proc.returncode)
    if code == 0:
        return "yes"
    if code == 1:
        return "no"
    return "timeout"


def _messagebox_still_working(title: str, message: str) -> StillWorkingAnswer:
    body = (
        "ВАЖНО:\n"
        "• ДА  = Продолжить учёт (я за компьютером)\n"
        "• НЕТ = На паузу (перерыв)\n\n"
        + (message or still_working_body("Deskline"))
    )
    result = ctypes.windll.user32.MessageBoxW(
        0, body, title, 0x04 | 0x20 | 0x40000  # MB_YESNO | MB_ICONQUESTION | MB_TOPMOST
    )
    if int(result) == 6:
        return "yes"
    if int(result) == 7:
        return "no"
    return "timeout"


def _taskdialog_still_working(title: str, message: str) -> StillWorkingAnswer:
    """Win32 TaskDialog with Продолжить / На паузу."""
    comctl32 = ctypes.windll.comctl32

    class TASKDIALOG_BUTTON(ctypes.Structure):
        _fields_ = [
            ("nButtonID", ctypes.c_int),
            ("pszButtonText", wintypes.LPCWSTR),
        ]

    class TASKDIALOGCONFIG(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("hwndParent", wintypes.HWND),
            ("hInstance", wintypes.HINSTANCE),
            ("dwFlags", ctypes.c_uint),
            ("dwCommonButtons", ctypes.c_uint),
            ("pszWindowTitle", wintypes.LPCWSTR),
            ("hMainIcon", ctypes.c_void_p),
            ("pszMainInstruction", wintypes.LPCWSTR),
            ("pszContent", wintypes.LPCWSTR),
            ("cButtons", ctypes.c_uint),
            ("pButtons", ctypes.POINTER(TASKDIALOG_BUTTON)),
            ("nDefaultButton", ctypes.c_int),
            ("cRadioButtons", ctypes.c_uint),
            ("pRadioButtons", ctypes.c_void_p),
            ("nDefaultRadioButton", ctypes.c_int),
            ("pszVerificationText", wintypes.LPCWSTR),
            ("pszExpandedInformation", wintypes.LPCWSTR),
            ("pszExpandedControlText", wintypes.LPCWSTR),
            ("pszCollapsedControlText", wintypes.LPCWSTR),
            ("pszFooterIcon", ctypes.c_void_p),
            ("pszFooter", wintypes.LPCWSTR),
            ("pfCallback", ctypes.c_void_p),
            ("lpCallbackData", ctypes.c_longlong),
            ("cxWidth", ctypes.c_uint),
        ]

    TDF_ALLOW_DIALOG_CANCELLATION = 0x0008
    TDF_USE_HICON_MAIN = 0x0002

    buttons = (TASKDIALOG_BUTTON * 2)(
        TASKDIALOG_BUTTON(_TD_CONTINUE, "Продолжить"),
        TASKDIALOG_BUTTON(_TD_PAUSE, "На паузу"),
    )

    cfg = TASKDIALOGCONFIG()
    cfg.cbSize = ctypes.sizeof(TASKDIALOGCONFIG)
    cfg.hwndParent = None
    cfg.hInstance = None
    cfg.dwFlags = TDF_ALLOW_DIALOG_CANCELLATION
    cfg.dwCommonButtons = 0
    cfg.pszWindowTitle = title or "Deskline"
    cfg.hMainIcon = None
    cfg.pszMainInstruction = "Вы ещё за компьютером?"
    cfg.pszContent = message
    cfg.cButtons = 2
    cfg.pButtons = ctypes.cast(buttons, ctypes.POINTER(TASKDIALOG_BUTTON))
    cfg.nDefaultButton = _TD_CONTINUE
    cfg.pszFooter = "Закрытие окна без выбора — учёт продолжится."
    cfg.cxWidth = 0

    try:
        class INITCOMMONCONTROLSEX(ctypes.Structure):
            _fields_ = [("dwSize", ctypes.c_uint), ("dwICC", ctypes.c_uint)]

        icc = INITCOMMONCONTROLSEX(ctypes.sizeof(INITCOMMONCONTROLSEX), 0xFFFF)
        ctypes.windll.comctl32.InitCommonControlsEx(ctypes.byref(icc))
    except Exception:
        pass

    pn_button = ctypes.c_int(0)
    hr = comctl32.TaskDialogIndirect(
        ctypes.byref(cfg),
        ctypes.byref(pn_button),
        None,
        None,
    )
    if hr != 0:
        raise OSError(f"TaskDialogIndirect failed: {hr}")
    btn = int(pn_button.value)
    if btn == _TD_CONTINUE:
        return "yes"
    if btn == _TD_PAUSE:
        return "no"
    return "timeout"
