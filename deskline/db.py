from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from deskline.capture import delete_screenshot_file
from deskline.classify import (
    display_name_for_app,
    is_browser,
    is_system_noise,
    normalize_category,
    resolve_activity,
    site_for_activity_label,
)
from deskline.config import DB_PATH, SCREENSHOTS_DIR, ensure_data_dirs
from deskline.icons import (
    ensure_app_icon,
    ensure_site_icon,
    icon_url_for_app,
    icon_url_for_site,
    resolve_icon_url,
)

MIN_DISPLAY_SEC = 60.0


def _utcnow() -> datetime:
    return datetime.now().astimezone()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def _parse(dt: str | None) -> datetime | None:
    if not dt:
        return None
    return datetime.fromisoformat(dt)


@dataclass
class SessionRow:
    id: int
    app_name: str
    window_title: str
    url_hint: str | None
    started_at: str
    ended_at: str | None
    duration_sec: float
    category: str
    display_name: str | None = None
    activity_kind: str | None = None
    activity_label: str | None = None
    app_path: str | None = None
    idle_sec: float = 0.0
    project_id: int | None = None
    task_id: int | None = None


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or DB_PATH)
        ensure_data_dirs()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_name TEXT NOT NULL,
                    window_title TEXT NOT NULL DEFAULT '',
                    url_hint TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_sec REAL NOT NULL DEFAULT 0,
                    category TEXT NOT NULL DEFAULT 'neutral',
                    display_name TEXT,
                    activity_kind TEXT,
                    activity_label TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
                CREATE INDEX IF NOT EXISTS idx_sessions_app ON sessions(app_name);

                CREATE TABLE IF NOT EXISTS screenshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    taken_at TEXT NOT NULL,
                    session_id INTEGER,
                    reason TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_shots_taken ON screenshots(taken_at);

                CREATE TABLE IF NOT EXISTS app_rules (
                    app_name TEXT PRIMARY KEY,
                    category TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS site_rules (
                    site TEXT PRIMARY KEY,
                    category TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    color TEXT NOT NULL DEFAULT '#2f6f5e',
                    archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                """
            )
            cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
            for col, decl in (
                ("display_name", "TEXT"),
                ("activity_kind", "TEXT"),
                ("activity_label", "TEXT"),
                ("app_path", "TEXT"),
                ("idle_sec", "REAL NOT NULL DEFAULT 0"),
                ("project_id", "INTEGER"),
                ("task_id", "INTEGER"),
            ):
                if col not in cols:
                    conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {decl}")

    def get_app_rules(self) -> dict[str, str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT app_name, category FROM app_rules").fetchall()
        return {r["app_name"]: r["category"] for r in rows}

    def get_site_rules(self) -> dict[str, str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT site, category FROM site_rules").fetchall()
        return {r["site"]: r["category"] for r in rows}

    def set_app_rule(self, app_name: str, category: str) -> None:
        category = normalize_category(category)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO app_rules(app_name, category) VALUES(?, ?)
                ON CONFLICT(app_name) DO UPDATE SET category=excluded.category
                """,
                (app_name.lower(), category),
            )

    def set_site_rule(self, site: str, category: str) -> None:
        category = normalize_category(category)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO site_rules(site, category) VALUES(?, ?)
                ON CONFLICT(site) DO UPDATE SET category=excluded.category
                """,
                (site.lower(), category),
            )

    def delete_app_rule(self, app_name: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM app_rules WHERE app_name=?", (app_name.lower(),))

    def delete_site_rule(self, site: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM site_rules WHERE site=?", (site.lower(),))

    def start_session(
        self,
        app_name: str,
        window_title: str,
        url_hint: str | None,
        category: str,
        started_at: datetime | None = None,
        display_name: str | None = None,
        activity_kind: str | None = None,
        activity_label: str | None = None,
        app_path: str | None = None,
        project_id: int | None = None,
        task_id: int | None = None,
    ) -> int:
        started = started_at or _utcnow()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO sessions(
                    app_name, window_title, url_hint, started_at, category,
                    display_name, activity_kind, activity_label, app_path,
                    project_id, task_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    app_name,
                    window_title or "",
                    url_hint,
                    _iso(started),
                    category,
                    display_name,
                    activity_kind,
                    activity_label,
                    app_path,
                    project_id,
                    task_id,
                ),
            )
            return int(cur.lastrowid)

    def end_session(self, session_id: int, ended_at: datetime | None = None) -> None:
        ended = ended_at or _utcnow()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT started_at FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            if not row:
                return
            started = _parse(row["started_at"])
            duration = max(0.0, (ended - started).total_seconds()) if started else 0.0
            conn.execute(
                "UPDATE sessions SET ended_at=?, duration_sec=? WHERE id=?",
                (_iso(ended), duration, session_id),
            )

    def add_screenshot(
        self, path: str, reason: str, session_id: int | None, taken_at: datetime | None = None
    ) -> int:
        taken = taken_at or _utcnow()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO screenshots(path, taken_at, session_id, reason)
                VALUES (?, ?, ?, ?)
                """,
                (path, _iso(taken), session_id, reason),
            )
            return int(cur.lastrowid)

    def open_session(self) -> SessionRow | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return self._session(row) if row else None

    def _session(self, row: sqlite3.Row) -> SessionRow:
        keys = row.keys()
        return SessionRow(
            id=row["id"],
            app_name=row["app_name"],
            window_title=row["window_title"],
            url_hint=row["url_hint"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            duration_sec=float(row["duration_sec"] or 0),
            category=row["category"],
            display_name=row["display_name"] if "display_name" in keys else None,
            activity_kind=row["activity_kind"] if "activity_kind" in keys else None,
            activity_label=row["activity_label"] if "activity_label" in keys else None,
            app_path=row["app_path"] if "app_path" in keys else None,
            idle_sec=float(row["idle_sec"] or 0) if "idle_sec" in keys else 0.0,
            project_id=int(row["project_id"]) if "project_id" in keys and row["project_id"] is not None else None,
            task_id=int(row["task_id"]) if "task_id" in keys and row["task_id"] is not None else None,
        )

    def add_idle_seconds(self, session_id: int, seconds: float) -> None:
        if seconds <= 0:
            return
        with self.connect() as conn:
            conn.execute(
                "UPDATE sessions SET idle_sec = COALESCE(idle_sec, 0) + ? WHERE id=?",
                (float(seconds), session_id),
            )

    def _enrich(self, row: sqlite3.Row, *, work_mode: bool = False, work_chat_keywords: list[str] | None = None) -> dict[str, Any]:
        keys = set(row.keys())
        app = row["app_name"]
        title = row["window_title"]
        site = row["url_hint"]
        display = row["display_name"] if "display_name" in keys else None
        kind = row["activity_kind"] if "activity_kind" in keys else None
        label = row["activity_label"] if "activity_label" in keys else None
        app_path = row["app_path"] if "app_path" in keys else None
        cat = row["category"]
        # Always re-resolve browsers: Edge titles rarely include domains, and old
        # rows were saved as a useless catch-all "Браузер".
        stale_browser = is_browser(app) and (not label or label in {"Браузер", "Браузер · другое"})
        if is_browser(app) or stale_browser or not display or not label or not kind:
            resolved = resolve_activity(
                app,
                title,
                site,
                work_mode=work_mode,
                work_chat_keywords=work_chat_keywords,
            )
            if is_browser(app):
                display = resolved["display_name"]
                kind = resolved["activity_kind"]
                label = resolved["activity_label"]
                cat = resolved["category"]
                site = resolved.get("url_hint") or site
            else:
                display = display or resolved["display_name"]
                kind = kind or resolved["activity_kind"]
                label = label or resolved["activity_label"]
                cat = cat or resolved["category"]
                site = site or resolved.get("url_hint")
        hidden = is_system_noise(app) or kind == "system"
        project_id = None
        task_id = None
        if "project_id" in keys and row["project_id"] is not None:
            project_id = int(row["project_id"])
        if "task_id" in keys and row["task_id"] is not None:
            task_id = int(row["task_id"])
        return {
            "app_name": app,
            "app_path": app_path,
            "display_name": display or display_name_for_app(app),
            "activity_kind": kind or "other",
            "activity_label": label or display_name_for_app(app),
            "category": cat or "neutral",
            "url_hint": site,
            "hidden": hidden,
            "project_id": project_id,
            "task_id": task_id,
        }

    def summary_for_day(self, day: date | None = None, project_id: int | None = None) -> dict[str, Any]:
        day = day or date.today()
        start = datetime.combine(day, datetime.min.time()).astimezone()
        end = start + timedelta(days=1)
        return self.summary_range(start, end, project_id=project_id)

    def daily_trends(self, days: int = 7, project_id: int | None = None) -> list[dict[str, Any]]:
        """Time Doctor–style Hours Tracked + productivity mix per day."""
        days = max(1, min(int(days), 31))
        today = date.today()
        out: list[dict[str, Any]] = []
        for i in range(days - 1, -1, -1):
            day = today - timedelta(days=i)
            s = self.summary_for_day(day, project_id=project_id)
            by_cat = s.get("by_category") or {}
            total = float(s.get("total_sec") or 0)
            productive = float(by_cat.get("productive") or 0)
            neutral = float(by_cat.get("neutral") or 0)
            distracting = float(by_cat.get("distracting") or 0)
            out.append(
                {
                    "day": day.isoformat(),
                    "total_sec": total,
                    "active_sec": float(s.get("active_sec") or 0),
                    "idle_sec": float(s.get("idle_sec") or 0),
                    "focus_sec": float(s.get("focus_sec") or 0),
                    "focus_pct": float(s.get("focus_pct") or 0),
                    "activity_pct": float(s.get("activity_pct") or 0),
                    "unproductive_pct": round((distracting / total * 100.0) if total else 0.0, 1),
                    "idle_pct": round((float(s.get("idle_sec") or 0) / total * 100.0) if total else 0.0, 1),
                    "by_category": {
                        "productive": productive,
                        "neutral": neutral,
                        "distracting": distracting,
                    },
                }
            )
        return out

    def summary_range(
        self,
        start: datetime,
        end: datetime,
        project_id: int | None = None,
    ) -> dict[str, Any]:
        from deskline.config import load_config

        cfg = load_config()
        work_mode = bool(cfg.get("work_mode"))
        keywords = list(cfg.get("work_chat_keywords") or [])

        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sessions
                WHERE started_at < ? AND (ended_at IS NULL OR ended_at >= ?)
                ORDER BY started_at
                """,
                (_iso(end), _iso(start)),
            ).fetchall()

        by_cat = {"productive": 0.0, "neutral": 0.0, "distracting": 0.0}
        by_app: dict[str, float] = {}
        by_site: dict[str, float] = {}
        by_activity: dict[str, float] = {}
        by_project: dict[int, float] = {}
        by_task: dict[int, float] = {}
        activity_kinds: dict[str, str] = {}
        app_kinds: dict[str, str] = {}
        app_exe_by_label: dict[str, str] = {}
        app_path_by_exe: dict[str, str] = {}
        activity_app_secs: dict[str, dict[str, float]] = {}
        activity_site_secs: dict[str, dict[str, float]] = {}
        by_kind: dict[str, float] = {}
        total = 0.0
        tracked = 0.0
        idle_tracked = 0.0
        now = _utcnow()

        for row in rows:
            keys = set(row.keys())
            s = _parse(row["started_at"]) or start
            e = _parse(row["ended_at"]) or now
            seg_start = max(s, start)
            seg_end = min(e, end)
            dur = max(0.0, (seg_end - seg_start).total_seconds())
            if dur <= 0:
                continue
            total += dur
            meta = self._enrich(row, work_mode=work_mode, work_chat_keywords=keywords)
            if meta["hidden"]:
                continue
            if project_id is not None and meta.get("project_id") != project_id:
                continue
            tracked += dur
            # Scale idle to the overlapping segment (TD: idle is orthogonal to category)
            full_span = max(0.0, (e - s).total_seconds()) or dur
            idle_full = float(row["idle_sec"] or 0) if "idle_sec" in keys else 0.0
            idle_full = min(max(0.0, idle_full), full_span)
            idle_part = idle_full * (dur / full_span) if full_span > 0 else 0.0
            idle_tracked += min(idle_part, dur)
            raw_cat = normalize_category(meta["category"])
            cat = "neutral" if raw_cat == "unrated" else raw_cat
            if cat not in by_cat:
                cat = "neutral"
            by_cat[cat] += dur
            app_label = meta["display_name"]
            exe = (meta["app_name"] or "unknown.exe").lower()
            by_app[app_label] = by_app.get(app_label, 0.0) + dur
            if app_label not in app_kinds:
                app_kinds[app_label] = meta["activity_kind"] or "other"
            if app_label not in app_exe_by_label:
                app_exe_by_label[app_label] = exe
            if meta.get("app_path") and exe not in app_path_by_exe:
                app_path_by_exe[exe] = meta["app_path"]
            act = meta["activity_label"]
            by_activity[act] = by_activity.get(act, 0.0) + dur
            kind = meta["activity_kind"] or "other"
            if act not in activity_kinds:
                activity_kinds[act] = kind
            bucket = activity_app_secs.setdefault(act, {})
            bucket[exe] = bucket.get(exe, 0.0) + dur
            by_kind[kind] = by_kind.get(kind, 0.0) + dur
            site = meta["url_hint"]
            if site:
                by_site[site] = by_site.get(site, 0.0) + dur
                site_bucket = activity_site_secs.setdefault(act, {})
                site_bucket[site] = site_bucket.get(site, 0.0) + dur
            pid = meta.get("project_id")
            if pid is not None:
                by_project[int(pid)] = by_project.get(int(pid), 0.0) + dur
            tid = meta.get("task_id")
            if tid is not None:
                by_task[int(tid)] = by_task.get(int(tid), 0.0) + dur

        def _top_exe(label: str) -> str:
            secs = activity_app_secs.get(label) or {}
            if not secs:
                return "unknown.exe"
            return max(secs.items(), key=lambda kv: kv[1])[0]

        def _top_site(label: str) -> str | None:
            secs = activity_site_secs.get(label) or {}
            if not secs:
                return None
            return max(secs.items(), key=lambda kv: kv[1])[0]

        def _icon_for_activity(label: str) -> str:
            site = _top_site(label) or site_for_activity_label(label)
            return resolve_icon_url(site=site, app_name=_top_exe(label))

        for exe, path in app_path_by_exe.items():
            try:
                ensure_app_icon(exe, path)
            except Exception:
                pass
        for exe in {_top_exe(a) for a in by_activity} | set(app_exe_by_label.values()):
            if exe not in app_path_by_exe:
                try:
                    # May resolve path via PATH/System32; never locks a per-app placeholder.
                    ensure_app_icon(exe, None)
                except Exception:
                    pass
        # Prefetch favicons for top sites (best-effort; UI also lazy-loads)
        for site in list(by_site.keys())[:40]:
            try:
                ensure_site_icon(site)
            except Exception:
                pass

        focus = by_cat["productive"]
        focus_pct = (focus / tracked * 100.0) if tracked else 0.0
        idle_tracked = min(idle_tracked, tracked)
        active_sec = max(0.0, tracked - idle_tracked)
        activity_pct = (active_sec / tracked * 100.0) if tracked else 0.0
        return {
            "total_sec": tracked,
            "raw_total_sec": total,
            "focus_sec": focus,
            "focus_pct": round(focus_pct, 1),
            "idle_sec": round(idle_tracked, 1),
            "active_sec": round(active_sec, 1),
            "activity_pct": round(activity_pct, 1),
            "by_category": by_cat,
            "by_kind": by_kind,
            "by_activity": sorted(
                [
                    {
                        "name": k,
                        "sec": v,
                        "kind": activity_kinds.get(k, "other"),
                        "app_name": _top_exe(k),
                        "site": _top_site(k),
                        "icon_url": _icon_for_activity(k),
                    }
                    for k, v in by_activity.items()
                    if v >= MIN_DISPLAY_SEC
                ],
                key=lambda x: x["sec"],
                reverse=True,
            ),
            "by_app": sorted(
                [
                    {
                        "name": k,
                        "sec": v,
                        "kind": app_kinds.get(k, "other"),
                        "app_name": app_exe_by_label.get(k, "unknown.exe"),
                        "icon_url": icon_url_for_app(app_exe_by_label.get(k)),
                    }
                    for k, v in by_app.items()
                    if v >= MIN_DISPLAY_SEC
                ],
                key=lambda x: x["sec"],
                reverse=True,
            ),
            "by_site": sorted(
                [
                    {
                        "name": k,
                        "sec": v,
                        "kind": "search",
                        "icon_url": resolve_icon_url(site=k, app_name="msedge.exe"),
                    }
                    for k, v in by_site.items()
                    if v >= MIN_DISPLAY_SEC
                ],
                key=lambda x: x["sec"],
                reverse=True,
            ),
            "by_project": sorted(
                [
                    {"project_id": k, "sec": v}
                    for k, v in by_project.items()
                    if v >= 1.0
                ],
                key=lambda x: x["sec"],
                reverse=True,
            ),
            "by_task": sorted(
                [
                    {"task_id": k, "sec": v}
                    for k, v in by_task.items()
                    if v >= 1.0
                ],
                key=lambda x: x["sec"],
                reverse=True,
            ),
        }

    def apps_range(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return self.summary_range(start, end)["by_app"]

    def sites_range(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return self.summary_range(start, end)["by_site"]

    def activities_range(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return self.summary_range(start, end)["by_activity"]

    def timeline_for_day(self, day: date | None = None) -> list[dict[str, Any]]:
        """Chronological session segments for a day (merged consecutive same activity)."""
        from deskline.config import load_config

        cfg = load_config()
        work_mode = bool(cfg.get("work_mode"))
        keywords = list(cfg.get("work_chat_keywords") or [])
        day = day or date.today()
        start = datetime.combine(day, datetime.min.time()).astimezone()
        end = start + timedelta(days=1)
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sessions
                WHERE started_at < ? AND (ended_at IS NULL OR ended_at >= ?)
                ORDER BY started_at
                """,
                (_iso(end), _iso(start)),
            ).fetchall()

        now = _utcnow()
        items: list[dict[str, Any]] = []
        for row in rows:
            keys = set(row.keys())
            s = _parse(row["started_at"]) or start
            e = _parse(row["ended_at"]) or now
            seg_start = max(s, start)
            seg_end = min(e, end)
            dur = max(0.0, (seg_end - seg_start).total_seconds())
            if dur < 3:
                continue
            meta = self._enrich(row, work_mode=work_mode, work_chat_keywords=keywords)
            if meta["hidden"]:
                continue
            full_span = max(0.0, (e - s).total_seconds()) or dur
            idle_full = float(row["idle_sec"] or 0) if "idle_sec" in keys else 0.0
            idle_part = min(dur, idle_full * (dur / full_span) if full_span else 0.0)
            site = meta.get("url_hint") or site_for_activity_label(meta["activity_label"])
            icon = resolve_icon_url(site=site, app_name=meta["app_name"])
            items.append(
                {
                    "started_at": _iso(seg_start),
                    "ended_at": _iso(seg_end),
                    "sec": round(dur, 1),
                    "idle_sec": round(idle_part, 1),
                    "name": meta["activity_label"],
                    "app_name": meta["app_name"],
                    "display_name": meta["display_name"],
                    "category": normalize_category(meta["category"]),
                    "site": site,
                    "project_id": meta.get("project_id"),
                    "icon_url": icon,
                }
            )
        return items

    def ratings_for_day(self, day: date | None = None) -> list[dict[str, Any]]:
        """Apps and sites seen today with effective category for the ratings editor."""
        day = day or date.today()
        start = datetime.combine(day, datetime.min.time()).astimezone()
        end = start + timedelta(days=1)
        summary = self.summary_range(start, end)
        user_apps = self.get_app_rules()
        user_sites = self.get_site_rules()
        rows: list[dict[str, Any]] = []

        for item in summary["by_app"]:
            exe = (item.get("app_name") or "").lower()
            meta = resolve_activity(exe, None, None, user_apps, user_sites)
            cat = normalize_category(meta["category"])
            rows.append(
                {
                    "kind": "app",
                    "key": exe,
                    "name": item["name"],
                    "category": cat,
                    "sec": item["sec"],
                    "icon_url": item.get("icon_url") or icon_url_for_app(exe),
                    "user_override": exe in user_apps,
                }
            )

        for item in summary["by_site"]:
            site = (item.get("name") or "").lower()
            meta = resolve_activity("msedge.exe", None, site, user_apps, user_sites)
            cat = normalize_category(meta["category"])
            rows.append(
                {
                    "kind": "site",
                    "key": site,
                    "name": site,
                    "category": cat,
                    "sec": item["sec"],
                    "icon_url": resolve_icon_url(site=site, app_name="msedge.exe"),
                    "user_override": site in user_sites,
                }
            )

        rows.sort(key=lambda r: r["sec"], reverse=True)
        return rows

    def screenshots_for_date(self, day: date | None = None) -> list[dict[str, Any]]:
        from deskline.config import load_config

        day = day or date.today()
        start = datetime.combine(day, datetime.min.time()).astimezone()
        end = start + timedelta(days=1)
        work_mode = bool(load_config().get("work_mode"))
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT sh.id, sh.path, sh.taken_at, sh.session_id, sh.reason,
                       s.category AS session_category
                FROM screenshots sh
                LEFT JOIN sessions s ON s.id = sh.session_id
                WHERE sh.taken_at >= ? AND sh.taken_at < ?
                ORDER BY sh.taken_at DESC
                """,
                (_iso(start), _iso(end)),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            cat = normalize_category(item.get("session_category") or "neutral")
            item["category"] = cat
            item["flag_distracting"] = bool(work_mode and cat == "distracting")
            out.append(item)
        return out

    def purge_old_screenshots(self, retention_days: int) -> dict[str, int]:
        """Delete screenshot files and DB rows older than retention_days. 0 = keep forever."""
        if retention_days <= 0:
            return {"deleted_rows": 0, "deleted_files": 0}

        cutoff = _utcnow() - timedelta(days=int(retention_days))
        deleted_rows = 0
        deleted_files = 0

        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, path FROM screenshots WHERE taken_at < ?",
                (_iso(cutoff),),
            ).fetchall()
            for row in rows:
                if delete_screenshot_file(row["path"]):
                    deleted_files += 1
                conn.execute("DELETE FROM screenshots WHERE id = ?", (row["id"],))
                deleted_rows += 1

        ensure_data_dirs()
        cutoff_ts = cutoff.timestamp()
        for path in SCREENSHOTS_DIR.iterdir():
            if not path.is_file():
                continue
            try:
                if path.stat().st_mtime < cutoff_ts:
                    if delete_screenshot_file(path):
                        deleted_files += 1
            except OSError:
                continue

        return {"deleted_rows": deleted_rows, "deleted_files": deleted_files}

    def list_projects(self, include_archived: bool = False) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if include_archived:
                rows = conn.execute(
                    "SELECT * FROM projects ORDER BY archived, name COLLATE NOCASE"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM projects WHERE archived=0 ORDER BY name COLLATE NOCASE"
                ).fetchall()
        return [dict(r) for r in rows]

    def create_project(self, name: str, color: str = "#2f6f5e") -> dict[str, Any]:
        name = (name or "").strip() or "Проект"
        color = (color or "#2f6f5e").strip()
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO projects(name, color, archived, created_at) VALUES(?, ?, 0, ?)",
                (name, color, _iso(_utcnow())),
            )
            pid = int(cur.lastrowid)
            # Time Doctor: project needs at least one task to be usable
            conn.execute(
                "INSERT INTO tasks(project_id, name, done, created_at) VALUES(?, ?, 0, ?)",
                (pid, "Основная", _iso(_utcnow())),
            )
            row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        return dict(row)

    def update_project(
        self,
        project_id: int,
        *,
        name: str | None = None,
        color: str | None = None,
        archived: bool | None = None,
    ) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not row:
                return None
            new_name = name.strip() if name is not None else row["name"]
            new_color = color.strip() if color is not None else row["color"]
            new_arch = int(archived) if archived is not None else row["archived"]
            conn.execute(
                "UPDATE projects SET name=?, color=?, archived=? WHERE id=?",
                (new_name, new_color, new_arch, project_id),
            )
            row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        return dict(row)

    def delete_project(self, project_id: int) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
            return cur.rowcount > 0

    def list_tasks(self, project_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if project_id is None:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY done, name COLLATE NOCASE"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE project_id=? ORDER BY done, name COLLATE NOCASE",
                    (project_id,),
                ).fetchall()
        return [dict(r) for r in rows]

    def create_task(self, project_id: int, name: str) -> dict[str, Any]:
        name = (name or "").strip() or "Задача"
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO tasks(project_id, name, done, created_at) VALUES(?, ?, 0, ?)",
                (project_id, name, _iso(_utcnow())),
            )
            tid = int(cur.lastrowid)
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        return dict(row)

    def update_task(
        self,
        task_id: int,
        *,
        name: str | None = None,
        done: bool | None = None,
    ) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not row:
                return None
            new_name = name.strip() if name is not None else row["name"]
            new_done = int(done) if done is not None else row["done"]
            conn.execute(
                "UPDATE tasks SET name=?, done=? WHERE id=?",
                (new_name, new_done, task_id),
            )
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row)

    def delete_task(self, task_id: int) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            return cur.rowcount > 0

    def clear_all_data(self) -> None:
        with self.connect() as conn:
            rows = conn.execute("SELECT path FROM screenshots").fetchall()
            for row in rows:
                delete_screenshot_file(row["path"])
            conn.execute("DELETE FROM screenshots")
            conn.execute("DELETE FROM sessions")
        ensure_data_dirs()
        for path in SCREENSHOTS_DIR.iterdir():
            if path.is_file():
                delete_screenshot_file(path)
