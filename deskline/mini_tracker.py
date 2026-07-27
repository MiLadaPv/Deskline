from __future__ import annotations

"""Compact always-on-top recording widget (Deskline brand).

Horizontal bar by default; flips to a vertical strip when docked
tight against the right screen edge.
"""

import threading
from typing import Any, Callable

from deskline.config import load_config, save_config

SnapshotFn = Callable[[], dict[str, Any]]

# Brand tokens (match web CSS)
_INK = "#15241f"
_INK_SOFT = "#9bb0a7"
_PAPER = "#f4faf7"
_ACCENT = "#1f6b56"
_ACCENT_SOFT = "#7dcea0"
_WARN = "#d4b483"
_IDLE = "#8aa399"
_BTN = "#243832"
_BTN_HOVER = "#314840"

_H_W, _H_H = 280, 64
_V_W, _V_H = 64, 216
_EDGE_PX = 22


def _fmt_elapsed(sec: float) -> str:
    total = max(0, int(sec))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _orient_for_position(x: int, width: int, screen_w: int) -> str:
    """Return 'vertical' when the widget sits flush against the right edge."""
    if screen_w <= 0:
        return "horizontal"
    if x + width >= screen_w - _EDGE_PX:
        return "vertical"
    return "horizontal"


def _truncate(text: str, max_chars: int) -> str:
    raw = (text or "").strip()
    if len(raw) <= max_chars:
        return raw
    if max_chars <= 1:
        return "…"
    return raw[: max_chars - 1].rstrip() + "…"


def _focus_label(snap: dict[str, Any], *, vertical: bool) -> str:
    project = (snap.get("project_name") or "").strip() or "Без проекта"
    task = (snap.get("task_name") or "").strip()
    if vertical:
        return _truncate(project, 18)
    if task:
        return _truncate(f"{project} · {task}", 36)
    return _truncate(project, 36)


class MiniTracker:
    """Small topmost window: elapsed time + project, closable, edge-aware."""

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
        self._orient = "horizontal"
        self._widgets: dict[str, Any] = {}

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

    def _save_geometry(self) -> None:
        root = self._root
        if root is None:
            return
        try:
            cfg = load_config()
            cfg["mini_tracker_x"] = int(root.winfo_x())
            cfg["mini_tracker_y"] = int(root.winfo_y())
            save_config(cfg)
        except Exception:
            pass

    def _initial_geometry(self, root: Any) -> tuple[int, int, int, int, str]:
        sw = int(root.winfo_screenwidth() or 1280)
        sh = int(root.winfo_screenheight() or 800)
        cfg = load_config()
        try:
            x = int(cfg.get("mini_tracker_x", -1))
            y = int(cfg.get("mini_tracker_y", -1))
        except (TypeError, ValueError):
            x, y = -1, -1
        if x < 0 or y < 0:
            x = max(20, sw - _H_W - 28)
            y = 24
        orient = _orient_for_position(x, _H_W if x + _H_W < sw - _EDGE_PX else _V_W, sw)
        if orient == "vertical":
            w, h = _V_W, _V_H
            x = max(0, sw - w - 10)
        else:
            w, h = _H_W, _H_H
            x = max(0, min(x, sw - w - 4))
        y = max(0, min(y, sh - h - 4))
        return w, h, x, y, orient

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
        root.configure(bg=_INK)
        try:
            root.overrideredirect(True)
        except Exception:
            pass
        try:
            root.attributes("-toolwindow", True)
        except Exception:
            pass
        try:
            root.attributes("-alpha", 0.97)
        except Exception:
            pass

        w, h, x, y, orient = self._initial_geometry(root)
        self._orient = orient
        root.geometry(f"{w}x{h}+{x}+{y}")

        title_font = tkfont.Font(family="Segoe UI Semibold", size=12)
        time_font = tkfont.Font(family="Segoe UI Semibold", size=14)
        meta_font = tkfont.Font(family="Segoe UI", size=9)
        tiny_font = tkfont.Font(family="Segoe UI", size=8)

        shell = tk.Frame(root, bg=_INK, highlightthickness=0)
        shell.pack(fill="both", expand=True)

        accent = tk.Frame(shell, bg=_ACCENT, width=4)
        body = tk.Frame(shell, bg=_INK)

        status_lbl = tk.Label(body, text="●", fg=_ACCENT_SOFT, bg=_INK, font=title_font)
        time_lbl = tk.Label(body, text="0:00", fg=_PAPER, bg=_INK, font=time_font)
        focus_lbl = tk.Label(
            body,
            text="Без проекта",
            fg=_INK_SOFT,
            bg=_INK,
            font=meta_font,
            justify="left",
            wraplength=_H_W - 48,
        )

        def toggle_pause() -> None:
            snap = self._get_snapshot()
            if snap.get("paused"):
                if self._on_resume:
                    self._on_resume()
            else:
                if self._on_pause:
                    self._on_pause()

        def open_dash(event: Any | None = None) -> None:
            if self._on_open:
                self._on_open()

        def close_widget(event: Any | None = None) -> None:
            self.hide(persist=True)

        pause_btn = tk.Button(
            body,
            text="Ⅱ",
            font=tiny_font,
            bg=_BTN,
            fg=_PAPER,
            activebackground=_BTN_HOVER,
            activeforeground=_PAPER,
            relief="flat",
            bd=0,
            padx=6,
            pady=2,
            cursor="hand2",
            command=toggle_pause,
        )
        close_btn = tk.Button(
            body,
            text="✕",
            font=tiny_font,
            bg=_BTN,
            fg=_INK_SOFT,
            activebackground=_BTN_HOVER,
            activeforeground=_PAPER,
            relief="flat",
            bd=0,
            padx=6,
            pady=2,
            cursor="hand2",
            command=close_widget,
        )

        self._widgets = {
            "shell": shell,
            "accent": accent,
            "body": body,
            "status": status_lbl,
            "time": time_lbl,
            "focus": focus_lbl,
            "pause": pause_btn,
            "close": close_btn,
            "title_font": title_font,
            "time_font": time_font,
            "meta_font": meta_font,
        }

        def apply_layout(next_orient: str) -> None:
            permanent = {status_lbl, time_lbl, focus_lbl, pause_btn, close_btn}
            for child in list(body.winfo_children()):
                if child not in permanent:
                    try:
                        child.destroy()
                    except Exception:
                        pass
                else:
                    child.pack_forget()
            accent.pack_forget()
            body.pack_forget()

            if next_orient == "vertical":
                accent.configure(width=60, height=3)
                accent.pack(side="top", fill="x")
                body.pack(side="top", fill="both", expand=True, padx=6, pady=8)
                status_lbl.configure(font=title_font, anchor="center")
                time_lbl.configure(font=time_font, anchor="center")
                focus_lbl.configure(
                    font=meta_font,
                    anchor="center",
                    justify="center",
                    wraplength=_V_W - 12,
                )
                status_lbl.pack(fill="x", pady=(0, 4))
                time_lbl.pack(fill="x", pady=(0, 8))
                focus_lbl.pack(fill="both", expand=True)
                pause_btn.pack(side="bottom", fill="x", pady=(8, 4))
                close_btn.pack(side="bottom", fill="x")
            else:
                accent.configure(width=4, height=_H_H)
                accent.pack(side="left", fill="y")
                body.pack(side="left", fill="both", expand=True, padx=10, pady=8)
                top = tk.Frame(body, bg=_INK)
                top.pack(fill="x")
                status_lbl.configure(font=title_font, anchor="w")
                time_lbl.configure(font=time_font, anchor="e")
                focus_lbl.configure(
                    font=meta_font,
                    anchor="w",
                    justify="left",
                    wraplength=_H_W - 48,
                )
                status_lbl.pack(in_=top, side="left")
                time_lbl.pack(in_=top, side="right")
                focus_lbl.pack(fill="x", pady=(2, 0))
                actions = tk.Frame(body, bg=_INK)
                actions.pack(fill="x", pady=(4, 0))
                pause_btn.pack(in_=actions, side="left")
                close_btn.pack(in_=actions, side="right")

            self._orient = next_orient
            self._bind_drag(
                [
                    shell,
                    accent,
                    body,
                    status_lbl,
                    time_lbl,
                    focus_lbl,
                ]
            )

        _drag: dict[str, int] = {"x": 0, "y": 0}

        def start_drag(event: Any) -> None:
            _drag["x"] = event.x_root - root.winfo_x()
            _drag["y"] = event.y_root - root.winfo_y()

        def on_drag(event: Any) -> None:
            nx = event.x_root - _drag["x"]
            ny = event.y_root - _drag["y"]
            root.geometry(f"+{nx}+{ny}")
            self._maybe_flip()

        def end_drag(_event: Any | None = None) -> None:
            self._maybe_flip(snap=True)
            self._save_geometry()

        self._start_drag = start_drag
        self._on_drag = on_drag
        self._end_drag = end_drag

        def _bind_drag(widgets: list[Any]) -> None:
            for widget in widgets:
                widget.bind("<Button-1>", start_drag)
                widget.bind("<B1-Motion>", on_drag)
                widget.bind("<ButtonRelease-1>", end_drag)
                widget.bind("<Double-Button-1>", open_dash)

        self._bind_drag = _bind_drag  # type: ignore[method-assign]

        def _maybe_flip(*, snap: bool = False) -> None:
            sw = int(root.winfo_screenwidth() or 1280)
            sh = int(root.winfo_screenheight() or 800)
            x0 = int(root.winfo_x())
            y0 = int(root.winfo_y())
            cur_w = _V_W if self._orient == "vertical" else _H_W
            next_orient = _orient_for_position(x0, cur_w, sw)
            if next_orient != self._orient:
                apply_layout(next_orient)
            if next_orient == "vertical":
                w1, h1 = _V_W, _V_H
                x1 = sw - w1 - 10 if snap or x0 + cur_w >= sw - _EDGE_PX else x0
                x1 = max(0, min(x1, sw - w1 - 2))
            else:
                w1, h1 = _H_W, _H_H
                x1 = max(0, min(x0, sw - w1 - 2))
            y1 = max(0, min(y0, sh - h1 - 2))
            root.geometry(f"{w1}x{h1}+{x1}+{y1}")

        self._maybe_flip = _maybe_flip  # type: ignore[method-assign]

        apply_layout(orient)
        root.bind("<Escape>", close_widget)
        root.protocol("WM_DELETE_WINDOW", close_widget)

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
                status_lbl.configure(text="Ⅱ", fg=_WARN)
                pause_btn.configure(text="▶")
                accent.configure(bg=_WARN)
            elif idle:
                status_lbl.configure(text="○", fg=_IDLE)
                pause_btn.configure(text="Ⅱ")
                accent.configure(bg=_IDLE)
            else:
                status_lbl.configure(text="●", fg=_ACCENT_SOFT)
                pause_btn.configure(text="Ⅱ")
                accent.configure(bg=_ACCENT)

            elapsed = float(snap.get("session_elapsed_sec") or 0)
            time_lbl.configure(text=_fmt_elapsed(elapsed))
            focus_lbl.configure(text=_focus_label(snap, vertical=self._orient == "vertical"))

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
            self._widgets = {}
