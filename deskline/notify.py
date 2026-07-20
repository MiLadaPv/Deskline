from __future__ import annotations

"""Windows notifications and styled dialogs for Deskline."""

import threading
from typing import Any, Literal

_lock = threading.Lock()
_icon: Any = None

StillWorkingAnswer = Literal["yes", "no", "timeout"]


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
    Styled still-working dialog.
    Returns yes / no / timeout. Timeout means keep tracking (do NOT pause).
    """
    try:
        return _tk_still_working(title, message, timeout_sec=timeout_sec)
    except Exception:
        try:
            import ctypes

            result = ctypes.windll.user32.MessageBoxW(
                0, message, title, 0x04 | 0x20 | 0x40000
            )
            if int(result) == 6:
                return "yes"
            if int(result) == 7:
                return "no"
            return "timeout"
        except Exception:
            return "yes"


def _tk_still_working(title: str, message: str, *, timeout_sec: float) -> StillWorkingAnswer:
    import tkinter as tk
    from tkinter import font as tkfont

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

    width, height = 440, 260
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
        wraplength=380,
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
        text="Да, работаю",
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
        text="Нет, пауза",
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
