from __future__ import annotations

from pathlib import Path

from deskline.auth import is_public_path
from deskline.config import (
    COMPANY_NAME,
    GITHUB_URL,
    LEGAL_JURISDICTION,
    SUPPORT_EMAIL,
    WEB_ROOT,
    brand_template_context,
)


def test_brand_constants():
    assert COMPANY_NAME == "AndalusGames"
    assert SUPPORT_EMAIL == "milanochka.llc@gmail.com"
    assert GITHUB_URL == "https://github.com/AndalusGames"
    assert "Jordan" in LEGAL_JURISDICTION


def test_brand_template_context_fields():
    ctx = brand_template_context(version="9.9.9")
    assert ctx["company_name"] == COMPANY_NAME
    assert ctx["support_email"] == SUPPORT_EMAIL
    assert ctx["github_url"] == GITHUB_URL
    assert ctx["version"] == "9.9.9"
    assert ctx["copyright_year"] >= 2026


def test_legal_paths_are_public():
    for path in ("/about", "/privacy", "/terms", "/login", "/welcome", "/logos", "/static/css/app.css"):
        assert is_public_path(path)
    assert not is_public_path("/")
    assert not is_public_path("/api/settings")


def test_logo_gallery_assets_exist():
    from deskline.logo_gallery import load_logo_cards

    logos = WEB_ROOT / "static" / "img" / "logos"
    assert logos.is_dir()
    cards = load_logo_cards()
    assert len(cards) >= 10
    assert all("<svg" in c["svg"] for c in cards)
    page = (WEB_ROOT / "templates" / "logos.html").read_text(encoding="utf-8")
    assert "logo_cards" in page
    assert "card.svg" in page


def test_legal_templates_exist_and_mention_company():
    for name in ("legal_base.html", "about.html", "privacy.html", "terms.html"):
        path = WEB_ROOT / "templates" / name
        assert path.is_file(), name
        text = path.read_text(encoding="utf-8")
        if name != "legal_base.html":
            assert "company_name" in text or "Deskline" in text
    about = (WEB_ROOT / "templates" / "about.html").read_text(encoding="utf-8")
    assert "local" in about.lower() or "локальн" in about.lower()
    privacy = (WEB_ROOT / "templates" / "privacy.html").read_text(encoding="utf-8")
    assert "legal_jurisdiction" in privacy
    assert Path(WEB_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    index = (WEB_ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'href="/privacy"' in index
    assert "support_email" in index
