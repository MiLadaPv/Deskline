from __future__ import annotations

"""Compact always-on-top recording widget (Time Doctor-style)."""

import threading
import time
from typing import Any, Callable

from deskline.config import load_config, save_config

SnapshotFn = Callable[[], dict[str, Any]]


def _fmt_elapsed(sec: float) -> str:
    total = max(0, int(sec))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class MiniTracker:
    """Small topmost window: recording time + current project/task, closable."""

    def __init__(
        self,
        get_snapshot: SnapshotFn,
        *,
        on_pause: Callable[[], None] | None = None,
        on_resume: Callable[[], None] | None = None,
        on_open: Callable[[], None] | None = None,
    ) -> None:
        self._get_snapshot = get_snapshot
        self._on_pause = on_pause
        self._on_resume = on_resume
        self._on_open = on_open
        self._thread: threading.Thread | None = None
        self._show_event = threading.Event()
        self._stop = threading.Event()
        self._root: Any = None
        self._visible = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        cfg = load_config()
        if cfg.get("show_mini_tracker", True):
            self._show_event.set()
        self._thread = threading.Thread(
            target=self._run, name="deskline-mini-tracker", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._show_event.set()
        root = self._root
        if root is not None:
            try:
                root.after(0, root.destroy)
            except Exception:
                pass

    def show(self) -> None:
        cfg = load_config()
        cfg["show_mini_tracker"] = True
        save_config(cfg)
        self._show_event.set()
        root = self._root
        if root is not None:
            try:
                root.after(0, self._map_window)
            except Exception:
                pass

    def hide(self, *, persist: bool = True) -> None:
        if persist:
            cfg = load_config()
            cfg["show_mini_tracker"] = False
            save_config(cfg)
        self._show_event.clear()
        root = self._root
        if root is not None:
            try:
                root.after(0, self._unmap_window)
            except Exception:
                pass

    def _map_window(self) -> None:
        if self._root is None:
            return
        self._root.deiconify()
        self._visible = True

    def _unmap_window(self) -> None:
        if self._root is None:
            return
        self._root.withdraw()
        self._visible = False

    def _run(self) -> None:
        try:
            import tkinter as tk
            from tkinter import font as tkfont
        except Exception:
            return

        root = tk.Tk()
        self._root = root
        root.title("Deskline")
        root.resizable(False, False)
        root.attributes("-topmost", True)
        root.configure(bg="#15241f")
        try:
            root.attributes("-toolwindow", True)
        except Exception:
            pass

        width, height = 320, 78
        sw = root.winfo_screenwidth()
        root.geometry(f"{width}x{height}+{max(20, sw - width - 28)}+24")

        title_font = tkfont.Font(family="Segoe UI Semibold", size=11)
        meta_font = tkfont.Font(family="Segoe UI", size=9)

        frame = tk.Frame(root, bg="#15241f", padx=12, pady=10)
        frame.pack(fill="both", expand=True)

        top = tk.Frame(frame, bg="#15241f")
        top.pack(fill="x")

        status_lbl = tk.Label(
            top,
            text="● Запись",
            fg="#7dcea0",
            bg="#15241f",
            font=title_font,
            anchor="w",
        )
        status_lbl.pack(side="left")

        time_lbl = tk.Label(
            top,
            text="0:00",
            fg="#f4f7f5",
            bg="#15241f",
            font=title_font,
            anchor="e",
        )
        time_lbl.pack(side="right")

        focus_lbl = tk.Label(
            frame,
            text="Без проекта · Без задачи",
            fg="#c5d5cf",
            bg="#15241f",
            font=meta_font,
            anchor="w",
            justify="left",
        )
        focus_lbl.pack(fill="x", pady=(6, 4))

        btns = tk.Frame(frame, bg="#15241f")
        btns.pack(fill="x")

        def toggle_pause() -> None:
            snap = self._get_snapshot()
            if snap.get("paused"):
                if self._on_resume:
                    self._on_resume()
            else:
                if self._on_pause:
                    self._on_pause()

        def open_dash() -> None:
            if self._on_open:
                self._on_open()

        def close_widget() -> None:
            self.hide(persist=True)

        pause_btn = tk.Button(
            btns,
            text="Пауза",
            font=meta_font,
            bg="#2a3d37",
            fg="#e8f0ed",
            activebackground="#3a524a",
            activeforeground="#ffffff",
            relief="flat",
            padx=8,
            pady=2,
            command=toggle_pause,
        )
        pause_btn.pack(side="left")

        open_btn = tk.Button(
            btns,
            text="Открыть",
            font=meta_font,
            bg="#2a3d37",
            fg="#e8f0ed",
            activebackground="#3a524a",
            activeforeground="#ffffff",
            relief="flat",
            padx=8,
            pady=2,
            command=open_dash,
        )
        open_btn.pack(side="left", padx=(6, 0))

        close_btn = tk.Button(
            btns,
            text="✕",
            font=meta_font,
            bg="#2a3d37",
            fg="#e8f0ed",
            activebackground="#3a524a",
            activeforeground="#ffffff",
            relief="flat",
            padx=8,
            pady=2,
            command=close_widget,
        )
        close_btn.pack(side="right")

        root.protocol("WM_DELETE_WINDOW", close_widget)

        # Drag window by empty chrome
        _drag: dict[str, int] = {"x": 0, "y": 0}

        def start_drag(event: Any) -> None:
            _drag["x"] = event.x_root - root.winfo_x()
            _drag["y"] = event.y_root - root.winfo_y()

        def on_drag(event: Any) -> None:
            root.geometry(f"+{event.x_root - _drag['x']}+{event.y_root - _drag['y']}")

        for widget in (frame, top, status_lbl, time_lbl, focus_lbl):
            widget.bind("<Button-1>", start_drag)
            widget.bind("<B1-Motion>", on_drag)

        def refresh() -> None:
            if self._stop.is_set():
                root.destroy()
                return
            want = load_config().get("show_mini_tracker", True)
            if want and not self._visible:
                self._map_window()
            elif not want and self._visible:
                self._unmap_window()

            snap = self._get_snapshot()
            paused = bool(snap.get("paused"))
            idle = bool(snap.get("idle"))
            if paused:
                status_lbl.configure(text="Ⅱ Пауза", fg="#d4b483")
                pause_btn.configure(text="Продолжить")
            elif idle:
                status_lbl.configure(text="○ Без ввода", fg="#9ab0a7")
                pause_btn.configure(text="Пауза")
            else:
                status_lbl.configure(text="● Запись", fg="#7dcea0")
                pause_btn.configure(text="Пауза")

            elapsed = float(snap.get("session_elapsed_sec") or 0)
            time_lbl.configure(text=_fmt_elapsed(elapsed))

            project = (snap.get("project_name") or "").strip() or "Без проекта"
            task = (snap.get("task_name") or "").strip() or "Без задачи"
            focus_lbl.configure(text=f"{project} · {task}")

            root.after(1000, refresh)

        if not load_config().get("show_mini_tracker", True):
            root.withdraw()
            self._visible = False
        else:
            self._visible = True

        root.after(200, refresh)
        try:
            root.mainloop()
        finally:
            self._root = None
            self._visible = False
