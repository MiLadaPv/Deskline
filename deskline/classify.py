from __future__ import annotations

import re
from urllib.parse import urlparse

Category = str  # productive | neutral | distracting

BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "browser.exe",  # Yandex
    "opera.exe",
    "brave.exe",
    "vivaldi.exe",
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


def normalize_app(app_name: str | None) -> str:
    return (app_name or "unknown").strip().lower()


def extract_site_from_title(window_title: str | None, app_name: str | None = None) -> str | None:
    """Best-effort domain extraction from browser window titles."""
    title = (window_title or "").strip()
    if not title:
        return None

    app = normalize_app(app_name)
    if app and app not in BROWSER_PROCESSES and not any(
        b.replace(".exe", "") in app for b in BROWSER_PROCESSES
    ):
        # Still try if title looks like a URL, otherwise skip.
        if "://" not in title and not re.search(r"\b[\w.-]+\.[a-z]{2,}\b", title, re.I):
            return None

    # Explicit URL in title
    url_match = re.search(r"(https?://[^\s]+)", title, re.I)
    if url_match:
        host = urlparse(url_match.group(1)).hostname
        return _clean_host(host)

    # Common patterns: "Page Title - example.com" / "Page Title — example.com"
    for sep in (" - ", " — ", " | ", " – "):
        if sep in title:
            parts = [p.strip() for p in title.split(sep) if p.strip()]
            for part in reversed(parts):
                host = _maybe_host(part)
                if host:
                    return host

    # Fallback: first domain-looking token
    token = re.search(r"\b([a-z0-9][a-z0-9.-]+\.[a-z]{2,})\b", title, re.I)
    if token:
        return _clean_host(token.group(1))
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


def classify(
    app_name: str | None,
    site: str | None = None,
    user_app_rules: dict[str, str] | None = None,
    user_site_rules: dict[str, str] | None = None,
) -> Category:
    app = normalize_app(app_name)
    site = _clean_host(site)

    user_app_rules = user_app_rules or {}
    user_site_rules = user_site_rules or {}

    if site:
        if site in user_site_rules:
            return user_site_rules[site]
        for key, cat in user_site_rules.items():
            if site.endswith("." + key) or site == key:
                return cat
        if site in DEFAULT_SITE_RULES:
            return DEFAULT_SITE_RULES[site]
        for key, cat in DEFAULT_SITE_RULES.items():
            if site.endswith("." + key) or site == key:
                return cat

    if app in user_app_rules:
        return user_app_rules[app]
    if app in DEFAULT_APP_RULES:
        return DEFAULT_APP_RULES[app]
    return "neutral"
