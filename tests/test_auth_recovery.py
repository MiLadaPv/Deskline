from __future__ import annotations

from deskline.auth import (
    ensure_recovery_code,
    has_recovery_code,
    reset_password_with_recovery,
    set_password,
    verify_password,
    verify_recovery_code,
)


def test_recovery_code_reset(tmp_path, monkeypatch):
    monkeypatch.setattr("deskline.auth.AUTH_PATH", tmp_path / "auth.json")
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)

    code = set_password("secret1", issue_recovery=True)
    assert code
    assert has_recovery_code()
    assert verify_recovery_code(code)
    assert verify_recovery_code(code.replace("-", ""))
    assert not verify_recovery_code("AAAA-BBBB-CCCC")

    new_code = reset_password_with_recovery(code, "secret2")
    assert verify_password("secret2")
    assert not verify_password("secret1")
    assert new_code
    assert verify_recovery_code(new_code)
    assert not verify_recovery_code(code)


def test_ensure_recovery_for_legacy_account(tmp_path, monkeypatch):
    monkeypatch.setattr("deskline.auth.AUTH_PATH", tmp_path / "auth.json")
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)

    set_password("legacy", issue_recovery=True)
    # wipe recovery to simulate old install
    from deskline.auth import _load_auth, _save_auth

    data = _load_auth()
    data.pop("recovery_hash", None)
    _save_auth(data)
    assert not has_recovery_code()
    issued = ensure_recovery_code()
    assert issued
    assert has_recovery_code()
    assert ensure_recovery_code() is None


def test_login_template_has_launch_and_forgot():
    from deskline.config import WEB_ROOT

    html = (WEB_ROOT / "templates" / "login.html").read_text(encoding="utf-8")
    assert "launch-hero" in html
    assert "Забыли пароль?" in html
    assert "recoverForm" in html
    assert "logo-anim" in html
    assert "preview-gauge" in html
    assert "preview-donut" not in html or "preview-gauge" in html
    assert "Кто в фокусе" in html
    assert "Ритм фокуса" in html
    assert "Highest % productive time" not in html
