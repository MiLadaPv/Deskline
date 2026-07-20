from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from deskline.capture import delete_screenshot_file
from deskline.classify import display_name_for_app, is_browser, is_system_noise, resolve_activity
from deskline.config import DB_PATH, SCREENSHOTS_DIR, ensure_data_dirs
from deskline.icons import ensure_app_icon, icon_url_for_app

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
                """
            )
            cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
            for col, decl in (
                ("display_name", "TEXT"),
                ("activity_kind", "TEXT"),
                ("activity_label", "TEXT"),
                ("app_path", "TEXT"),
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
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO app_rules(app_name, category) VALUES(?, ?)
                ON CONFLICT(app_name) DO UPDATE SET category=excluded.category
                """,
                (app_name.lower(), category),
            )

    def set_site_rule(self, site: str, category: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO site_rules(site, category) VALUES(?, ?)
                ON CONFLICT(site) DO UPDATE SET category=excluded.category
                """,
                (site.lower(), category),
            )

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
    ) -> int:
        started = started_at or _utcnow()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO sessions(
                    app_name, window_title, url_hint, started_at, category,
                    display_name, activity_kind, activity_label, app_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        )

    def _enrich(self, row: sqlite3.Row) -> dict[str, Any]:
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
            resolved = resolve_activity(app, title, site)
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
        return {
            "app_name": app,
            "app_path": app_path,
            "display_name": display or display_name_for_app(app),
            "activity_kind": kind or "other",
            "activity_label": label or display_name_for_app(app),
            "category": cat or "neutral",
            "url_hint": site,
            "hidden": hidden,
        }

    def summary_for_day(self, day: date | None = None) -> dict[str, Any]:
        day = day or date.today()
        start = datetime.combine(day, datetime.min.time()).astimezone()
        end = start + timedelta(days=1)
        return self.summary_range(start, end)

    def summary_range(self, start: datetime, end: datetime) -> dict[str, Any]:
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
        activity_kinds: dict[str, str] = {}
        app_kinds: dict[str, str] = {}
        app_exe_by_label: dict[str, str] = {}
        app_path_by_exe: dict[str, str] = {}
        activity_app_secs: dict[str, dict[str, float]] = {}
        by_kind: dict[str, float] = {}
        total = 0.0
        tracked = 0.0
        now = _utcnow()

        for row in rows:
            s = _parse(row["started_at"]) or start
            e = _parse(row["ended_at"]) or now
            seg_start = max(s, start)
            seg_end = min(e, end)
            dur = max(0.0, (seg_end - seg_start).total_seconds())
            if dur <= 0:
                continue
            total += dur
            meta = self._enrich(row)
            if meta["hidden"]:
                continue
            tracked += dur
            cat = meta["category"] if meta["category"] in by_cat else "neutral"
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

        def _top_exe(label: str) -> str:
            secs = activity_app_secs.get(label) or {}
            if not secs:
                return "unknown.exe"
            return max(secs.items(), key=lambda kv: kv[1])[0]

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

        focus = by_cat["productive"]
        focus_pct = (focus / tracked * 100.0) if tracked else 0.0
        return {
            "total_sec": tracked,
            "raw_total_sec": total,
            "focus_sec": focus,
            "focus_pct": round(focus_pct, 1),
            "by_category": by_cat,
            "by_kind": by_kind,
            "by_activity": sorted(
                [
                    {
                        "name": k,
                        "sec": v,
                        "kind": activity_kinds.get(k, "other"),
                        "app_name": _top_exe(k),
                        "icon_url": icon_url_for_app(_top_exe(k)),
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
                        "icon_url": icon_url_for_app("msedge.exe"),
                    }
                    for k, v in by_site.items()
                    if v >= MIN_DISPLAY_SEC
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

    def screenshots_for_date(self, day: date | None = None) -> list[dict[str, Any]]:
        day = day or date.today()
        start = datetime.combine(day, datetime.min.time()).astimezone()
        end = start + timedelta(days=1)
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, path, taken_at, session_id, reason
                FROM screenshots
                WHERE taken_at >= ? AND taken_at < ?
                ORDER BY taken_at DESC
                """,
                (_iso(start), _iso(end)),
            ).fetchall()
        return [dict(r) for r in rows]

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
