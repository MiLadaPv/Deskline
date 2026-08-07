"""Calls, meetings & mail heuristics: foreground time in known apps/sites.
Deskline tracks window focus, not true call-join state. Reports are labeled accordingly.
"""

from __future__ import annotations
import re
from typing import Any
from deskline.classify import SITE_ACTIVITIES, clean_browser_title
# Desktop executables where calls/meetings are primary (also used for longer idle).
MEETING_APP_EXES: frozenset[str] = frozenset(
    {
        "teams.exe",
        "ms-teams.exe",
        "zoom.exe",
        "skype.exe",
        "webex.exe",
        "ciscowebexstart.exe",
        "slack.exe",
        "discord.exe",  # voice / huddles - counted as meeting app
    }
)
# Browser hosts that are meeting / call products (incl. RU: Telemost, Yandex Messenger).
MEETING_SITE_HOSTS: frozenset[str] = frozenset(
    {
        "zoom.us",
        "meet.google.com",
        "teams.microsoft.com",
        "teams.live.com",
        "webex.com",
        "discord.com",
        "telemost.yandex.ru",
        "messenger.yandex.ru",
        "web.skype.com",
    }
)
MEETING_APP_LABELS: dict[str, str] = {
    "teams.exe": "Microsoft Teams",
    "ms-teams.exe": "Microsoft Teams",
    "zoom.exe": "Zoom",
    "skype.exe": "Skype",
    "webex.exe": "Webex",
    "ciscowebexstart.exe": "Webex",
    "slack.exe": "Slack",
    "discord.exe": "Discord",
}
MEETING_SITE_LABELS: dict[str, str] = {
    "telemost.yandex.ru": "Яндекс Телемост",
    "messenger.yandex.ru": "Яндекс Мессенджер",
    "meet.google.com": "Google Meet",
    "zoom.us": "Zoom",
    "teams.microsoft.com": "Microsoft Teams",
    "teams.live.com": "Microsoft Teams",
    "webex.com": "Webex",
    "discord.com": "Discord",
    "web.skype.com": "Skype",
}
EMAIL_APP_EXES: frozenset[str] = frozenset(
    {
        "outlook.exe",
        "hxoutlook.exe",
        "olk.exe",
        "mail.exe",
    }
)
EMAIL_SITE_HOSTS: frozenset[str] = frozenset(
    {
        "mail.yandex.ru",
        "gmail.com",
        "mail.google.com",
        "mail.ru",
        "outlook.live.com",
        "outlook.office.com",
    }
)
_MEETING_TITLE_RE = re.compile(
    r"телемост|telemost|яндекс\s*мессенджер|yandex\s*messenger|"
    r"google\s*meet|\bzoom\b|microsoft\s*teams|\bwebex\b",
    re.IGNORECASE,
)
_BRAND_PREFIX_RE = re.compile(
    r"^(?:"
    r"яндекс\s*мессенджер|yandex\s*messenger|"
    r"яндекс\s*телемост|yandex\s*telemost|телемост|telemost|"
    r"google\s*meet|zoom(?:\s*meeting)?|microsoft\s*teams|teams|webex|discord|skype"
    r")\s*[—\-–|·:]*\s*",
    re.IGNORECASE,
)
_NOISE_DETAIL = re.compile(
    r"^(?:"
    r"нов\w*\s+сообщени\w*|"
    r"unread(?:\s+messages?)?|"
    r"непрочитанн\w*|"
    r"входящие|inbox|sent|черновики|drafts|"
    r"создать\s+видеовстречу|бесплатные\s+видеовстречи.*"
    r")$",
    re.IGNORECASE,
)

def normalize_app_exe(app_name: str | None) -> str:
    raw = str(app_name or "").strip().casefold()
    if not raw:
        return ""
    if "\\" in raw or "/" in raw:
        raw = raw.replace("\\", "/").rsplit("/", 1)[-1]
    return raw

def normalize_site_host(site: str | None) -> str:
    host = str(site or "").strip().casefold()
    if host.startswith("www."):
        host = host[4:]
    return host

def is_meeting_app(app_name: str | None) -> bool:
    return normalize_app_exe(app_name) in MEETING_APP_EXES

def is_meeting_site(site: str | None) -> bool:
    host = normalize_site_host(site)
    if not host:
        return False
    if host in MEETING_SITE_HOSTS:
        return True
    return any(host == h or host.endswith("." + h) for h in MEETING_SITE_HOSTS)

def is_email_app(app_name: str | None) -> bool:
    return normalize_app_exe(app_name) in EMAIL_APP_EXES

def is_email_site(site: str | None) -> bool:
    host = normalize_site_host(site)
    if not host:
        return False
    if host in EMAIL_SITE_HOSTS:
        return True
    return any(host == h or host.endswith("." + h) for h in EMAIL_SITE_HOSTS)

def meeting_app_label(app_name: str | None, fallback: str | None = None) -> str:
    key = normalize_app_exe(app_name)
    if key in MEETING_APP_LABELS:
        return MEETING_APP_LABELS[key]
    name = str(fallback or "").strip()
    if name:
        return name
    if key.endswith(".exe"):
        return key[:-4].capitalize()
    return key or "Приложение"

def meeting_site_label(site: str | None, fallback: str | None = None) -> str:
    host = normalize_site_host(site)
    if host in MEETING_SITE_LABELS:
        return MEETING_SITE_LABELS[host]
    if host in SITE_ACTIVITIES:
        return SITE_ACTIVITIES[host][1]
    for key, (_kind, label, _cat) in SITE_ACTIVITIES.items():
        if host == key or host.endswith("." + key):
            return label
    name = str(fallback or "").strip()
    return name or host or "Сайт"

def email_channel_label(site: str | None, app: str | None = None, fallback: str | None = None) -> str:
    host = normalize_site_host(site)
    if host in SITE_ACTIVITIES:
        return SITE_ACTIVITIES[host][1]
    for key, (_kind, label, _cat) in SITE_ACTIVITIES.items():
        if host == key or host.endswith("." + key):
            return label
    exe = normalize_app_exe(app)
    if exe in {"outlook.exe", "hxoutlook.exe", "olk.exe"}:
        return "Outlook"
    name = str(fallback or "").strip()
    return name or host or exe or "Почта"

def infer_meeting_site(
    *,
    site: str | None = None,
    activity_label: str | None = None,
    window_title: str | None = None,
) -> str | None:
    """Resolve meeting host even when historical rows lack url_hint."""
    host = normalize_site_host(site)
    if is_meeting_site(host):
        return host
    blob = f"{activity_label or ''} {window_title or ''}".casefold().replace("\xa0", " ")
    if "телемост" in blob or "telemost" in blob:
        return "telemost.yandex.ru"
    if "яндекс мессенджер" in blob or "yandex messenger" in blob:
        return "messenger.yandex.ru"
    if "meet.google" in blob or "google meet" in blob:
        return "meet.google.com"
    if re.search(r"\bzoom\b", blob):
        return "zoom.us"
    if "microsoft teams" in blob or re.search(r"\bteams\b", blob):
        return "teams.microsoft.com"
    return None

def is_meeting_activity(
    *,
    app_name: str | None = None,
    site: str | None = None,
    activity_label: str | None = None,
    window_title: str | None = None,
) -> bool:
    if is_meeting_app(app_name):
        return True
    if infer_meeting_site(site=site, activity_label=activity_label, window_title=window_title):
        return True
    blob = f"{activity_label or ''} {window_title or ''}"
    return bool(_MEETING_TITLE_RE.search(blob.replace("\xa0", " ")))

def is_email_activity(
    *,
    app_name: str | None = None,
    site: str | None = None,
    activity_kind: str | None = None,
    activity_label: str | None = None,
) -> bool:
    if str(activity_kind or "").strip().lower() == "email":
        return True
    if is_email_app(app_name) or is_email_site(site):
        return True
    label = str(activity_label or "").casefold()
    return any(tok in label for tok in ("почта", "gmail", "outlook", "mail.ru"))

def meeting_context_from_title(
    window_title: str | None,
    *,
    site: str | None = None,
    activity_label: str | None = None,
) -> str | None:
    """Best-effort 'with whom / about what' from the window title (may be empty)."""
    cleaned = clean_browser_title(window_title)
    if not cleaned:
        return None
    text = cleaned.replace("\xa0", " ").strip()
    text = _BRAND_PREFIX_RE.sub("", text).strip(" -—|·:•")
    if not text:
        return None
    if _NOISE_DETAIL.match(text):
        return None
    # Drop leftover unread counters mid-string
    text = re.sub(
        r"\b\d+\s+(?:нов\w*\s+сообщен\w*|unread(?:\s+messages?)?)\b",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" -—|·:•")
    if not text or len(text) < 2:
        return None
    brand = (activity_label or meeting_site_label(site) or "").casefold()
    if brand and text.casefold() == brand:
        return None
    if len(text) > 72:
        return text[:69].rstrip(" -—|·") + "…"
    return text

def build_meetings_report(
    *,
    by_app: list[dict[str, Any]],
    by_site: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
    email_channels: list[dict[str, Any]] | None = None,
    email_sessions: list[dict[str, Any]] | None = None,
    total_tracked_sec: float = 0.0,
) -> dict[str, Any]:
    """Filter summary/timeline payloads into a meetings (+ mail) report."""
    apps_out: list[dict[str, Any]] = []
    for row in by_app or []:
        app = row.get("app_name") or row.get("name")
        if not is_meeting_app(app):
            continue
        sec = float(row.get("sec") or 0)
        if sec < 1:
            continue
        apps_out.append(
            {
                "key": normalize_app_exe(app),
                "name": meeting_app_label(app, row.get("name") or row.get("display_name")),
                "app_name": normalize_app_exe(app),
                "sec": round(sec, 1),
                "icon_url": row.get("icon_url"),
                "source": "app",
            }
        )
    sites_out: list[dict[str, Any]] = []
    for row in by_site or []:
        site = row.get("site") or row.get("name")
        host = normalize_site_host(site)
        if not is_meeting_site(host):
            continue
        sec = float(row.get("sec") or 0)
        if sec < 1:
            continue
        sites_out.append(
            {
                "key": f"site:{host}",
                "name": meeting_site_label(host, row.get("display_name") or row.get("name")),
                "site": host,
                "sec": round(sec, 1),
                "icon_url": row.get("icon_url"),
                "source": "site",
            }
        )
    combined = apps_out + sites_out
    combined.sort(key=lambda r: r["sec"], reverse=True)
    total_sec = round(sum(r["sec"] for r in combined), 1)
    sess_out: list[dict[str, Any]] = []
    for row in sessions or []:
        app = row.get("app_name")
        site = row.get("site")
        label = row.get("name") or row.get("display_name") or row.get("activity_label")
        title = row.get("window_title")
        if not is_meeting_activity(
            app_name=app, site=site, activity_label=label, window_title=title
        ):
            continue
        inferred = infer_meeting_site(site=site, activity_label=label, window_title=title)
        detail = meeting_context_from_title(title, site=inferred or site, activity_label=label)
        sess_out.append(
            {
                "started_at": row.get("started_at"),
                "ended_at": row.get("ended_at"),
                "sec": row.get("sec"),
                "idle_sec": row.get("idle_sec"),
                "name": label,
                "app_name": row.get("app_name"),
                "display_name": row.get("display_name"),
                "site": inferred or site,
                "category": row.get("category"),
                "icon_url": row.get("icon_url"),
                "window_title": title,
                "detail": detail,
                "has_detail": bool(detail),
            }
        )
    sess_out.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)
    email_out = list(email_channels or [])
    email_out.sort(key=lambda r: float(r.get("sec") or 0), reverse=True)
    email_total = round(sum(float(r.get("sec") or 0) for r in email_out), 1)
    email_sess = list(email_sessions or [])
    email_sess.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)
    share = 0.0
    tracked = float(total_tracked_sec or 0)
    if tracked > 0 and total_sec > 0:
        share = round(min(100.0, (total_sec / tracked) * 100.0), 1)
    return {
        "total_sec": total_sec,
        "share_pct": share,
        "tracked_sec": round(tracked, 1),
        "by_app": apps_out,
        "by_site": sites_out,
        "top": combined[:12],
        "sessions": sess_out[:50],
        "email_total_sec": email_total,
        "email_top": email_out[:12],
        "email_sessions": email_sess[:40],
        "note": (
            "Учитывается время в фокусе окна: Телемост, Яндекс Мессенджер, Teams, Zoom, Meet… "
            "и отдельно почта. Это не факт «в звонке», а активное окно. "
            "«Развернуть» показывает контекст из заголовка окна, если он есть."
        ),
    }
