from __future__ import annotations

import socket
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from deskline.capture import delete_screenshot_file
from deskline.classify import (
    display_name_for_app,
    is_system_noise,
    normalize_category,
    resolve_activity,
    site_for_activity_label,
)
from deskline.company_tokens import (
    EMPLOYEE_COLORS,
    hash_ingest_token,
    initials_from_name,
    new_ingest_token,
)
from deskline.config import DB_PATH, ensure_data_dirs, get_screenshots_dir
from deskline.icons import (
    icon_url_for_app,
    resolve_icon_url,
)

MIN_DISPLAY_SEC = 60.0


class ProjectNameExists(ValueError):
    """Raised when an active project with the same name already exists."""


def _utcnow() -> datetime:
    return datetime.now().astimezone()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def parse_iso_datetime(value: str | datetime) -> datetime:
    """Parse ISO-8601 datetimes from the UI (including trailing Z) as timezone-aware."""
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.astimezone()
    text = str(value).strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        # Date-only / naive values are treated as local wall time.
        return parsed.astimezone()
    return parsed


def _parse(dt: str | None) -> datetime | None:
    if not dt:
        return None
    try:
        return parse_iso_datetime(dt)
    except ValueError:
        return None


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
    employee_id: int | None = None


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

                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    display_name TEXT NOT NULL,
                    initials TEXT NOT NULL DEFAULT '?',
                    color TEXT NOT NULL DEFAULT '#1f6b56',
                    role TEXT NOT NULL DEFAULT 'member',
                    active INTEGER NOT NULL DEFAULT 1,
                    ingest_token_hash TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_employees_token ON employees(ingest_token_hash);

                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    hostname TEXT NOT NULL,
                    last_seen_at TEXT,
                    FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE,
                    UNIQUE(employee_id, hostname)
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
                ("employee_id", "INTEGER"),
                ("ingest_key", "TEXT"),
            ):
                if col not in cols:
                    conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {decl}")
            shot_cols = {r[1] for r in conn.execute("PRAGMA table_info(screenshots)").fetchall()}
            if "employee_id" not in shot_cols:
                conn.execute("ALTER TABLE screenshots ADD COLUMN employee_id INTEGER")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_ingest_key "
                "ON sessions(ingest_key) WHERE ingest_key IS NOT NULL"
            )
        self.ensure_default_employee()

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
        employee_id: int | None = None,
        ingest_key: str | None = None,
    ) -> int:
        started = started_at or _utcnow()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO sessions(
                    app_name, window_title, url_hint, started_at, category,
                    display_name, activity_kind, activity_label, app_path,
                    project_id, task_id, employee_id, ingest_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    employee_id,
                    ingest_key,
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

    def repair_sessions_spanning_boot(self, boot_time: float) -> int:
        """Clamp sessions that started before OS boot and ended after it.

        Hard power-off leaves `ended_at IS NULL`; on restart an older bug resumed
        that session so offline hours were counted. Rewrite `started_at` to boot
        so only post-boot time remains.
        """
        boot_dt = datetime.fromtimestamp(float(boot_time)).astimezone()
        boot_iso = _iso(boot_dt)
        repaired = 0
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, started_at, ended_at, idle_sec FROM sessions
                WHERE started_at < ?
                  AND ended_at IS NOT NULL
                  AND ended_at > ?
                """,
                (boot_iso, boot_iso),
            ).fetchall()
            for row in rows:
                started = _parse(row["started_at"])
                ended = _parse(row["ended_at"])
                if not started or not ended or ended <= boot_dt:
                    continue
                full_span = max(0.0, (ended - started).total_seconds())
                duration = max(0.0, (ended - boot_dt).total_seconds())
                idle_full = float(row["idle_sec"] or 0)
                idle_full = min(max(0.0, idle_full), full_span) if full_span else 0.0
                idle_part = (
                    idle_full * (duration / full_span) if full_span > 0 else 0.0
                )
                idle_part = min(idle_part, duration)
                conn.execute(
                    """
                    UPDATE sessions
                    SET started_at=?, duration_sec=?, idle_sec=?
                    WHERE id=?
                    """,
                    (boot_iso, duration, idle_part, row["id"]),
                )
                repaired += 1
        return repaired

    def update_session_activity(
        self,
        session_id: int,
        *,
        activity_label: str,
        activity_kind: str | None = None,
        display_name: str | None = None,
    ) -> bool:
        """Relabel an open/closed session after RDP vision confirm (does not change duration)."""
        label = (activity_label or "").strip()
        if not label or session_id <= 0:
            return False
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM sessions WHERE id=?", (session_id,)).fetchone()
            if not row:
                return False
            fields = ["activity_label=?"]
            vals: list[Any] = [label]
            if activity_kind:
                fields.append("activity_kind=?")
                vals.append(activity_kind)
            if display_name:
                fields.append("display_name=?")
                vals.append(display_name)
            vals.append(session_id)
            conn.execute(
                f"UPDATE sessions SET {', '.join(fields)} WHERE id=?",
                tuple(vals),
            )
            return True

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
            employee_id=int(row["employee_id"]) if "employee_id" in keys and row["employee_id"] is not None else None,
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
        # Re-resolve labels every time so rankings stay brand-readable even for
        # older sessions that stored abstract buckets («Разработка», «Почта»).
        resolved = resolve_activity(
            app,
            title,
            site,
            work_mode=work_mode,
            work_chat_keywords=work_chat_keywords,
        )
        display = resolved["display_name"]
        kind = resolved["activity_kind"]
        label = resolved["activity_label"]
        site = resolved.get("url_hint") or site
        cat = cat or resolved["category"]
        hidden = is_system_noise(app) or kind == "system"
        project_id = None
        task_id = None
        if "project_id" in keys and row["project_id"] is not None:
            project_id = int(row["project_id"])
        if "task_id" in keys and row["task_id"] is not None:
            task_id = int(row["task_id"])
        employee_id = None
        if "employee_id" in keys and row["employee_id"] is not None:
            employee_id = int(row["employee_id"])
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
            "employee_id": employee_id,
        }

    def summary_for_day(
        self,
        day: date | None = None,
        project_id: int | None = None,
        task_id: int | None = None,
        employee_id: int | None = None,
    ) -> dict[str, Any]:
        day = day or date.today()
        start = datetime.combine(day, datetime.min.time()).astimezone()
        end = start + timedelta(days=1)
        return self.summary_range(
            start, end, project_id=project_id, task_id=task_id, employee_id=employee_id
        )

    def daily_trends(
        self,
        days: int = 7,
        project_id: int | None = None,
        task_id: int | None = None,
        employee_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Time Doctor–style Hours Tracked + productivity mix per day."""
        days = max(1, min(int(days), 31))
        today = date.today()
        out: list[dict[str, Any]] = []
        for i in range(days - 1, -1, -1):
            day = today - timedelta(days=i)
            s = self.summary_for_day(
                day, project_id=project_id, task_id=task_id, employee_id=employee_id
            )
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
        task_id: int | None = None,
        employee_id: int | None = None,
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
        by_project: dict[int | None, float] = {}
        by_task: dict[int | None, float] = {}
        task_projects: dict[int | None, int | None] = {}
        activity_kinds: dict[str, str] = {}
        app_kinds: dict[str, str] = {}
        app_exe_by_label: dict[str, str] = {}
        app_path_by_exe: dict[str, str] = {}
        activity_app_secs: dict[str, dict[str, float]] = {}
        activity_site_secs: dict[str, dict[str, float]] = {}
        # app_label → activity_label → seconds (for Time Doctor–style grouping)
        activity_by_app: dict[str, dict[str, float]] = {}
        activity_kind_by_app: dict[str, dict[str, str]] = {}
        activity_cat_by_app: dict[str, dict[str, str]] = {}
        activity_site_by_app: dict[str, dict[str, str | None]] = {}
        by_kind: dict[str, float] = {}
        activity_cats: dict[str, str] = {}
        app_cats: dict[str, str] = {}
        site_cats: dict[str, str] = {}
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
            if task_id is not None and meta.get("task_id") != task_id:
                continue
            if employee_id is not None and meta.get("employee_id") != employee_id:
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
            if app_label not in app_cats:
                app_cats[app_label] = cat
            if app_label not in app_exe_by_label:
                app_exe_by_label[app_label] = exe
            if meta.get("app_path") and exe not in app_path_by_exe:
                app_path_by_exe[exe] = meta["app_path"]
            act = meta["activity_label"]
            by_activity[act] = by_activity.get(act, 0.0) + dur
            kind = meta["activity_kind"] or "other"
            if act not in activity_kinds:
                activity_kinds[act] = kind
            if act not in activity_cats:
                activity_cats[act] = cat
            bucket = activity_app_secs.setdefault(act, {})
            bucket[exe] = bucket.get(exe, 0.0) + dur
            app_acts = activity_by_app.setdefault(app_label, {})
            app_acts[act] = app_acts.get(act, 0.0) + dur
            activity_kind_by_app.setdefault(app_label, {}).setdefault(act, kind)
            activity_cat_by_app.setdefault(app_label, {}).setdefault(act, cat)
            by_kind[kind] = by_kind.get(kind, 0.0) + dur
            site = meta["url_hint"]
            if site:
                by_site[site] = by_site.get(site, 0.0) + dur
                if site not in site_cats:
                    site_cats[site] = cat
                site_bucket = activity_site_secs.setdefault(act, {})
                site_bucket[site] = site_bucket.get(site, 0.0) + dur
                activity_site_by_app.setdefault(app_label, {})[act] = site
            elif act not in activity_site_by_app.setdefault(app_label, {}):
                activity_site_by_app[app_label][act] = None
            pid = meta.get("project_id")
            pid_key = int(pid) if pid is not None else None
            by_project[pid_key] = by_project.get(pid_key, 0.0) + dur
            tid = meta.get("task_id")
            tid_key = int(tid) if tid is not None else None
            by_task[tid_key] = by_task.get(tid_key, 0.0) + dur
            if tid_key not in task_projects:
                task_projects[tid_key] = pid_key

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

        # Do not download/extract icons during summary aggregation — that can
        # block the API for tens of seconds (favicon timeouts × many sites).
        # The UI resolves /api/icons lazily when rows are rendered.

        by_app_grouped: list[dict[str, Any]] = []
        for app_label, app_sec in by_app.items():
            if app_sec < MIN_DISPLAY_SEC:
                continue
            exe = app_exe_by_label.get(app_label, "unknown.exe")
            children_raw = activity_by_app.get(app_label) or {}
            children: list[dict[str, Any]] = []
            for act_name, act_sec in children_raw.items():
                if act_sec < MIN_DISPLAY_SEC:
                    continue
                site = activity_site_by_app.get(app_label, {}).get(act_name)
                if not site:
                    site = _top_site(act_name) or site_for_activity_label(act_name)
                children.append(
                    {
                        "name": act_name,
                        "sec": act_sec,
                        "kind": activity_kind_by_app.get(app_label, {}).get(
                            act_name, activity_kinds.get(act_name, "other")
                        ),
                        "category": activity_cat_by_app.get(app_label, {}).get(
                            act_name, activity_cats.get(act_name, "neutral")
                        ),
                        "site": site,
                        "icon_url": resolve_icon_url(site=site, app_name=exe),
                    }
                )
            children.sort(key=lambda x: x["sec"], reverse=True)
            # Single child with same name as parent → no expand row
            if (
                len(children) == 1
                and children[0]["name"].casefold() == app_label.casefold()
            ):
                children = []
            by_app_grouped.append(
                {
                    "name": app_label,
                    "sec": app_sec,
                    "kind": app_kinds.get(app_label, "other"),
                    "category": app_cats.get(app_label, "neutral"),
                    "app_name": exe,
                    "icon_url": icon_url_for_app(exe),
                    "children": children,
                }
            )
        by_app_grouped.sort(key=lambda x: x["sec"], reverse=True)

        # Remember exe→path so /media/icons can re-extract without a blank path.
        try:
            from deskline.icons import remember_app_paths

            remember_app_paths(app_path_by_exe)
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
                        "category": activity_cats.get(k, "neutral"),
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
                        "category": app_cats.get(k, "neutral"),
                        "app_name": app_exe_by_label.get(k, "unknown.exe"),
                        "icon_url": icon_url_for_app(app_exe_by_label.get(k)),
                    }
                    for k, v in by_app.items()
                    if v >= MIN_DISPLAY_SEC
                ],
                key=lambda x: x["sec"],
                reverse=True,
            ),
            "by_app_grouped": by_app_grouped,
            "by_site": sorted(
                [
                    {
                        "name": k,
                        "sec": v,
                        "kind": "search",
                        "category": site_cats.get(k, "neutral"),
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
                    {
                        "task_id": k,
                        "project_id": task_projects.get(k),
                        "sec": v,
                    }
                    for k, v in by_task.items()
                    if v >= 1.0
                ],
                key=lambda x: x["sec"],
                reverse=True,
            ),
        }

    def apps_range(
        self,
        start: datetime,
        end: datetime,
        project_id: int | None = None,
        task_id: int | None = None,
        employee_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.summary_range(
            start, end, project_id=project_id, task_id=task_id, employee_id=employee_id
        )["by_app"]

    def sites_range(
        self,
        start: datetime,
        end: datetime,
        project_id: int | None = None,
        task_id: int | None = None,
        employee_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.summary_range(
            start, end, project_id=project_id, task_id=task_id, employee_id=employee_id
        )["by_site"]

    def activities_range(
        self,
        start: datetime,
        end: datetime,
        project_id: int | None = None,
        task_id: int | None = None,
        employee_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.summary_range(
            start, end, project_id=project_id, task_id=task_id, employee_id=employee_id
        )["by_activity"]

    def timeline_for_day(
        self, day: date | None = None, employee_id: int | None = None
    ) -> list[dict[str, Any]]:
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
            if employee_id is not None and meta.get("employee_id") != employee_id:
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
                    "employee_id": meta.get("employee_id"),
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
        shots_dir = get_screenshots_dir()
        if shots_dir.is_dir():
            for path in shots_dir.iterdir():
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

    def find_project_by_name(
        self, name: str, *, exclude_id: int | None = None
    ) -> dict[str, Any] | None:
        needle = (name or "").strip().casefold()
        if not needle:
            return None
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects WHERE archived=0"
            ).fetchall()
        for row in rows:
            if exclude_id is not None and int(row["id"]) == int(exclude_id):
                continue
            if str(row["name"] or "").strip().casefold() == needle:
                return dict(row)
        return None

    def get_project(self, project_id: int | None) -> dict[str, Any] | None:
        if project_id is None:
            return None
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id=?", (project_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_task(self, task_id: int | None) -> dict[str, Any] | None:
        if task_id is None:
            return None
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def create_project(self, name: str, color: str = "#2f6f5e") -> dict[str, Any]:
        name = (name or "").strip() or "Проект"
        color = (color or "#2f6f5e").strip()
        if self.find_project_by_name(name):
            raise ProjectNameExists(f"Проект «{name}» уже есть")
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
            if not new_arch and self.find_project_by_name(new_name, exclude_id=project_id):
                raise ProjectNameExists(f"Проект «{new_name}» уже есть")
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
        shots_dir = get_screenshots_dir()
        if shots_dir.is_dir():
            for path in shots_dir.iterdir():
                if path.is_file():
                    delete_screenshot_file(path)

    def _employee_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "display_name": row["display_name"],
            "initials": row["initials"],
            "color": row["color"],
            "role": row["role"],
            "active": bool(row["active"]),
            "has_token": bool(row["ingest_token_hash"]),
            "created_at": row["created_at"],
        }

    def ensure_default_employee(self) -> int:
        """Create local owner employee and backfill sessions without employee_id."""
        hostname = socket.gethostname() or "PC"
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id FROM employees WHERE role='admin' ORDER BY id ASC LIMIT 1"
            ).fetchone()
            if row:
                eid = int(row["id"])
            else:
                token = new_ingest_token()
                cur = conn.execute(
                    """
                    INSERT INTO employees(
                        display_name, initials, color, role, active,
                        ingest_token_hash, created_at
                    ) VALUES (?, ?, ?, 'admin', 1, ?, ?)
                    """,
                    (
                        "Я",
                        initials_from_name("Я"),
                        EMPLOYEE_COLORS[0],
                        hash_ingest_token(token),
                        _iso(_utcnow()),
                    ),
                )
                eid = int(cur.lastrowid)
            conn.execute(
                "UPDATE sessions SET employee_id=? WHERE employee_id IS NULL",
                (eid,),
            )
            conn.execute(
                "UPDATE screenshots SET employee_id=? WHERE employee_id IS NULL",
                (eid,),
            )
            conn.execute(
                """
                INSERT INTO devices(employee_id, hostname, last_seen_at)
                VALUES (?, ?, ?)
                ON CONFLICT(employee_id, hostname) DO UPDATE SET last_seen_at=excluded.last_seen_at
                """,
                (eid, hostname, _iso(_utcnow())),
            )
        return eid

    def list_employees(self, *, active_only: bool = False) -> list[dict[str, Any]]:
        self.ensure_default_employee()
        q = "SELECT * FROM employees"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY role='admin' DESC, display_name COLLATE NOCASE"
        with self.connect() as conn:
            rows = conn.execute(q).fetchall()
        return [self._employee_row(r) for r in rows]

    def get_employee(self, employee_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM employees WHERE id=?", (employee_id,)
            ).fetchone()
        return self._employee_row(row) if row else None

    def create_employee(self, display_name: str, *, role: str = "member") -> dict[str, Any]:
        name = (display_name or "").strip() or "Сотрудник"
        role = "admin" if role == "admin" else "member"
        token = new_ingest_token()
        with self.connect() as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM employees").fetchone()["c"]
            color = EMPLOYEE_COLORS[int(count) % len(EMPLOYEE_COLORS)]
            cur = conn.execute(
                """
                INSERT INTO employees(
                    display_name, initials, color, role, active,
                    ingest_token_hash, created_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    name,
                    initials_from_name(name),
                    color,
                    role,
                    hash_ingest_token(token),
                    _iso(_utcnow()),
                ),
            )
            eid = int(cur.lastrowid)
            row = conn.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
        out = self._employee_row(row)
        out["ingest_token"] = token
        return out

    def update_employee(
        self,
        employee_id: int,
        *,
        display_name: str | None = None,
        active: bool | None = None,
        role: str | None = None,
    ) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM employees WHERE id=?", (employee_id,)
            ).fetchone()
            if not row:
                return None
            name = display_name.strip() if display_name is not None else row["display_name"]
            initials = initials_from_name(name) if display_name is not None else row["initials"]
            new_active = int(active) if active is not None else row["active"]
            new_role = row["role"]
            if role is not None:
                new_role = "admin" if role == "admin" else "member"
            conn.execute(
                """
                UPDATE employees
                SET display_name=?, initials=?, active=?, role=?
                WHERE id=?
                """,
                (name, initials, new_active, new_role, employee_id),
            )
            row = conn.execute(
                "SELECT * FROM employees WHERE id=?", (employee_id,)
            ).fetchone()
        return self._employee_row(row)

    def rotate_employee_token(self, employee_id: int) -> dict[str, Any] | None:
        token = new_ingest_token()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id FROM employees WHERE id=?", (employee_id,)
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE employees SET ingest_token_hash=? WHERE id=?",
                (hash_ingest_token(token), employee_id),
            )
            row = conn.execute(
                "SELECT * FROM employees WHERE id=?", (employee_id,)
            ).fetchone()
        out = self._employee_row(row)
        out["ingest_token"] = token
        return out

    def find_employee_by_token(self, token: str) -> dict[str, Any] | None:
        digest = hash_ingest_token(token)
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM employees WHERE ingest_token_hash=? AND active=1",
                (digest,),
            ).fetchone()
        return self._employee_row(row) if row else None

    def touch_device(self, employee_id: int, hostname: str) -> None:
        host = (hostname or "").strip() or "unknown"
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO devices(employee_id, hostname, last_seen_at)
                VALUES (?, ?, ?)
                ON CONFLICT(employee_id, hostname) DO UPDATE SET last_seen_at=excluded.last_seen_at
                """,
                (employee_id, host, _iso(_utcnow())),
            )

    def list_devices(self, employee_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if employee_id is None:
                rows = conn.execute(
                    """
                    SELECT d.*, e.display_name AS employee_name
                    FROM devices d
                    JOIN employees e ON e.id = d.employee_id
                    ORDER BY d.last_seen_at DESC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT d.*, e.display_name AS employee_name
                    FROM devices d
                    JOIN employees e ON e.id = d.employee_id
                    WHERE d.employee_id=?
                    ORDER BY d.last_seen_at DESC
                    """,
                    (employee_id,),
                ).fetchall()
        return [
            {
                "id": int(r["id"]),
                "employee_id": int(r["employee_id"]),
                "employee_name": r["employee_name"],
                "hostname": r["hostname"],
                "last_seen_at": r["last_seen_at"],
            }
            for r in rows
        ]

    def get_session_payload(self, session_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            return None
        keys = set(row.keys())
        return {
            "app_name": row["app_name"],
            "window_title": row["window_title"],
            "url_hint": row["url_hint"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
            "duration_sec": float(row["duration_sec"] or 0),
            "category": row["category"],
            "display_name": row["display_name"] if "display_name" in keys else None,
            "activity_kind": row["activity_kind"] if "activity_kind" in keys else None,
            "activity_label": row["activity_label"] if "activity_label" in keys else None,
            "app_path": row["app_path"] if "app_path" in keys else None,
            "idle_sec": float(row["idle_sec"] or 0) if "idle_sec" in keys else 0.0,
            "project_id": int(row["project_id"])
            if "project_id" in keys and row["project_id"] is not None
            else None,
            "task_id": int(row["task_id"])
            if "task_id" in keys and row["task_id"] is not None
            else None,
            "ingest_key": row["ingest_key"] if "ingest_key" in keys else None,
        }

    def ingest_sessions(
        self, employee_id: int, sessions: list[dict[str, Any]], *, hostname: str | None = None
    ) -> dict[str, Any]:
        inserted = 0
        skipped = 0
        with self.connect() as conn:
            for item in sessions:
                ingest_key = str(item.get("ingest_key") or "").strip() or None
                if ingest_key:
                    exists = conn.execute(
                        "SELECT id FROM sessions WHERE ingest_key=?", (ingest_key,)
                    ).fetchone()
                    if exists:
                        skipped += 1
                        continue
                started = item.get("started_at")
                ended = item.get("ended_at")
                if not started:
                    skipped += 1
                    continue
                try:
                    duration = float(item.get("duration_sec") or 0)
                except (TypeError, ValueError):
                    duration = 0.0
                try:
                    idle = float(item.get("idle_sec") or 0)
                except (TypeError, ValueError):
                    idle = 0.0
                conn.execute(
                    """
                    INSERT INTO sessions(
                        app_name, window_title, url_hint, started_at, ended_at,
                        duration_sec, category, display_name, activity_kind,
                        activity_label, app_path, idle_sec, project_id, task_id,
                        employee_id, ingest_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(item.get("app_name") or "unknown.exe"),
                        str(item.get("window_title") or ""),
                        item.get("url_hint"),
                        str(started),
                        str(ended) if ended else None,
                        max(0.0, duration),
                        normalize_category(str(item.get("category") or "neutral")),
                        item.get("display_name"),
                        item.get("activity_kind"),
                        item.get("activity_label"),
                        item.get("app_path"),
                        max(0.0, idle),
                        item.get("project_id"),
                        item.get("task_id"),
                        employee_id,
                        ingest_key,
                    ),
                )
                inserted += 1
        if hostname:
            self.touch_device(employee_id, hostname)
        else:
            self.touch_device(employee_id, "remote")
        return {"inserted": inserted, "skipped": skipped}

    def team_summary(
        self,
        start: datetime,
        end: datetime,
        *,
        project_id: int | None = None,
        task_id: int | None = None,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for emp in self.list_employees(active_only=True):
            s = self.summary_range(
                start, end, project_id=project_id, task_id=task_id, employee_id=emp["id"]
            )
            out.append(
                {
                    **emp,
                    "focus_pct": s.get("focus_pct") or 0,
                    "activity_pct": s.get("activity_pct") or 0,
                    "total_sec": s.get("total_sec") or 0,
                    "focus_sec": s.get("focus_sec") or 0,
                    "idle_sec": s.get("idle_sec") or 0,
                    "active_sec": s.get("active_sec") or 0,
                    "by_category": s.get("by_category") or {},
                }
            )
        out.sort(key=lambda r: float(r.get("focus_pct") or 0), reverse=True)
        return out
