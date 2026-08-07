from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

Category = str  # productive | neutral | distracting | unrated


def normalize_category(cat: str | None) -> Category:
    c = (cat or "neutral").strip().lower()
    if c in {"productive", "neutral", "distracting", "unrated"}:
        return c
    return "neutral"


def category_for_focus(cat: str | None) -> Category:
    """Unrated does not count as focus (treated like neutral), matching Time Doctor."""
    c = normalize_category(cat)
    return "neutral" if c == "unrated" else c
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
    "windowsterminal.exe": "Терминал",
    "wt.exe": "Терминал",
    "snippingtool.exe": "Ножницы",
    "screenclippinghost.exe": "Ножницы",
    "notepad.exe": "Блокнот",
    "keepass.exe": "KeePass",
    "keepassxc.exe": "KeePassXC",
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
    # RDP clipboard helper only — the client itself is labeled as remote work
    "rdpclip.exe",
    # Credential / UAC / picker chrome
    "credentialuibroker.exe",
    "consent.exe",
    "useraccountcontrolsettings.exe",
    "pickerhost.exe",
    "openwith.exe",
    "dllhost.exe",
    "runtimebroker.exe",
    "sihost.exe",
    "startmenuexperiencehost.exe",
    "searchapp.exe",
    "searchui.exe",
    "widgetservice.exe",
    "widgets.exe",
    "shellexperiencehost.exe",
    "taskhostw.exe",
    "backgroundtaskhost.exe",
    "conhost.exe",
    "fontdrvhost.exe",
    "dwm.exe",
    "ctfmon.exe",
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
    "telegram.exe": "neutral",
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

# domain suffix -> (kind, label, category) — labels are brand/product names for readability
SITE_ACTIVITIES: dict[str, tuple[ActivityKind, str, Category]] = {
    "youtube.com": ("video", "YouTube", "distracting"),
    "youtu.be": ("video", "YouTube", "distracting"),
    "netflix.com": ("video", "Netflix", "distracting"),
    "twitch.tv": ("video", "Twitch", "distracting"),
    "tiktok.com": ("video", "TikTok", "distracting"),
    "rutube.ru": ("video", "RuTube", "distracting"),
    "gmail.com": ("email", "Gmail", "productive"),
    "mail.google.com": ("email", "Gmail", "productive"),
    "mail.yandex.ru": ("email", "Яндекс Почта", "productive"),
    "mail.ru": ("email", "Mail.ru", "productive"),
    "outlook.live.com": ("email", "Outlook", "productive"),
    "outlook.office.com": ("email", "Outlook", "productive"),
    "web.telegram.org": ("messaging", "Telegram Web", "neutral"),
    "web.whatsapp.com": ("messaging", "WhatsApp", "neutral"),
    "web.skype.com": ("messaging", "Skype", "neutral"),
    "messenger.yandex.ru": ("messaging", "Яндекс Мессенджер", "neutral"),
    "telemost.yandex.ru": ("messaging", "Яндекс Телемост", "productive"),
    "discord.com": ("messaging", "Discord", "neutral"),
    "vk.com": ("social", "ВКонтакте", "distracting"),
    "instagram.com": ("social", "Instagram", "distracting"),
    "facebook.com": ("social", "Facebook", "distracting"),
    "twitter.com": ("social", "X (Twitter)", "distracting"),
    "x.com": ("social", "X (Twitter)", "distracting"),
    "reddit.com": ("social", "Reddit", "distracting"),
    "github.com": ("work", "GitHub", "productive"),
    "gitlab.com": ("work", "GitLab", "productive"),
    "stackoverflow.com": ("work", "Stack Overflow", "productive"),
    "notion.so": ("work", "Notion", "productive"),
    "docs.google.com": ("work", "Google Docs", "productive"),
    "docs.microsoft.com": ("work", "Microsoft Docs", "productive"),
    "learn.microsoft.com": ("work", "Microsoft Learn", "productive"),
    "figma.com": ("work", "Figma", "productive"),
    "chatgpt.com": ("work", "ChatGPT", "productive"),
    "chat.openai.com": ("work", "ChatGPT", "productive"),
    "claude.ai": ("work", "Claude", "productive"),
    "habr.com": ("work", "Habr", "productive"),
    "zoom.us": ("messaging", "Zoom", "productive"),
    "meet.google.com": ("messaging", "Google Meet", "productive"),
    "teams.microsoft.com": ("messaging", "Microsoft Teams", "productive"),
    "teams.live.com": ("messaging", "Microsoft Teams", "productive"),
    "webex.com": ("messaging", "Webex", "productive"),
    "bbc.co.uk": ("other", "BBC", "neutral"),
    "bbc.com": ("other", "BBC", "neutral"),
    "linkedin.com": ("social", "LinkedIn", "neutral"),
    "wikipedia.org": ("work", "Wikipedia", "productive"),
    "amazon.com": ("shopping", "Amazon", "neutral"),
    "ozon.ru": ("shopping", "Ozon", "neutral"),
    "wildberries.ru": ("shopping", "Wildberries", "neutral"),
    "avito.ru": ("shopping", "Avito", "neutral"),
}

SEARCH_HOSTS = {
    "google.com",
    "www.google.com",
    "yandex.ru",
    "ya.ru",
    "bing.com",
    "duckduckgo.com",
}

# Keywords in tab titles → site (Edge often omits the domain)
TITLE_BRAND_HINTS: list[tuple[str, str]] = [
    ("youtube", "youtube.com"),
    ("habr", "habr.com"),
    ("хабр", "habr.com"),
    ("github", "github.com"),
    ("gitlab", "gitlab.com"),
    ("chatgpt", "chatgpt.com"),
    ("openai", "chatgpt.com"),
    ("claude.ai", "claude.ai"),
    ("gmail", "gmail.com"),
    ("whatsapp", "web.whatsapp.com"),
    ("telegram", "web.telegram.org"),
    ("discord", "discord.com"),
    ("zoom", "zoom.us"),
    ("notion", "notion.so"),
    ("figma", "figma.com"),
    ("reddit", "reddit.com"),
    ("instagram", "instagram.com"),
    ("facebook", "facebook.com"),
    ("twitter", "twitter.com"),
    ("stackoverflow", "stackoverflow.com"),
    ("stack overflow", "stackoverflow.com"),
    ("bbc", "bbc.co.uk"),
    ("netflix", "netflix.com"),
    ("twitch", "twitch.tv"),
    ("tiktok", "tiktok.com"),
    ("vk.com", "vk.com"),
    ("вконтакте", "vk.com"),
    ("яндекс мессенджер", "messenger.yandex.ru"),
    ("yandex messenger", "messenger.yandex.ru"),
    ("яндекс телемост", "telemost.yandex.ru"),
    ("yandex telemost", "telemost.yandex.ru"),
    ("телемост", "telemost.yandex.ru"),
    ("telemost", "telemost.yandex.ru"),
    ("яндекс.почта", "mail.yandex.ru"),
    ("яндекс почта", "mail.yandex.ru"),
    ("yandex mail", "mail.yandex.ru"),
    ("mail.ru", "mail.ru"),
    ("outlook", "outlook.live.com"),
    ("linkedin", "linkedin.com"),
    ("wikipedia", "wikipedia.org"),
]

_NEW_TAB_TITLES = {
    "новая вкладка",
    "new tab",
    "new tab - personal",
    "startsida",
    "about:blank",
    "edge://newtab",
    "chrome://newtab",
}

_BROWSER_EXTRA_PAGES = re.compile(
    r"\s+и еще\s+\d+\s+страниц\w*\b",
    re.IGNORECASE,
)
_BROWSER_APP_TAIL = re.compile(
    r"\s*[—\-–|]\s*(?:личный:\s*|work:\s*|рабочий:\s*)?"
    r"(?:microsoft\s*edge|google\s*chrome|mozilla\s*firefox|firefox|opera|brave|vivaldi|yandex(?:\s*browser)?)\s*$",
    re.IGNORECASE,
)
# Dynamic notification / unread counts that fragment the same site into many rows
_DYNAMIC_UNREAD_SUFFIX = re.compile(
    r"\s*[—\-–|]\s*\d+\s+"
    r"(?:"
    r"нов\w*\s+сообщени\w*"
    r"|unread(?:\s+messages?)?"
    r"|непрочитанн\w*"
    r")\s*$",
    re.IGNORECASE,
)
_DYNAMIC_PAREN_COUNT = re.compile(r"\s*\(\d+\)\s*$")
_DYNAMIC_LEADING_COUNT = re.compile(r"^\(\d+\)\s+")
_DYNAMIC_LEADING_DOT_COUNT = re.compile(r"^\d+\s*[·•.]\s+")


def normalize_dynamic_title(title: str) -> str:
    """Strip unread/notification counters so the same site keeps one activity label."""
    if not title:
        return ""
    out = title
    out = _DYNAMIC_UNREAD_SUFFIX.sub("", out)
    out = _DYNAMIC_PAREN_COUNT.sub("", out)
    out = _DYNAMIC_LEADING_COUNT.sub("", out)
    out = _DYNAMIC_LEADING_DOT_COUNT.sub("", out)
    return out.strip(" -—|·•")


def clean_browser_title(window_title: str | None) -> str:
    """Strip Edge/Chrome multi-tab and app-name suffixes from the window title."""
    title = (window_title or "").strip()
    if not title:
        return ""
    # Normalize rare unicode spaces Edge inserts in "Microsoft Edge"
    title = title.replace("\u200b", "").replace("\xa0", " ")
    title = _BROWSER_EXTRA_PAGES.sub("", title)
    title = _BROWSER_APP_TAIL.sub("", title)
    title = re.sub(r"\s+[—\-–|]\s*$", "", title)
    title = normalize_dynamic_title(title)
    return title.strip(" -—|·")


# Desktop apps: kind + brand/product label (not abstract buckets like «Разработка»)
APP_ACTIVITY_DEFAULTS: dict[str, tuple[ActivityKind, str]] = {
    "telegram.exe": ("messaging", "Telegram"),
    "discord.exe": ("messaging", "Discord"),
    "slack.exe": ("messaging", "Slack"),
    "outlook.exe": ("email", "Outlook"),
    "spotify.exe": ("video", "Spotify"),
    "steam.exe": ("other", "Steam"),
    "code.exe": ("work", "VS Code"),
    "cursor.exe": ("work", "Cursor"),
    "devenv.exe": ("work", "Visual Studio"),
    "idea64.exe": ("work", "IntelliJ IDEA"),
    "pycharm64.exe": ("work", "PyCharm"),
    "notepad++.exe": ("work", "Notepad++"),
    "winword.exe": ("work", "Word"),
    "excel.exe": ("work", "Excel"),
    "powerpnt.exe": ("work", "PowerPoint"),
    "teams.exe": ("messaging", "Microsoft Teams"),
    "ms-teams.exe": ("messaging", "Microsoft Teams"),
    "zoom.exe": ("messaging", "Zoom"),
    "skype.exe": ("messaging", "Skype"),
    "webex.exe": ("messaging", "Webex"),
    "ciscowebexstart.exe": ("messaging", "Webex"),
    "mstsc.exe": ("remote", "Удалённый рабочий стол"),
    "msrdc.exe": ("remote", "Удалённый рабочий стол"),
    "explorer.exe": ("other", "Проводник"),
    "windowsterminal.exe": ("work", "Терминал"),
    "wt.exe": ("work", "Терминал"),
}

KIND_LABELS_RU: dict[str, str] = {
    "work": "Работа",
    "remote": "Удалёнка",
    "video": "Видео / музыка",
    "messaging": "Общение",
    "email": "Почта",
    "social": "Соцсети",
    "search": "Поиск",
    "shopping": "Покупки",
    "system": "Система",
    "other": "Прочее",
}


def kind_label(kind: str | None) -> str:
    key = (kind or "other").strip().lower()
    return KIND_LABELS_RU.get(key, KIND_LABELS_RU["other"])

RDP_CLIENTS = {"mstsc.exe", "msrdc.exe"}

_RDP_TITLE_RE = re.compile(
    r"^(?P<host>.+?)\s*[-—–]\s*(?:Remote Desktop(?: Connection)?|Подключение к удалённому рабочему столу|Удалённый рабочий стол)\s*$",
    re.IGNORECASE,
)


def parse_rdp_host(window_title: str | None) -> str | None:
    """Extract remote host from an RDP client window title, if present."""
    title = (window_title or "").strip()
    if not title:
        return None
    m = _RDP_TITLE_RE.match(title)
    if m:
        host = m.group("host").strip().strip('"').strip()
        return host or None
    # Bare connection window without host
    lowered = title.lower()
    if lowered in {
        "remote desktop connection",
        "remote desktop",
        "подключение к удалённому рабочему столу",
        "удалённый рабочий стол",
    }:
        return None
    return None


def is_rdp_client(app_name: str | None) -> bool:
    return normalize_app(app_name) in RDP_CLIENTS


def normalize_app(app_name: str | None) -> str:
    return (app_name or "unknown").strip().lower()


def is_browser(app_name: str | None) -> bool:
    app = normalize_app(app_name)
    return app in BROWSER_PROCESSES


def is_system_noise(app_name: str | None) -> bool:
    app = normalize_app(app_name)
    if app in SYSTEM_APPS:
        return True
    if app.endswith(".tmp") or app.endswith(".py") or app.endswith(".pyw"):
        return True
    # Scripts / non-exe foreground noise (e.g. url.py)
    if "." in app and not app.endswith(".exe"):
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
    raw = (window_title or "").strip()
    if not raw:
        return None

    app = normalize_app(app_name)
    title = clean_browser_title(raw) if (not app or is_browser(app)) else raw
    if not title:
        title = raw

    if app and not is_browser(app):
        if "://" not in title and not re.search(r"\b[\w.-]+\.[a-z]{2,}\b", title, re.I):
            return None

    url_match = re.search(r"(https?://[^\s]+)", title, re.I)
    if url_match:
        host = urlparse(url_match.group(1)).hostname
        return _clean_host(host)

    for sep in (" - ", " — ", " | ", " – ", " / "):
        if sep in title:
            parts = [p.strip() for p in title.split(sep) if p.strip()]
            for part in reversed(parts):
                host = _maybe_host(part)
                if host:
                    return host

    token = re.search(r"\b([a-z0-9][a-z0-9.-]+\.[a-z]{2,})\b", title, re.I)
    if token:
        return _clean_host(token.group(1))

    low = title.lower()
    for needle, host in TITLE_BRAND_HINTS:
        if needle in low:
            return host
    return None


def _page_title_activity(window_title: str | None) -> str:
    """Human label from a browser tab title when no site rule matched."""
    page = clean_browser_title(window_title)
    if not page:
        return "Новая вкладка"
    low = page.lower()
    if low in _NEW_TAB_TITLES or low.startswith("new tab"):
        return "Новая вкладка"
    if len(page) > 52:
        return page[:49].rstrip(" -—|·") + "…"
    return page


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


def site_for_activity_label(label: str | None) -> str | None:
    """Best domain for a known activity label (favicon when url_hint is missing)."""
    if not label:
        return None
    target = label.strip().lower()
    for site, (_kind, site_label, _cat) in SITE_ACTIVITIES.items():
        if site_label.lower() == target:
            return site
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
    *,
    work_mode: bool = False,
    work_chat_keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve human-facing labels for a window session."""
    app = normalize_app(app_name)
    site = _clean_host(site) or extract_site_from_title(window_title, app)
    display = display_name_for_app(app)
    user_app_rules = user_app_rules or {}
    user_site_rules = user_site_rules or {}
    keywords = [k.strip().lower() for k in (work_chat_keywords or []) if str(k).strip()]

    if is_system_noise(app):
        return {
            "display_name": display,
            "activity_kind": "system",
            "activity_label": "Система",
            "category": "neutral",
            "url_hint": site,
            "hidden": True,
        }

    if is_rdp_client(app):
        host = parse_rdp_host(window_title)
        label = f"RDP · {host}" if host else "Удалёнка"
        cat: Category = "productive"
        user_override = False
        if app in user_app_rules:
            cat = normalize_category(user_app_rules[app])
            user_override = True
        cat = _apply_work_context(
            cat,
            "remote",
            window_title,
            work_mode=work_mode,
            keywords=keywords,
            user_override=user_override,
        )
        return {
            "display_name": display,
            "activity_kind": "remote",
            "activity_label": label,
            "category": cat,
            "url_hint": None,
            "hidden": False,
        }

    # Site-driven activity (especially browsers)
    matched = _match_site_activity(site)
    if matched:
        kind, label, cat = matched
        user_override = False
        if site and site in user_site_rules:
            cat = normalize_category(user_site_rules[site])
            user_override = True
        elif site:
            for key, ucat in user_site_rules.items():
                if site == key or site.endswith("." + key):
                    cat = normalize_category(ucat)
                    user_override = True
                    break
        cat = _apply_work_context(
            cat,
            kind,
            window_title,
            work_mode=work_mode,
            keywords=keywords,
            user_override=user_override,
        )
        return {
            "display_name": display,
            "activity_kind": kind,
            "activity_label": label,
            "category": cat,
            "url_hint": site,
            "hidden": False,
        }

    if is_browser(app):
        # Unknown site — never dump everything into a single "Браузер" bucket
        cat: Category = "unrated"
        user_override = False
        if app in user_app_rules:
            cat = normalize_category(user_app_rules[app])
            user_override = True
        elif site and site in DEFAULT_SITE_RULES:
            cat = DEFAULT_SITE_RULES[site]
        if site:
            label = site
            kind: ActivityKind = "other"
        else:
            label = _page_title_activity(window_title)
            kind = "other"
        cat = _apply_work_context(
            cat,
            kind,
            window_title,
            work_mode=work_mode,
            keywords=keywords,
            user_override=user_override,
        )
        return {
            "display_name": display,
            "activity_kind": kind,
            "activity_label": label,
            "category": cat,
            "url_hint": site,
            "hidden": False,
        }

    # Desktop apps
    if app in APP_ACTIVITY_DEFAULTS:
        kind, label = APP_ACTIVITY_DEFAULTS[app]
    else:
        kind, label = "other", display

    cat = "unrated"
    user_override = False
    if app in user_app_rules:
        cat = normalize_category(user_app_rules[app])
        user_override = True
    elif app in DEFAULT_APP_RULES:
        cat = DEFAULT_APP_RULES[app]
    elif kind in {"messaging", "video", "social"}:
        cat = "distracting" if kind != "messaging" else "neutral"
    elif kind in {"work", "email", "remote"}:
        cat = "productive"

    cat = _apply_work_context(
        cat,
        kind,
        window_title,
        work_mode=work_mode,
        keywords=keywords,
        user_override=user_override,
    )

    return {
        "display_name": display,
        "activity_kind": kind,
        "activity_label": label,
        "category": cat,
        "url_hint": site,
        "hidden": False,
    }


def _apply_work_context(
    cat: Category,
    kind: ActivityKind,
    window_title: str | None,
    *,
    work_mode: bool,
    keywords: list[str],
    user_override: bool,
) -> Category:
    if user_override:
        return cat
    title = (window_title or "").lower()
    if keywords and any(k in title for k in keywords):
        return "productive"
    if work_mode and kind == "messaging":
        return "productive"
    return cat
