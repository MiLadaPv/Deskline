from __future__ import annotations

"""Windows notifications and styled dialogs for Deskline."""

import ctypes
import threading
from ctypes import wintypes
from typing import Any, Literal

_lock = threading.Lock()
_icon: Any = None

StillWorkingAnswer = Literal["yes", "no", "timeout"]

# Custom TaskDialog button IDs (must be > 100 per Win32 convention for custom buttons)
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
        import subprocess

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


def still_working_body(label: str, *, for_message_box: bool = False) -> str:
    """User-facing body that states what each choice does."""
    head = (
        f"Нет клавиатуры и мыши уже некоторое время.\n"
        f"Сейчас: {label}\n\n"
    )
    if for_message_box:
        return (
            head
            + "Да — я за компьютером, продолжить учёт времени.\n"
            + "Нет — перерыв: поставить Deskline на паузу.\n\n"
            + "Если не ответите, трекинг продолжится."
        )
    return (
        head
        + "«Продолжить» — я за компьютером, учёт времени идёт дальше.\n"
        + "«На паузу» — это перерыв, Deskline ставится на паузу.\n\n"
        + "Без ответа трекинг продолжится."
    )


def ask_yes_no(title: str, message: str) -> bool:
    """Blocking Yes/No. Prefer ask_still_working for the idle prompt."""
    return ask_still_working(title, message) == "yes"


def ask_still_working(
    title: str,
    message: str,
    *,
    timeout_sec: float = 45.0,
) -> StillWorkingAnswer:
    """
    Still-working dialog.
    Returns yes / no / timeout. Timeout means keep tracking (do NOT pause).
    """
    try:
        return _tk_still_working(title, message, timeout_sec=timeout_sec)
    except Exception:
        pass
    try:
        return _taskdialog_still_working(title, message)
    except Exception:
        pass
    try:
        return _messagebox_still_working(title, message)
    except Exception:
        return "yes"


def _messagebox_still_working(title: str, message: str) -> StillWorkingAnswer:
    # Ensure consequences are visible even with generic Да/Нет labels.
    body = message
    if "продолжить" not in message.lower() and "пауз" not in message.lower():
        body = still_working_body("Deskline", for_message_box=True)
    result = ctypes.windll.user32.MessageBoxW(
        0, body, title, 0x04 | 0x20 | 0x40000  # MB_YESNO | MB_ICONQUESTION | MB_TOPMOST
    )
    if int(result) == 6:  # IDYES
        return "yes"
    if int(result) == 7:  # IDNO
        return "no"
    return "timeout"


def _taskdialog_still_working(title: str, message: str) -> StillWorkingAnswer:
    """Win32 TaskDialog with custom Continue / Pause buttons (no Tk required)."""
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
            ("hMainIcon", wintypes.LPCWSTR),  # union simplified as pointer/PCWSTR
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
            ("pszFooterIcon", wintypes.LPCWSTR),
            ("pszFooter", wintypes.LPCWSTR),
            ("pfCallback", ctypes.c_void_p),
            ("lpCallbackData", ctypes.c_longlong),
            ("cxWidth", ctypes.c_uint),
        ]

    TDF_ALLOW_DIALOG_CANCELLATION = 0x0008
    TDF_POSITION_RELATIVE_TO_WINDOW = 0x1000

    buttons = (TASKDIALOG_BUTTON * 2)(
        TASKDIALOG_BUTTON(_TD_CONTINUE, "Продолжить"),
        TASKDIALOG_BUTTON(_TD_PAUSE, "На паузу"),
    )

    cfg = TASKDIALOGCONFIG()
    cfg.cbSize = ctypes.sizeof(TASKDIALOGCONFIG)
    cfg.hwndParent = None
    cfg.hInstance = None
    cfg.dwFlags = TDF_ALLOW_DIALOG_CANCELLATION | TDF_POSITION_RELATIVE_TO_WINDOW
    cfg.dwCommonButtons = 0
    cfg.pszWindowTitle = title or "Deskline"
    cfg.hMainIcon = None
    cfg.pszMainInstruction = "Вы ещё за компьютером?"
    cfg.pszContent = message
    cfg.cButtons = 2
    cfg.pButtons = ctypes.cast(buttons, ctypes.POINTER(TASKDIALOG_BUTTON))
    cfg.nDefaultButton = _TD_CONTINUE
    cfg.cRadioButtons = 0
    cfg.pRadioButtons = None
    cfg.nDefaultRadioButton = 0
    cfg.pszVerificationText = None
    cfg.pszExpandedInformation = None
    cfg.pszExpandedControlText = None
    cfg.pszCollapsedControlText = None
    cfg.pszFooterIcon = None
    cfg.pszFooter = "Без ответа закройте окно — трекинг продолжится."
    cfg.pfCallback = None
    cfg.lpCallbackData = 0
    cfg.cxWidth = 0

    pn_button = ctypes.c_int(0)
    # InitCommonControlsEx may be required on some systems
    try:
        class INITCOMMONCONTROLSEX(ctypes.Structure):
            _fields_ = [("dwSize", ctypes.c_uint), ("dwICC", ctypes.c_uint)]

        icc = INITCOMMONCONTROLSEX(ctypes.sizeof(INITCOMMONCONTROLSEX), 0xFFFF)
        ctypes.windll.comctl32.InitCommonControlsEx(ctypes.byref(icc))
    except Exception:
        pass

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
    # Cancel / close / Esc → keep tracking
    return "timeout"


def _tk_still_working(title: str, message: str, *, timeout_sec: float) -> StillWorkingAnswer:
    import tkinter as tk
    from tkinter import font as tkfont

    # Tk often fails from a non-main thread under pythonw; surface that clearly.
    if threading.current_thread() is not threading.main_thread():
        # Still try — works on some setups; TaskDialog is the reliable fallback.
        pass

    result: dict[str, StillWorkingAnswer] = {"value": "timeout"}

    root = tk.Tk()
    root.title(title or "Deskline")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.configure(bg="#1a2e28")

    try:
        root.iconbitmap(default="")
    except Exception:
        pass

    width, height = 460, 300
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{width}x{height}+{(sw - width) // 2}+{(sh - height) // 3}")

    title_font = tkfont.Font(family="Segoe UI Semibold", size=14)
    body_font = tkfont.Font(family="Segoe UI", size=11)
    btn_font = tkfont.Font(family="Segoe UI Semibold", size=10)

    frame = tk.Frame(root, bg="#1a2e28", padx=28, pady=24)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="Deskline",
        fg="#8fbfb0",
        bg="#1a2e28",
        font=title_font,
        anchor="w",
    ).pack(fill="x")

    tk.Label(
        frame,
        text="Вы ещё за компьютером?",
        fg="#f4f7f5",
        bg="#1a2e28",
        font=title_font,
        anchor="w",
        pady=(12, 6),
    ).pack(fill="x")

    tk.Label(
        frame,
        text=message,
        fg="#c5d5cf",
        bg="#1a2e28",
        font=body_font,
        wraplength=400,
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(0, 18))

    btns = tk.Frame(frame, bg="#1a2e28")
    btns.pack(fill="x")

    def choose(val: StillWorkingAnswer) -> None:
        result["value"] = val
        root.destroy()

    yes_btn = tk.Button(
        btns,
        text="Продолжить",
        font=btn_font,
        bg="#2f6f5e",
        fg="#ffffff",
        activebackground="#3d8a75",
        activeforeground="#ffffff",
        relief="flat",
        padx=16,
        pady=10,
        cursor="hand2",
        command=lambda: choose("yes"),
    )
    yes_btn.pack(side="left", padx=(0, 10))

    no_btn = tk.Button(
        btns,
        text="На паузу",
        font=btn_font,
        bg="#2a3d37",
        fg="#e8f0ed",
        activebackground="#3a524a",
        activeforeground="#ffffff",
        relief="flat",
        padx=16,
        pady=10,
        cursor="hand2",
        command=lambda: choose("no"),
    )
    no_btn.pack(side="left")

    hint = tk.Label(
        frame,
        text=f"Без ответа через {int(timeout_sec)} с трекинг продолжится",
        fg="#7a948c",
        bg="#1a2e28",
        font=tkfont.Font(family="Segoe UI", size=9),
        anchor="w",
        pady=(16, 0),
    )
    hint.pack(fill="x")

    root.protocol("WM_DELETE_WINDOW", lambda: choose("timeout"))
    root.after(int(max(5.0, timeout_sec) * 1000), lambda: choose("timeout"))
    root.focus_force()
    yes_btn.focus_set()
    root.mainloop()
    return result["value"]
