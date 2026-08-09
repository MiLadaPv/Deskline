"""Calls, meetings & mail heuristics.

Foreground focus still drives the day timeline. For the Calls panel we also
count *background call presence*: while a desktop meeting window stays open
(e.g. Zoom Meeting), multitasking in the browser still counts as being on the call.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from deskline.classify import SITE_ACTIVITIES

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
# Browser hosts that are meeting / call products (not chat-first messengers).
MEETING_SITE_HOSTS: frozenset[str] = frozenset(
    {
        "zoom.us",
        "meet.google.com",
        "teams.microsoft.com",
        "teams.live.com",
        "webex.com",
        "telemost.yandex.ru",
    }
)
# Chat products that look like "calls" only when the title shows a real call/huddle.
CHAT_SITE_HOSTS: frozenset[str] = frozenset(
    {
        "messenger.yandex.ru",
        "discord.com",
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
    r"телемост|telemost|"
    r"google\s*meet|\bzoom\b|microsoft\s*teams|\bwebex\b",
    re.IGNORECASE,
)
_CALL_SIGNAL_RE = re.compile(
    r"звонок|видеозвонок|видео\s*встреч|в\s+звонке|в\s+встрече|"
    r"call\s+with|in\s+a\s+call|joining\s+call|huddle|voice\s+channel|"
    r"meeting\s+with|screen\s+shar",
    re.IGNORECASE,
)
# Desktop meeting UI that can stay open while the user focuses another app.
_ZOOM_IN_CALL_CLASS_RE = re.compile(
    r"Conf(?:Video|Content|Chat)|ZPContent|VideoFrame|CptHost|ppt_presentation|"
    r"Zoom(?:Meeting|Content)|zVideoUI",
    re.IGNORECASE,
)
_IN_CALL_TITLE_RE = re.compile(
    r"zoom\s+meeting|zoom\s+webinar|meeting\s+id|"
    r"microsoft\s+teams.*(?:meeting|call)|meeting\s+compact|"
    r"webex\s+meeting|\bhuddle\b|"
    r"ид[её]т\s+встреч|конференци",
    re.IGNORECASE,
)
_ZOOM_HOME_TITLE_RE = re.compile(
    r"^(?:zoom(?:\s+workplace)?|zoom\s+cloud\s+meetings|zoom\s+-\s+settings|"
    r"settings|sign\s*in|login)\s*$",
    re.IGNORECASE,
)
_CHAT_BRAND_RE = re.compile(
    r"яндекс\s*мессенджер|yandex\s*messenger|\bdiscord\b|\bskype\b",
    re.IGNORECASE,
)
_BRAND_PREFIX_RE = re.compile(
    r"^(?:"
    r"(?:звонок\s+(?:в\s+)?)?(?:яндекс\s*)?телемост\w*|"
    r"яндекс\s*мессенджер|yandex\s*messenger|"
    r"yandex\s*telemost\w*|telemost\w*|"
    r"google\s*meet|"
    r"zoom(?:\s+meeting)?(?:\s+with)?|"
    r"microsoft\s*teams|teams|webex|discord|skype"
    r")\s*[—\-–|·:]*\s*",
    re.IGNORECASE,
)
_NOISE_DETAIL = re.compile(
    r"^(?:"
    r"нов\w*\s+сообщени\w*|"
    r"unread(?:\s+messages?)?|"
    r"непрочитанн\w*|"
    r"входящие|inbox|sent|черновики|drafts|"
    r"создать\s+(?:видео)?встреч\w*|"
    r"бесплатные\s+видеовстречи.*"
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

def is_chat_site(site: str | None) -> bool:
    host = normalize_site_host(site)
    if not host:
        return False
    if host in CHAT_SITE_HOSTS:
        return True
    return any(host == h or host.endswith("." + h) for h in CHAT_SITE_HOSTS)


def title_suggests_call(activity_label: str | None = None, window_title: str | None = None) -> bool:
    blob = f"{activity_label or ''} {window_title or ''}".replace("\xa0", " ")
    return bool(_CALL_SIGNAL_RE.search(blob))


def window_looks_like_active_call(
    *,
    app_name: str | None = None,
    window_title: str | None = None,
    class_name: str | None = None,
) -> bool:
    """True when a desktop meeting *call UI* is open (may be unfocused)."""
    exe = normalize_app_exe(app_name)
    if exe not in MEETING_APP_EXES:
        return False
    title = str(window_title or "").replace("\xa0", " ").strip()
    cls = str(class_name or "").strip()

    if exe == "zoom.exe":
        if _ZOOM_IN_CALL_CLASS_RE.search(cls):
            return True
        if _ZOOM_HOME_TITLE_RE.match(title):
            return False
        if _IN_CALL_TITLE_RE.search(title) or title_suggests_call(window_title=title):
            return True
        # Topic-named meeting windows often drop the word "Zoom Meeting".
        if title and not re.search(r"settings|sign\s*in|login|workplace", title, re.I):
            cleaned = re.sub(r"\bzoom\b", "", title, flags=re.I).strip(" -—–|·:")
            return len(cleaned) >= 2
        return False

    if exe in {"teams.exe", "ms-teams.exe"}:
        if _IN_CALL_TITLE_RE.search(title) or title_suggests_call(window_title=title):
            return True
        if re.search(r"\bmeeting\b|\bcall\b|встреч|звонок", title, re.I):
            return True
        # Named call/meeting windows often look like "Topic | Microsoft Teams".
        if re.search(r"\|\s*microsoft\s+teams\s*$", title, re.I):
            left = re.split(r"\|", title, maxsplit=1)[0].strip()
            if left and not re.match(
                r"^(chat|activity|calendar|teams|calls|сообщени|календар|активност)",
                left,
                re.I,
            ):
                return True
        return False

    if exe in {"slack.exe", "discord.exe", "skype.exe"}:
        return title_suggests_call(window_title=title) or bool(
            re.search(r"\bhuddle\b|voice\s+channel|in\s+a\s+call", title, re.I)
        )

    if exe in {"webex.exe", "ciscowebexstart.exe"}:
        return bool(_IN_CALL_TITLE_RE.search(title) or title_suggests_call(window_title=title))

    return bool(_IN_CALL_TITLE_RE.search(title) or title_suggests_call(window_title=title))


def find_background_call_presence(*, foreground_pid: int | None = None):
    """Return one open in-call window that is not the current foreground PID."""
    from deskline.windows import WindowInfo, iter_top_level_windows

    best: WindowInfo | None = None
    best_rank = 99
    for win in iter_top_level_windows(visible_only=True):
        if foreground_pid and int(win.pid) == int(foreground_pid):
            continue
        if not window_looks_like_active_call(
            app_name=win.app_name,
            window_title=win.window_title,
            class_name=win.class_name,
        ):
            continue
        # Prefer Zoom/Teams over chat clients when several match.
        exe = normalize_app_exe(win.app_name)
        rank = 0 if exe in {"zoom.exe", "teams.exe", "ms-teams.exe", "webex.exe"} else 1
        if best is None or rank < best_rank:
            best = win
            best_rank = rank
    return best


def is_meeting_activity(
    *,
    app_name: str | None = None,
    site: str | None = None,
    activity_label: str | None = None,
    window_title: str | None = None,
) -> bool:
    """True for real meeting/call surfaces — not passive messenger chat browsing."""
    if is_meeting_app(app_name):
        return True
    host = normalize_site_host(site) or infer_meeting_site(
        site=site, activity_label=activity_label, window_title=window_title
    )
    blob = f"{activity_label or ''} {window_title or ''}".replace("\xa0", " ")
    if host and is_chat_site(host):
        return title_suggests_call(activity_label=activity_label, window_title=window_title)
    if host and is_meeting_site(host):
        return True
    # Chat brand in title without a call signal stays out of the Calls panel.
    if _CHAT_BRAND_RE.search(blob) and not title_suggests_call(
        activity_label=activity_label, window_title=window_title
    ):
        return False
    return bool(_MEETING_TITLE_RE.search(blob))

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

_PAGES_RE = re.compile(
    r"\s*(?:и еще\s+)?\d+\s+страниц\w*\b",
    re.IGNORECASE,
)
_UNREAD_RE = re.compile(
    r"\s*[—\-–|·:]*\s*\d+\s+"
    r"(?:"
    r"нов\w*\s+сообщени\w*"
    r"|unread(?:\s+messages?)?"
    r"|непрочитанн\w*"
    r")\b",
    re.IGNORECASE,
)
_GROUP_SPLIT_RE = re.compile(r"\s*(?:,|;|/|·|\||\bи\b)\s*", re.IGNORECASE)


def meeting_peers_from_title(
    window_title: str | None,
    *,
    site: str | None = None,
    activity_label: str | None = None,
) -> list[str]:
    """Extract chat/call counterpart names from a window title (best-effort).

    Edge often does NOT put Yandex Messenger peer names in the title — only unread
    counters. Telemost / Zoom / Teams titles frequently do include names.
    """
    from deskline.classify import _BROWSER_APP_TAIL, _BROWSER_EXTRA_PAGES

    title = (window_title or "").replace("\u200b", "").replace("\xa0", " ").strip()
    if not title:
        return []
    title = _BROWSER_EXTRA_PAGES.sub("", title)
    title = _BROWSER_APP_TAIL.sub("", title)
    title = re.sub(r"\s*[—\-–|]\s*microsoft\s*teams\s*$", "", title, flags=re.IGNORECASE)
    title = _PAGES_RE.sub("", title)
    title = _UNREAD_RE.sub("", title)
    title = re.sub(r"\s+[—\-–|]\s*$", "", title).strip(" -—|·:•")
    title = _BRAND_PREFIX_RE.sub("", title).strip(" -—|·:•")
    title = re.sub(r"(?:^|\s)—?\s*яндекс\s*:.*$", "", title, flags=re.IGNORECASE).strip(" -—|·:•")
    title = re.sub(r"^яндекс\s*:\s*", "", title, flags=re.IGNORECASE).strip(" -—|·:•")
    if not title or len(title) < 2:
        return []
    if _NOISE_DETAIL.match(title):
        return []
    brand = (activity_label or meeting_site_label(site) or "").casefold()
    if brand and title.casefold() == brand:
        return []
    parts = [p.strip(" -—|·:•") for p in _GROUP_SPLIT_RE.split(title) if p and p.strip()]
    peers: list[str] = []
    for part in parts or [title]:
        if len(part) < 2 or _NOISE_DETAIL.match(part):
            continue
        part = re.sub(r"^(?:with|с|со)\s+", "", part, flags=re.IGNORECASE).strip()
        if brand and part.casefold() == brand:
            continue
        if len(part) > 64:
            part = part[:61].rstrip(" -—|·") + "…"
        if part not in peers:
            peers.append(part)
    return peers[:8]


def meeting_context_from_title(
    window_title: str | None,
    *,
    site: str | None = None,
    activity_label: str | None = None,
) -> str | None:
    """Best-effort 'with whom / about what' from the window title (may be empty)."""
    peers = meeting_peers_from_title(
        window_title, site=site, activity_label=activity_label
    )
    if not peers:
        return None
    return peers[0] if len(peers) == 1 else ", ".join(peers)


def is_group_meeting_title(window_title: str | None) -> bool:
    peers = meeting_peers_from_title(window_title)
    if len(peers) >= 2:
        return True
    blob = (window_title or "").casefold()
    return any(tok in blob for tok in ("групп", "group", "команд", "team meeting", "standup"))


def attach_peers_to_channels(
    channels: list[dict[str, Any]], sessions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Roll session peer details up onto channel rows for expandable «С кем»."""
    buckets: dict[str, dict[str, dict[str, Any]]] = {}
    for sess in sessions or []:
        site = normalize_site_host(sess.get("site"))
        app = normalize_app_exe(sess.get("app_name"))
        channel_key = f"site:{site}" if site else f"app:{app}"
        peers = list(sess.get("peers") or [])
        if not peers and sess.get("detail"):
            peers = [str(sess["detail"])]
        if not peers:
            peers = meeting_peers_from_title(
                sess.get("window_title"),
                site=site,
                activity_label=sess.get("name") or sess.get("display_name"),
            )
        if not peers:
            continue
        sec = float(sess.get("sec") or 0)
        kind = (
            "group"
            if len(peers) >= 2 or is_group_meeting_title(sess.get("window_title"))
            else "dm"
        )
        label = ", ".join(peers) if kind == "group" else peers[0]
        channel_bucket = buckets.setdefault(channel_key, {})
        slot = channel_bucket.setdefault(
            label.casefold(),
            {"name": label, "sec": 0.0, "kind": kind, "parts": 0},
        )
        slot["sec"] = round(float(slot["sec"]) + sec, 1)
        slot["parts"] = int(slot["parts"]) + 1
        if kind == "group":
            slot["kind"] = "group"

    out: list[dict[str, Any]] = []
    for ch in channels:
        row = dict(ch)
        key = str(row.get("key") or "")
        peer_map = buckets.get(key) or {}
        peers = sorted(peer_map.values(), key=lambda r: float(r["sec"]), reverse=True)
        row["peers"] = peers[:12]
        row["peers_sec"] = round(sum(float(p["sec"]) for p in peers), 1)
        row["has_peers"] = bool(peers)
        if key.startswith("site:messenger.yandex.ru") and not peers:
            row["peers_hint"] = (
                "В заголовке Edge обычно нет имени чата. Можно распознать собеседника "
                "по скриншоту Deskline (нужен API-ключ Vision в настройках)."
            )
        elif not peers:
            row["peers_hint"] = (
                "В заголовке окна не было имён. Для Zoom/Teams/Телемоста имена "
                "появятся, если их показывает сам заголовок — или распознайте со скрина."
            )
        else:
            row["peers_hint"] = None
        out.append(row)
    return out


def _session_channel_key(row: dict[str, Any]) -> tuple[str, str]:
    site = normalize_site_host(row.get("site"))
    name = str(row.get("name") or row.get("display_name") or "").strip().casefold()
    app = normalize_app_exe(row.get("app_name"))
    return (site or name or app, app)


def _parse_iso_ts(value: Any) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def compact_meeting_sessions(
    items: list[dict[str, Any]],
    *,
    min_sec: float = 60.0,
    max_gap_sec: float = 180.0,
) -> list[dict[str, Any]]:
    """Collapse short window flickers so Calls → Recent windows stays readable."""
    if not items:
        return []
    chrono = sorted(items, key=lambda r: str(r.get("started_at") or ""))
    out: list[dict[str, Any]] = []
    for raw in chrono:
        cur = dict(raw)
        cur["sec"] = float(cur.get("sec") or 0)
        cur["parts"] = int(cur.get("parts") or 1)
        if out:
            prev = out[-1]
            same = _session_channel_key(prev) == _session_channel_key(cur)
            pe = _parse_iso_ts(prev.get("ended_at"))
            cs = _parse_iso_ts(cur.get("started_at"))
            gap = max(0.0, cs - pe) if pe is not None and cs is not None else 0.0
            if cur["sec"] < min_sec or (same and gap <= max_gap_sec):
                prev["ended_at"] = cur.get("ended_at") or prev.get("ended_at")
                prev["sec"] = round(float(prev["sec"]) + cur["sec"], 1)
                prev["parts"] = int(prev.get("parts") or 1) + cur["parts"]
                if not prev.get("detail") and cur.get("detail"):
                    prev["detail"] = cur["detail"]
                    prev["has_detail"] = True
                if cur.get("peers"):
                    prev["peers"] = list(
                        dict.fromkeys([*(prev.get("peers") or []), *cur["peers"]])
                    )
                continue
        out.append(cur)
    while len(out) >= 2 and float(out[0].get("sec") or 0) < min_sec:
        first = out.pop(0)
        nxt = out[0]
        nxt["started_at"] = first.get("started_at") or nxt.get("started_at")
        nxt["sec"] = round(float(nxt.get("sec") or 0) + float(first.get("sec") or 0), 1)
        nxt["parts"] = int(nxt.get("parts") or 1) + int(first.get("parts") or 1)
        if not nxt.get("detail") and first.get("detail"):
            nxt["detail"] = first["detail"]
            nxt["has_detail"] = True
    return out


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

    # Use raw (pre-compact) sessions for peer mining so short named flickers aren't lost.
    peer_source: list[dict[str, Any]] = []
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
        peers = meeting_peers_from_title(
            title, site=inferred or site, activity_label=label
        )
        detail = meeting_context_from_title(
            title, site=inferred or site, activity_label=label
        )
        item = {
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
            "peers": peers,
            "has_detail": bool(detail),
            "is_group": len(peers) >= 2 or is_group_meeting_title(title),
        }
        peer_source.append(item)
        sess_out.append(item)

    combined = attach_peers_to_channels(combined, peer_source)

    sess_out.sort(key=lambda r: str(r.get("started_at") or ""))
    sess_out = compact_meeting_sessions(sess_out, min_sec=60.0, max_gap_sec=180.0)
    sess_out.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)

    email_out = list(email_channels or [])
    email_out.sort(key=lambda r: float(r.get("sec") or 0), reverse=True)
    email_total = round(sum(float(r.get("sec") or 0) for r in email_out), 1)
    email_sess = list(email_sessions or [])
    email_sess.sort(key=lambda r: str(r.get("started_at") or ""))
    email_sess = compact_meeting_sessions(email_sess, min_sec=60.0, max_gap_sec=180.0)
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
        "sessions": sess_out[:15],
        "email_total_sec": email_total,
        "email_top": email_out[:12],
        "email_sessions": email_sess[:12],
        "note": (
            "В «Звонках» — время в Телемосте, Teams, Zoom, Meet и похожих. "
            "Если звонок в Zoom/Teams остаётся открыт, а вы переключаетесь в браузер — "
            "это время тоже считается звонком. "
            "Чаты (Яндекс Мессенджер и т.п.) сюда не входят, пока в заголовке нет признаков звонка. "
            "«С кем» берёт имена из заголовка окна; если пусто — можно распознать со скриншота."
        ),
    }
