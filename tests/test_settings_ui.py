from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")
JS = (ROOT / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")


def test_settings_search_shell_present():
    assert 'id="settingsSearch"' in HTML
    assert 'id="settingsForm"' in HTML
    assert 'class="settings-shell"' in HTML
    assert 'data-settings-group' in HTML
    assert 'name="work_mode"' in HTML
    assert 'name="screenshots_enabled"' in HTML
    assert 'name="company_mode"' in HTML
    assert 'id="licenseBox"' in HTML
    assert 'id="passwordForm"' in HTML
    assert 'id="settingsSaveBtn"' in HTML


def test_settings_apple_styles_and_search_hooks():
    assert ".settings-search" in CSS
    assert ".settings-switch" in CSS
    assert ".settings-group-ico" in CSS
    assert ".settings-card" in CSS
    assert "function filterSettingsSearch" in JS
    assert "function wireSettingsSearch" in JS
    assert "wireSettingsSearch()" in JS
