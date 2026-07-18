from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from deskline.config import DB_PATH, ensure_data_dirs


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
                    category TEXT NOT NULL DEFAULT 'neutral'
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
    ) -> int:
        started = started_at or _utcnow()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO sessions(app_name, window_title, url_hint, started_at, category)
                VALUES (?, ?, ?, ?, ?)
                """,
                (app_name, window_title or "", url_hint, _iso(started), category),
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
        return SessionRow(
            id=row["id"],
            app_name=row["app_name"],
            window_title=row["window_title"],
            url_hint=row["url_hint"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            duration_sec=float(row["duration_sec"] or 0),
            category=row["category"],
        )

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
        total = 0.0
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
            cat = row["category"] if row["category"] in by_cat else "neutral"
            by_cat[cat] += dur
            app = row["app_name"] or "unknown"
            by_app[app] = by_app.get(app, 0.0) + dur
            site = row["url_hint"]
            if site:
                by_site[site] = by_site.get(site, 0.0) + dur

        focus = by_cat["productive"]
        focus_pct = (focus / total * 100.0) if total else 0.0
        return {
            "total_sec": total,
            "focus_sec": focus,
            "focus_pct": round(focus_pct, 1),
            "by_category": by_cat,
            "by_app": sorted(
                [{"name": k, "sec": v} for k, v in by_app.items()],
                key=lambda x: x["sec"],
                reverse=True,
            ),
            "by_site": sorted(
                [{"name": k, "sec": v} for k, v in by_site.items()],
                key=lambda x: x["sec"],
                reverse=True,
            ),
        }

    def apps_range(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return self.summary_range(start, end)["by_app"]

    def sites_range(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return self.summary_range(start, end)["by_site"]

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

    def clear_all_data(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM screenshots")
            conn.execute("DELETE FROM sessions")
