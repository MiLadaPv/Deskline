from __future__ import annotations

import time

from deskline.auth import (
    SESSION_TTL_REMEMBER_SEC,
    SESSION_TTL_SEC,
    create_session_token,
    set_password,
    validate_session_token,
)


def test_create_session_token_ttl_default_and_remember(tmp_path, monkeypatch):
    monkeypatch.setattr("deskline.auth.AUTH_PATH", tmp_path / "auth.json")
    monkeypatch.setattr("deskline.config.DATA_ROOT", tmp_path)
    set_password("secret1")

    now = int(time.time())
    short = create_session_token(remember=False)
    long = create_session_token(remember=True)
    assert validate_session_token(short)
    assert validate_session_token(long)

    short_exp = int(short.split(".", 1)[0])
    long_exp = int(long.split(".", 1)[0])
    assert abs(short_exp - (now + SESSION_TTL_SEC)) <= 3
    assert abs(long_exp - (now + SESSION_TTL_REMEMBER_SEC)) <= 3
    assert long_exp - short_exp >= SESSION_TTL_REMEMBER_SEC - SESSION_TTL_SEC - 5


def test_login_template_has_remember_unchecked():
    from deskline.config import WEB_ROOT

    html = (WEB_ROOT / "templates" / "login.html").read_text(encoding="utf-8")
    assert 'id="rememberMe"' in html
    assert "Запомнить меня" in html
    # Must not be checked by default
    assert "checked" not in html.split('id="rememberMe"')[1].split(">")[0]
