from __future__ import annotations

from pathlib import Path

from deskline.config import DEFAULT_CONFIG


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")
JS = (ROOT / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")


def test_personal_mode_is_default():
    assert DEFAULT_CONFIG.get("personal_mode") is True
    assert DEFAULT_CONFIG.get("company_mode") is False


def test_personal_ui_hides_team_surfaces():
    assert 'data-team-only' in HTML
    assert 'id="whoBlock"' in HTML
    assert 'data-team-only' in HTML[HTML.index('id="whoBlock"') : HTML.index('id="whoBlock"') + 80]
    assert 'id="checkoutTeam"' in HTML
    assert "applyPersonalMode" in JS
    assert "showTeamUi" in JS
    assert 'data-personal' in JS
    assert 'html[data-personal="1"]' in CSS
    assert "personal_mode: true" in JS or "personal_mode:true" in JS.replace(" ", "")


def test_settings_keep_company_markup_for_later():
    assert 'name="company_mode"' in HTML
    assert "Компания" in HTML
    assert "Агент → hub" in HTML
