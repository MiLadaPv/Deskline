"""Calls & meetings heuristics: foreground time in known meeting apps/sites.

Deskline tracks window focus, not true call-join state. Reports are labeled accordingly.
"""

from __future__ import annotations

from typing import Any

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
        "discord.exe",  # voice / huddles — counted as meeting app
    }
)

# Browser hosts that are meeting products (not general chat like Telegram web).
MEETING_SITE_HOSTS: frozenset[str] = frozenset(
    {
        "zoom.us",
        "meet.google.com",
        "teams.microsoft.com",
        "teams.live.com",
        "webex.com",
        "discord.com",
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


def normalize_app_exe(app_name: str | None) -> str:
    raw = str(app_name or "").strip().casefold()
    if not raw:
        return ""
    # paths → basename
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


def build_meetings_report(
    *,
    by_app: list[dict[str, Any]],
    by_site: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
    total_tracked_sec: float = 0.0,
) -> dict[str, Any]:
    """Filter summary/timeline payloads into a meetings report."""
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
        site = row.get("name") or row.get("site")
        if not is_meeting_site(site):
            continue
        sec = float(row.get("sec") or 0)
        if sec < 1:
            continue
        host = normalize_site_host(site)
        sites_out.append(
            {
                "key": f"site:{host}",
                "name": host,
                "site": host,
                "sec": round(sec, 1),
                "icon_url": row.get("icon_url"),
                "source": "site",
            }
        )

    # Merge same brand from app+site for top list (keep separate sources in detail)
    combined = apps_out + sites_out
    combined.sort(key=lambda r: r["sec"], reverse=True)
    total_sec = round(sum(r["sec"] for r in combined), 1)

    sess_out: list[dict[str, Any]] = []
    for row in sessions or []:
        app = row.get("app_name")
        site = row.get("site")
        if not (is_meeting_app(app) or is_meeting_site(site)):
            continue
        sess_out.append(
            {
                "started_at": row.get("started_at"),
                "ended_at": row.get("ended_at"),
                "sec": row.get("sec"),
                "idle_sec": row.get("idle_sec"),
                "name": row.get("name") or row.get("display_name"),
                "app_name": row.get("app_name"),
                "display_name": row.get("display_name"),
                "site": row.get("site"),
                "category": row.get("category"),
                "icon_url": row.get("icon_url"),
            }
        )
    sess_out.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)

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
        "sessions": sess_out[:40],
        "note": (
            "Учитывается время в фокусе окна приложений и сайтов для звонков/встреч "
            "(Teams, Zoom, Meet, Slack, Discord…). Это не факт «в звонке», а активное окно."
        ),
    }
