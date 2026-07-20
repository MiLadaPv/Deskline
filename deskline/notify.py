from __future__ import annotations

"""Windows notifications for Deskline (tray balloon / toast)."""

import threading
from typing import Any

_lock = threading.Lock()
_icon: Any = None


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
    """Blocking Yes/No MessageBox. Returns True for Yes."""
    try:
        import ctypes

        result = ctypes.windll.user32.MessageBoxW(0, message, title, 0x04 | 0x20 | 0x40000)
        return int(result) == 6  # IDYES
    except Exception:
        return True
