"""Standalone still-working dialog (own process = reliable UI thread).

Exit codes: 0 = continue tracking, 1 = pause, 2 = timeout/dismiss.
"""

from __future__ import annotations

import sys


def _run_tk(title: str, body: str, timeout_sec: float) -> int:
    import tkinter as tk
    from tkinter import font as tkfont

    result = {"code": 2}

    root = tk.Tk()
    root.title(title or "Deskline")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.configure(bg="#f3f7f5")

    width, height = 420, 280
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{width}x{height}+{(sw - width) // 2}+{(sh - height) // 3}")

    title_font = tkfont.Font(family="Segoe UI Semibold", size=13)
    body_font = tkfont.Font(family="Segoe UI", size=10)
    btn_font = tkfont.Font(family="Segoe UI Semibold", size=10)

    frame = tk.Frame(root, bg="#f3f7f5", padx=24, pady=20)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="Deskline",
        fg="#1f6b56",
        bg="#f3f7f5",
        font=title_font,
        anchor="w",
    ).pack(fill="x")

    tk.Label(
        frame,
        text="Вы ещё за компьютером?",
        fg="#15241f",
        bg="#f3f7f5",
        font=title_font,
        anchor="w",
        pady=(10, 8),
    ).pack(fill="x")

    tk.Label(
        frame,
        text=body,
        fg="#4a5c56",
        bg="#f3f7f5",
        font=body_font,
        wraplength=360,
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(0, 16))

    btns = tk.Frame(frame, bg="#f3f7f5")
    btns.pack(fill="x")

    def choose(code: int) -> None:
        result["code"] = code
        root.destroy()

    cont = tk.Button(
        btns,
        text="Продолжить",
        font=btn_font,
        bg="#1f6b56",
        fg="#ffffff",
        activebackground="#2a8570",
        activeforeground="#ffffff",
        relief="flat",
        padx=18,
        pady=10,
        cursor="hand2",
        command=lambda: choose(0),
    )
    cont.pack(side="left", padx=(0, 10))

    pause = tk.Button(
        btns,
        text="На паузу",
        font=btn_font,
        bg="#ffffff",
        fg="#15241f",
        activebackground="#e7eeeb",
        relief="solid",
        borderwidth=1,
        padx=18,
        pady=10,
        cursor="hand2",
        command=lambda: choose(1),
    )
    pause.pack(side="left")

    tk.Label(
        frame,
        text=f"Без ответа через {int(timeout_sec)} с — учёт продолжится",
        fg="#7a8f87",
        bg="#f3f7f5",
        font=tkfont.Font(family="Segoe UI", size=9),
        anchor="w",
        pady=(14, 0),
    ).pack(fill="x")

    root.protocol("WM_DELETE_WINDOW", lambda: choose(2))
    root.after(int(max(5.0, timeout_sec) * 1000), lambda: choose(2))
    root.focus_force()
    cont.focus_set()
    root.mainloop()
    return int(result["code"])


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    title = args[0] if len(args) > 0 else "Deskline"
    body = args[1] if len(args) > 1 else "Нет ввода с клавиатуры и мыши."
    try:
        timeout_sec = float(args[2]) if len(args) > 2 else 45.0
    except ValueError:
        timeout_sec = 45.0
    try:
        return _run_tk(title, body, timeout_sec)
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
