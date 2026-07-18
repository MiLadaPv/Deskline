from __future__ import annotations

import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from deskline import __version__
from deskline.config import (
    APP_NAME,
    BASE_URL,
    HOST,
    PORT,
    SCREENSHOTS_DIR,
    WEB_ROOT,
    load_config,
    save_config,
)
from deskline.db import Database
from deskline.tracker import Tracker


class SettingsUpdate(BaseModel):
    poll_interval_sec: float | None = None
    min_session_sec: float | None = None
    screenshot_interval_sec: int | None = None
    screenshot_on_app_switch: bool | None = None
    screenshots_enabled: bool | None = None
    open_dashboard_on_start: bool | None = None
    autostart: bool | None = None


class RuleUpdate(BaseModel):
    category: str = Field(pattern="^(productive|neutral|distracting)$")


def create_app(tracker: Tracker, db: Database | None = None) -> FastAPI:
    db = db or tracker.db
    app = FastAPI(title=APP_NAME, version=__version__)
    templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))
    app.mount("/static", StaticFiles(directory=str(WEB_ROOT / "static")), name="static")

    def _range(from_s: str | None, to_s: str | None) -> tuple[datetime, datetime]:
        end = datetime.fromisoformat(to_s) if to_s else datetime.now().astimezone()
        start = datetime.fromisoformat(from_s) if from_s else end - timedelta(days=1)
        return start, end

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "app_name": APP_NAME,
                "version": __version__,
                "base_url": BASE_URL,
            },
        )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "app": APP_NAME, "version": __version__}

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return tracker.status()

    @app.get("/api/summary/today")
    def summary_today() -> dict[str, Any]:
        return db.summary_for_day(date.today())

    @app.get("/api/apps")
    def apps(
        from_ts: str | None = Query(default=None, alias="from"),
        to: str | None = None,
    ) -> list[dict[str, Any]]:
        start, end = _range(from_ts, to)
        return db.apps_range(start, end)

    @app.get("/api/sites")
    def sites(
        from_ts: str | None = Query(default=None, alias="from"),
        to: str | None = None,
    ) -> list[dict[str, Any]]:
        start, end = _range(from_ts, to)
        return db.sites_range(start, end)

    @app.get("/api/activities")
    def activities(
        from_ts: str | None = Query(default=None, alias="from"),
        to: str | None = None,
    ) -> list[dict[str, Any]]:
        start, end = _range(from_ts, to)
        return db.activities_range(start, end)

    @app.get("/api/screenshots")
    def screenshots(day: str | None = None) -> list[dict[str, Any]]:
        d = date.fromisoformat(day) if day else date.today()
        rows = db.screenshots_for_date(d)
        for row in rows:
            p = Path(row["path"])
            row["filename"] = p.name
            row["url"] = f"/media/screenshots/{p.name}"
        return rows

    @app.get("/media/screenshots/{name}")
    def media_screenshot(name: str) -> FileResponse:
        safe = Path(name).name
        path = SCREENSHOTS_DIR / safe
        if not path.exists() or not path.is_file():
            raise HTTPException(404, "Screenshot not found")
        return FileResponse(path)

    @app.post("/api/control/pause")
    def pause() -> dict[str, Any]:
        tracker.pause()
        return tracker.status()

    @app.post("/api/control/resume")
    def resume() -> dict[str, Any]:
        tracker.resume()
        return tracker.status()

    @app.get("/api/settings")
    def get_settings() -> dict[str, Any]:
        return load_config()

    @app.put("/api/settings")
    def put_settings(body: SettingsUpdate) -> dict[str, Any]:
        cfg = load_config()
        data = body.model_dump(exclude_none=True)
        cfg.update(data)
        saved = save_config(cfg)
        tracker.reload_config()
        if "autostart" in data:
            _set_autostart(bool(saved.get("autostart")))
        return saved

    @app.put("/api/rules/{app_name}")
    def put_rule(app_name: str, body: RuleUpdate) -> dict[str, str]:
        db.set_app_rule(app_name, body.category)
        return {"app_name": app_name.lower(), "category": body.category}

    @app.post("/api/data/clear")
    def clear_data() -> dict[str, bool]:
        db.clear_all_data()
        return {"ok": True}

    return app


def _set_autostart(enabled: bool) -> None:
    try:
        import winreg
    except ImportError:
        return
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    name = "Deskline"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            import sys

            if getattr(sys, "frozen", False):
                cmd = f'"{sys.executable}" --no-browser'
            else:
                pythonw = Path(sys.executable).with_name("pythonw.exe")
                exe = str(pythonw if pythonw.exists() else sys.executable)
                cmd = f'"{exe}" -m deskline --no-browser'
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass


def open_dashboard() -> None:
    webbrowser.open(BASE_URL)


__all__ = ["create_app", "open_dashboard", "HOST", "PORT"]
