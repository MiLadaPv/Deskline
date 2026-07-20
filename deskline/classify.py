from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

Category = str  # productive | neutral | distracting
ActivityKind = str

BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "browser.exe",  # Yandex
    "opera.exe",
    "brave.exe",
    "vivaldi.exe",
}

APP_DISPLAY_NAMES: dict[str, str] = {
    "msedge.exe": "Microsoft Edge",
    "chrome.exe": "Google Chrome",
    "firefox.exe": "Firefox",
    "browser.exe": "Yandex Browser",
    "opera.exe": "Opera",
    "brave.exe": "Brave",
    "vivaldi.exe": "Vivaldi",
    "code.exe": "VS Code",
    "cursor.exe": "Cursor",
    "devenv.exe": "Visual Studio",
    "idea64.exe": "IntelliJ IDEA",
    "pycharm64.exe": "PyCharm",
    "winword.exe": "Word",
    "excel.exe": "Excel",
    "powerpnt.exe": "PowerPoint",
    "outlook.exe": "Outlook",
    "teams.exe": "Microsoft Teams",
    "ms-teams.exe": "Microsoft Teams",
    "slack.exe": "Slack",
    "discord.exe": "Discord",
    "telegram.exe": "Telegram",
    "spotify.exe": "Spotify",
    "steam.exe": "Steam",
    "mstsc.exe": "Remote Desktop",
    "explorer.exe": "Проводник",
    "chatgpt classic.exe": "ChatGPT",
    "notepad++.exe": "Notepad++",
    "mpc-hc64.exe": "Media Player Classic",
    "qemu-system-x86_64.exe": "QEMU",
    "lockapp.exe": "Экран блокировки",
    "shellhost.exe": "Windows Shell",
}

# Noise / installer processes — hide from main rankings
SYSTEM_APPS = {
    "lockapp.exe",
    "shellhost.exe",
    "searchhost.exe",
    "textinputhost.exe",
    "applicationframehost.exe",
    "systemsettings.exe",
    "securityhealthsystray.exe",
    # Remote Desktop client itself — track work on the PC, not the RDP window
    "mstsc.exe",
    "msrdc.exe",
    "rdpclip.exe",
}

DEFAULT_APP_RULES: dict[str, Category] = {
    "code.exe": "productive",
    "devenv.exe": "productive",
    "idea64.exe": "productive",
    "pycharm64.exe": "productive",
    "cursor.exe": "productive",
    "notepad++.exe": "productive",
    "winword.exe": "productive",
    "excel.exe": "productive",
    "powerpnt.exe": "productive",
    "outlook.exe": "productive",
    "teams.exe": "productive",
    "ms-teams.exe": "productive",
    "slack.exe": "neutral",
    "discord.exe": "distracting",
    "spotify.exe": "distracting",
    "steam.exe": "distracting",
    "telegram.exe": "distracting",
}

DEFAULT_SITE_RULES: dict[str, Category] = {
    "github.com": "productive",
    "gitlab.com": "productive",
    "stackoverflow.com": "productive",
    "docs.microsoft.com": "productive",
    "learn.microsoft.com": "productive",
    "notion.so": "productive",
    "youtube.com": "distracting",
    "youtu.be": "distracting",
    "tiktok.com": "distracting",
    "instagram.com": "distracting",
    "facebook.com": "distracting",
    "vk.com": "distracting",
    "twitter.com": "distracting",
    "x.com": "distracting",
    "reddit.com": "distracting",
    "netflix.com": "distracting",
}

# domain suffix -> (kind, label_ru, category)
SITE_ACTIVITIES: dict[str, tuple[ActivityKind, str, Category]] = {
    "youtube.com": ("video", "YouTube", "distracting"),
    "youtu.be": ("video", "YouTube", "distracting"),
    "netflix.com": ("video", "Netflix", "distracting"),
    "twitch.tv": ("video", "Twitch", "distracting"),
    "tiktok.com": ("video", "TikTok", "distracting"),
    "rutube.ru": ("video", "RuTube", "distracting"),
    "gmail.com": ("email", "Почта", "productive"),
    "mail.google.com": ("email", "Почта", "productive"),
    "mail.yandex.ru": ("email", "Почта", "productive"),
    "mail.ru": ("email", "Почта", "productive"),
    "outlook.live.com": ("email", "Почта", "productive"),
    "outlook.office.com": ("email", "Почта", "productive"),
    "web.telegram.org": ("messaging", "Мессенджер", "distracting"),
    "web.whatsapp.com": ("messaging", "Мессенджер", "distracting"),
    "web.skype.com": ("messaging", "Мессенджер", "neutral"),
    "discord.com": ("messaging", "Discord", "distracting"),
    "vk.com": ("social", "Соцсети", "distracting"),
    "instagram.com": ("social", "Соцсети", "distracting"),
    "facebook.com": ("social", "Соцсети", "distracting"),
    "twitter.com": ("social", "Соцсети", "distracting"),
    "x.com": ("social", "Соцсети", "distracting"),
    "reddit.com": ("social", "Reddit", "distracting"),
    "github.com": ("work", "Работа", "productive"),
    "gitlab.com": ("work", "Работа", "productive"),
    "stackoverflow.com": ("work", "Работа", "productive"),
    "notion.so": ("work", "Работа", "productive"),
    "docs.google.com": ("work", "Документы", "productive"),
    "docs.microsoft.com": ("work", "Документы", "productive"),
    "learn.microsoft.com": ("work", "Обучение", "productive"),
    "figma.com": ("work", "Дизайн", "productive"),
    "chatgpt.com": ("work", "AI-чат", "productive"),
    "chat.openai.com": ("work", "AI-чат", "productive"),
    "claude.ai": ("work", "AI-чат", "productive"),
    "amazon.com": ("shopping", "Покупки", "neutral"),
    "ozon.ru": ("shopping", "Покупки", "neutral"),
    "wildberries.ru": ("shopping", "Покупки", "neutral"),
    "avito.ru": ("shopping", "Покупки", "neutral"),
}

SEARCH_HOSTS = {
    "google.com",
    "www.google.com",
    "yandex.ru",
    "ya.ru",
    "bing.com",
    "duckduckgo.com",
}

APP_ACTIVITY_DEFAULTS: dict[str, tuple[ActivityKind, str]] = {
    "telegram.exe": ("messaging", "Мессенджер"),
    "discord.exe": ("messaging", "Discord"),
    "slack.exe": ("messaging", "Slack"),
    "outlook.exe": ("email", "Почта"),
    "spotify.exe": ("video", "Музыка"),
    "steam.exe": ("other", "Игры"),
    "code.exe": ("work", "Разработка"),
    "cursor.exe": ("work", "Разработка"),
    "devenv.exe": ("work", "Разработка"),
    "winword.exe": ("work", "Документы"),
    "excel.exe": ("work", "Таблицы"),
    "teams.exe": ("messaging", "Созвоны"),
    "ms-teams.exe": ("messaging", "Созвоны"),
}


def normalize_app(app_name: str | None) -> str:
    return (app_name or "unknown").strip().lower()


def is_browser(app_name: str | None) -> bool:
    app = normalize_app(app_name)
    return app in BROWSER_PROCESSES


def is_system_noise(app_name: str | None) -> bool:
    app = normalize_app(app_name)
    if app in SYSTEM_APPS:
        return True
    if app.endswith(".tmp"):
        return True
    if "setup" in app and (app.endswith(".exe") or app.endswith(".tmp")):
        return True
    return False


def display_name_for_app(app_name: str | None) -> str:
    app = normalize_app(app_name)
    if app in APP_DISPLAY_NAMES:
        return APP_DISPLAY_NAMES[app]
    # Strip .exe and title-case
    base = app[:-4] if app.endswith(".exe") else app
    return base.replace("_", " ").replace("-", " ").title() or "Unknown"


def extract_site_from_title(window_title: str | None, app_name: str | None = None) -> str | None:
    """Best-effort domain extraction from browser window titles."""
    title = (window_title or "").strip()
    if not title:
        return None

    app = normalize_app(app_name)
    if app and not is_browser(app):
        if "://" not in title and not re.search(r"\b[\w.-]+\.[a-z]{2,}\b", title, re.I):
            return None

    url_match = re.search(r"(https?://[^\s]+)", title, re.I)
    if url_match:
        host = urlparse(url_match.group(1)).hostname
        return _clean_host(host)

    for sep in (" - ", " — ", " | ", " – "):
        if sep in title:
            parts = [p.strip() for p in title.split(sep) if p.strip()]
            for part in reversed(parts):
                host = _maybe_host(part)
                if host:
                    return host

    token = re.search(r"\b([a-z0-9][a-z0-9.-]+\.[a-z]{2,})\b", title, re.I)
    if token:
        return _clean_host(token.group(1))

    # Brand hints without domain in title
    low = title.lower()
    if "youtube" in low:
        return "youtube.com"
    if "gmail" in low:
        return "gmail.com"
    if "whatsapp" in low:
        return "web.whatsapp.com"
    return None


def _maybe_host(value: str) -> str | None:
    value = value.strip().rstrip("/")
    if " " in value:
        return None
    if value.startswith("www."):
        value = value[4:]
    if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", value, re.I):
        return value.lower()
    return None


def _clean_host(host: str | None) -> str | None:
    if not host:
        return None
    host = host.lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _match_site_activity(site: str | None) -> tuple[ActivityKind, str, Category] | None:
    site = _clean_host(site)
    if not site:
        return None
    if site in SITE_ACTIVITIES:
        return SITE_ACTIVITIES[site]
    for key, val in SITE_ACTIVITIES.items():
        if site == key or site.endswith("." + key):
            return val
    if site in SEARCH_HOSTS or any(site.endswith("." + h) for h in SEARCH_HOSTS if not h.startswith("www.")):
        return ("search", "Поиск", "neutral")
    if site.startswith("google.") or site.endswith(".google.com"):
        return ("search", "Поиск", "neutral")
    return None


def classify(
    app_name: str | None,
    site: str | None = None,
    user_app_rules: dict[str, str] | None = None,
    user_site_rules: dict[str, str] | None = None,
) -> Category:
    return resolve_activity(app_name, None, site, user_app_rules, user_site_rules)["category"]


def resolve_activity(
    app_name: str | None,
    window_title: str | None = None,
    site: str | None = None,
    user_app_rules: dict[str, str] | None = None,
    user_site_rules: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve human-facing labels for a window session."""
    app = normalize_app(app_name)
    site = _clean_host(site) or extract_site_from_title(window_title, app)
    display = display_name_for_app(app)
    user_app_rules = user_app_rules or {}
    user_site_rules = user_site_rules or {}

    if is_system_noise(app):
        return {
            "display_name": display,
            "activity_kind": "system",
            "activity_label": "Система",
            "category": "neutral",
            "url_hint": site,
            "hidden": True,
        }

    # Site-driven activity (especially browsers)
    matched = _match_site_activity(site)
    if matched:
        kind, label, cat = matched
        if site and site in user_site_rules:
            cat = user_site_rules[site]
        elif site:
            for key, ucat in user_site_rules.items():
                if site == key or site.endswith("." + key):
                    cat = ucat
                    break
        if is_browser(app):
            # Prefer activity label over "Microsoft Edge"
            return {
                "display_name": display,
                "activity_kind": kind,
                "activity_label": label,
                "category": cat,
                "url_hint": site,
                "hidden": False,
            }
        return {
            "display_name": display,
            "activity_kind": kind,
            "activity_label": label,
            "category": cat,
            "url_hint": site,
            "hidden": False,
        }

    if is_browser(app):
        # Unknown site in browser
        cat = "neutral"
        if app in user_app_rules:
            cat = user_app_rules[app]
        label = site if site else "Браузер · другое"
        return {
            "display_name": display,
            "activity_kind": "other" if site else "other",
            "activity_label": label if site else "Браузер",
            "category": cat,
            "url_hint": site,
            "hidden": False,
        }

    # Desktop apps
    if app in APP_ACTIVITY_DEFAULTS:
        kind, label = APP_ACTIVITY_DEFAULTS[app]
    else:
        kind, label = "other", display

    cat: Category = "neutral"
    if app in user_app_rules:
        cat = user_app_rules[app]
    elif app in DEFAULT_APP_RULES:
        cat = DEFAULT_APP_RULES[app]
    elif kind in {"messaging", "video", "social"}:
        cat = "distracting"
    elif kind in {"work", "email", "remote"}:
        cat = "productive"

    return {
        "display_name": display,
        "activity_kind": kind,
        "activity_label": label,
        "category": cat,
        "url_hint": site,
        "hidden": False,
    }
