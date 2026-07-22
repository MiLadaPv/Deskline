from __future__ import annotations

from pathlib import Path

from deskline.api import autostart_command
from deskline.notify import still_working_body


def test_still_working_body_explains_continue_and_pause() -> None:
    text = still_working_body("Cursor")
    assert "Cursor" in text
    assert "Продолжить" in text
    assert "пауз" in text.lower()
    assert "перерыв" in text.lower()
    # Old misleading advice must be gone
    assert "выберите «Да, работаю»" not in text


def test_still_working_body_message_box_mentions_yes_no() -> None:
    text = still_working_body("Deskline", for_message_box=True)
    assert text.startswith("Нет клавиатуры")
    assert "Да —" in text
    assert "Нет —" in text


def test_autostart_prefers_desktop_exe(tmp_path: Path, monkeypatch) -> None:
    desktop = tmp_path / "Programs" / "Deskline" / "deskline-desktop.exe"
    desktop.parent.mkdir(parents=True)
    desktop.write_bytes(b"mz")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    cmd = autostart_command()
    assert "deskline-desktop.exe" in cmd
    assert str(desktop) in cmd.replace('"', "")


def test_autostart_falls_back_to_python_module(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("sys.frozen", False, raising=False)
    monkeypatch.setattr("sys.executable", str(tmp_path / "python.exe"))
    (tmp_path / "python.exe").write_bytes(b"x")
    cmd = autostart_command()
    assert "-m deskline" in cmd
    assert "deskline-desktop.exe" not in cmd
