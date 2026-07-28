"""Welcome-back panel after long idle / sleep (own process = reliable UI thread).

Reads payload JSON path from argv[1], writes result JSON next to it (or --result PATH).

Result:
  {"action": "continue"|"pause"|"clear", "project_id": int|null, "task_id": int|null}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _load_payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


def _write_result(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _fmt_away(sec: float) -> str:
    sec = max(0, int(sec))
    if sec < 60:
        return f"{sec} с"
    mins = sec // 60
    if mins < 60:
        return f"{mins} мин"
    hours = mins // 60
    rem = mins % 60
    if rem:
        return f"{hours} ч {rem} мин"
    return f"{hours} ч"


def _run_tk(payload: dict[str, Any], result_path: Path) -> int:
    import tkinter as tk
    from tkinter import font as tkfont

    result: dict[str, Any] = {
        "action": "continue",
        "project_id": payload.get("project_id"),
        "task_id": payload.get("task_id"),
    }

    projects = [
        p
        for p in (payload.get("projects") or [])
        if isinstance(p, dict) and p.get("id") is not None
    ]
    selected = {"id": payload.get("project_id")}

    away = _fmt_away(float(payload.get("away_sec") or 0))
    reason = str(payload.get("reason") or "idle")
    reason_line = (
        f"ПК просыпался · отсутствовали {away}"
        if reason == "sleep"
        else f"Без ввода {away}"
    )
    cur_name = str(payload.get("project_name") or "Без проекта").strip() or "Без проекта"
    cur_task = str(payload.get("task_name") or "").strip()
    cur_color = str(payload.get("project_color") or "#1f6b56")

    root = tk.Tk()
    root.title("Deskline · Снова за ПК")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.configure(bg="#eef4f1")

    width, height = 440, 520
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{width}x{height}+{(sw - width) // 2}+{(sh - height) // 4}")

    title_font = tkfont.Font(family="Segoe UI Semibold", size=14)
    brand_font = tkfont.Font(family="Segoe UI Semibold", size=11)
    body_font = tkfont.Font(family="Segoe UI", size=10)
    small_font = tkfont.Font(family="Segoe UI", size=9)
    btn_font = tkfont.Font(family="Segoe UI Semibold", size=10)

    shell = tk.Frame(root, bg="#eef4f1", padx=18, pady=16)
    shell.pack(fill="both", expand=True)

    card = tk.Frame(shell, bg="#ffffff", highlightthickness=1, highlightbackground="#d5e2dc")
    card.pack(fill="both", expand=True)
    inner = tk.Frame(card, bg="#ffffff", padx=20, pady=18)
    inner.pack(fill="both", expand=True)

    head = tk.Frame(inner, bg="#ffffff")
    head.pack(fill="x")
    tk.Label(head, text="Deskline", fg="#1f6b56", bg="#ffffff", font=brand_font, anchor="w").pack(
        side="left"
    )
    tk.Label(head, text="возврат", fg="#7a8f87", bg="#ffffff", font=small_font, anchor="e").pack(
        side="right"
    )

    tk.Label(
        inner,
        text="Снова за ПК",
        fg="#15241f",
        bg="#ffffff",
        font=title_font,
        anchor="w",
        pady=(12, 2),
    ).pack(fill="x")
    tk.Label(
        inner,
        text=reason_line,
        fg="#4a5c56",
        bg="#ffffff",
        font=body_font,
        anchor="w",
    ).pack(fill="x", pady=(0, 14))

    focus = tk.Frame(inner, bg="#f3f7f5", padx=12, pady=10)
    focus.pack(fill="x", pady=(0, 14))
    accent = tk.Frame(focus, bg=cur_color, width=4)
    accent.pack(side="left", fill="y", padx=(0, 10))
    focus_text = tk.Frame(focus, bg="#f3f7f5")
    focus_text.pack(side="left", fill="x", expand=True)
    tk.Label(
        focus_text, text="Сейчас в фокусе", fg="#7a8f87", bg="#f3f7f5", font=small_font, anchor="w"
    ).pack(fill="x")
    focus_name = tk.Label(
        focus_text, text=cur_name, fg="#15241f", bg="#f3f7f5", font=brand_font, anchor="w"
    )
    focus_name.pack(fill="x")
    focus_task = tk.Label(
        focus_text,
        text=cur_task or " ",
        fg="#4a5c56",
        bg="#f3f7f5",
        font=small_font,
        anchor="w",
    )
    focus_task.pack(fill="x")

    tk.Label(
        inner,
        text="Переключить проект",
        fg="#15241f",
        bg="#ffffff",
        font=brand_font,
        anchor="w",
    ).pack(fill="x", pady=(0, 6))

    search_var = tk.StringVar()
    search = tk.Entry(
        inner,
        textvariable=search_var,
        font=body_font,
        bg="#f8fbf9",
        fg="#15241f",
        relief="solid",
        bd=1,
        highlightthickness=0,
    )
    search.pack(fill="x", ipady=6, pady=(0, 8))
    search.insert(0, "")
    # placeholder via label overlay is heavy; use empty + hint below
    tk.Label(
        inner,
        text="Начните вводить имя проекта",
        fg="#9aaba4",
        bg="#ffffff",
        font=small_font,
        anchor="w",
    ).pack(fill="x", pady=(0, 6))

    list_frame = tk.Frame(inner, bg="#ffffff")
    list_frame.pack(fill="both", expand=True)
    scroll = tk.Scrollbar(list_frame)
    scroll.pack(side="right", fill="y")
    listbox = tk.Listbox(
        list_frame,
        font=body_font,
        bg="#ffffff",
        fg="#15241f",
        selectbackground="#d8ebe3",
        selectforeground="#15241f",
        activestyle="none",
        relief="solid",
        bd=1,
        highlightthickness=0,
        yscrollcommand=scroll.set,
        exportselection=False,
    )
    listbox.pack(side="left", fill="both", expand=True)
    scroll.config(command=listbox.yview)

    visible: list[dict[str, Any]] = []

    def refresh_list(*_args: Any) -> None:
        q = search_var.get().strip().casefold()
        listbox.delete(0, tk.END)
        visible.clear()
        for p in projects:
            name = str(p.get("name") or "").strip()
            if q and q not in name.casefold():
                continue
            visible.append(p)
            listbox.insert(tk.END, name or f"#{p.get('id')}")
        # select current if visible
        for i, p in enumerate(visible):
            if selected["id"] is not None and int(p["id"]) == int(selected["id"]):
                listbox.selection_set(i)
                listbox.see(i)
                break

    def on_select(_evt: Any = None) -> None:
        sel = listbox.curselection()
        if not sel:
            return
        p = visible[int(sel[0])]
        selected["id"] = int(p["id"])
        result["project_id"] = int(p["id"])
        result["task_id"] = None
        focus_name.config(text=str(p.get("name") or "Проект"))
        focus_task.config(text=" ")
        color = str(p.get("color") or "#1f6b56")
        accent.config(bg=color)

    search_var.trace_add("write", refresh_list)
    listbox.bind("<<ListboxSelect>>", on_select)
    refresh_list()

    def finish(action: str) -> None:
        result["action"] = action
        if action == "clear":
            result["project_id"] = None
            result["task_id"] = None
        elif action == "continue":
            result["project_id"] = selected["id"]
            # keep task only if project unchanged
            if payload.get("project_id") is None or selected["id"] is None:
                result["task_id"] = None
            elif int(selected["id"]) != int(payload.get("project_id")):
                result["task_id"] = None
            else:
                result["task_id"] = payload.get("task_id")
        _write_result(result_path, result)
        root.destroy()

    btns = tk.Frame(inner, bg="#ffffff")
    btns.pack(fill="x", pady=(14, 0))

    cont = tk.Button(
        btns,
        text="Продолжить",
        font=btn_font,
        bg="#1f6b56",
        fg="#ffffff",
        activebackground="#2a8570",
        activeforeground="#ffffff",
        relief="flat",
        padx=16,
        pady=10,
        cursor="hand2",
        command=lambda: finish("continue"),
    )
    cont.pack(side="left", padx=(0, 8))

    pause = tk.Button(
        btns,
        text="На паузу",
        font=btn_font,
        bg="#ffffff",
        fg="#15241f",
        activebackground="#e7eeeb",
        relief="solid",
        borderwidth=1,
        padx=16,
        pady=10,
        cursor="hand2",
        command=lambda: finish("pause"),
    )
    pause.pack(side="left")

    clear = tk.Button(
        inner,
        text="Без проекта · просто продолжить учёт",
        font=small_font,
        bg="#ffffff",
        fg="#1f6b56",
        activeforeground="#2a8570",
        relief="flat",
        cursor="hand2",
        anchor="w",
        command=lambda: finish("clear"),
    )
    clear.pack(fill="x", pady=(10, 0))

    tk.Label(
        inner,
        text="Без ответа — продолжим с прежним фокусом",
        fg="#9aaba4",
        bg="#ffffff",
        font=small_font,
        anchor="w",
        pady=(10, 0),
    ).pack(fill="x")

    timeout_sec = float(payload.get("timeout_sec") or 60.0)

    def on_timeout() -> None:
        result["action"] = "continue"
        result["project_id"] = payload.get("project_id")
        result["task_id"] = payload.get("task_id")
        _write_result(result_path, result)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_timeout)
    root.after(int(max(15.0, timeout_sec) * 1000), on_timeout)
    root.focus_force()
    search.focus_set()
    root.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        return 2
    payload_path = Path(args[0])
    result_path = Path(args[1]) if len(args) > 1 else payload_path.with_suffix(".result.json")
    try:
        payload = _load_payload(payload_path)
    except Exception:
        return 2
    try:
        return _run_tk(payload, result_path)
    except Exception:
        _write_result(
            result_path,
            {
                "action": "continue",
                "project_id": payload.get("project_id"),
                "task_id": payload.get("task_id"),
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
