from __future__ import annotations

import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from deskline import __version__
from deskline.auth import (
    COOKIE_NAME,
    change_password,
    create_session_token,
    is_password_set,
    is_public_path,
    set_password,
    validate_session_token,
    verify_password,
)
from deskline.capture import resolve_screenshot_file, screenshots_storage_info
from deskline.config import (
    APP_NAME,
    BASE_URL,
    HOST,
    PORT,
    ICONS_DIR,
    WEB_ROOT,
    ensure_screenshots_dir,
    get_screenshots_dir,
    load_config,
    save_config,
)
from deskline.db import Database, ProjectNameExists, parse_iso_datetime
from deskline.tracker import Tracker


class SettingsUpdate(BaseModel):
    poll_interval_sec: float | None = None
    min_session_sec: float | None = None
    idle_after_sec: float | None = Field(default=None, ge=30, le=3600)
    still_working_grace_sec: float | None = Field(default=None, ge=15, le=600)
    sleep_gap_sec: float | None = Field(default=None, ge=60, le=3600)
    poor_time_popup: bool | None = None
    poor_time_min_sec: float | None = Field(default=None, ge=15, le=3600)
    blur_screenshots: bool | None = None
    screenshot_interval_sec: int | None = Field(default=None, ge=60, le=3600)
    screenshot_on_app_switch: bool | None = None
    screenshots_enabled: bool | None = None
    screenshot_retention_days: int | None = Field(default=None, ge=0, le=3650)
    screenshots_dir: str | None = Field(default=None, max_length=500)
    open_dashboard_on_start: bool | None = None
    autostart: bool | None = None
    work_mode: bool | None = None
    work_chat_keywords: list[str] | None = None
    current_project_id: int | None = None
    current_task_id: int | None = None
    show_mini_tracker: bool | None = None


def _validate_screenshots_dir(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise HTTPException(
            400,
            "Укажите полный путь к папке, например D:\\Deskline\\screenshots",
        )
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".deskline_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise HTTPException(400, f"Не удалось использовать папку: {exc}") from exc
    return str(path)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default="#2f6f5e", max_length=32)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    color: str | None = Field(default=None, max_length=32)
    archived: bool | None = None


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    project_id: int


class TaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    done: bool | None = None


class FocusUpdate(BaseModel):
    project_id: int | None = None
    task_id: int | None = None


class RuleUpdate(BaseModel):
    kind: str = Field(default="app", pattern="^(app|site)$")
    category: str = Field(pattern="^(productive|neutral|distracting|unrated)$")


class PasswordBody(BaseModel):
    password: str = Field(min_length=4, max_length=128)


class ChangePasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=4, max_length=128)


def _set_session_cookie(response: Response, token: str) -> None:
    # Session cookie (no max_age): cleared when the browser is closed.
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="strict",
    )


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        if is_public_path(path):
            return await call_next(request)

        token = request.cookies.get(COOKIE_NAME)
        authed = validate_session_token(token)
        password_ready = is_password_set()

        if not password_ready:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "password setup required"}, status_code=401)
            return RedirectResponse(url="/login", status_code=303)

        if not authed:
            if path.startswith("/api/") or path.startswith("/media/"):
                return JSONResponse({"detail": "authentication required"}, status_code=401)
            return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)


def create_app(tracker: Tracker, db: Database | None = None) -> FastAPI:
    db = db or tracker.db
    app = FastAPI(title=APP_NAME, version=__version__)
    templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))
    app.mount("/static", StaticFiles(directory=str(WEB_ROOT / "static")), name="static")
    app.add_middleware(AuthMiddleware)

    def _range(from_s: str | None, to_s: str | None) -> tuple[datetime, datetime]:
        try:
            end = (
                parse_iso_datetime(to_s)
                if to_s
                else datetime.now().astimezone()
            )
            start = (
                parse_iso_datetime(from_s)
                if from_s
                else end - timedelta(days=1)
            )
        except ValueError as exc:
            raise HTTPException(400, f"Invalid date range: {exc}") from exc
        if start > end:
            start, end = end, start
        return start, end

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"app_name": APP_NAME, "version": __version__},
        )

    @app.get("/api/auth/status")
    def auth_status(request: Request) -> dict[str, Any]:
        token = request.cookies.get(COOKIE_NAME)
        return {
            "password_set": is_password_set(),
            "authenticated": validate_session_token(token),
        }

    @app.post("/api/auth/setup")
    def auth_setup(body: PasswordBody) -> Response:
        if is_password_set():
            raise HTTPException(400, "password already set")
        try:
            set_password(body.password)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        token = create_session_token()
        response = JSONResponse({"ok": True})
        _set_session_cookie(response, token)
        return response

    @app.post("/api/auth/login")
    def auth_login(body: PasswordBody) -> Response:
        if not is_password_set():
            raise HTTPException(400, "password not set")
        if not verify_password(body.password):
            raise HTTPException(401, "Неверный пароль")
        token = create_session_token()
        response = JSONResponse({"ok": True})
        _set_session_cookie(response, token)
        return response

    @app.post("/api/auth/logout")
    def auth_logout() -> Response:
        response = JSONResponse({"ok": True})
        _clear_session_cookie(response)
        return response

    @app.post("/api/auth/change-password")
    def auth_change_password(body: ChangePasswordBody) -> dict[str, bool]:
        try:
            change_password(body.current_password, body.new_password)
        except PermissionError as exc:
            raise HTTPException(401, "Неверный текущий пароль") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"ok": True}

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
        return {
            "ok": True,
            "app": APP_NAME,
            "version": __version__,
            # Fingerprint so the desktop shell can reject older packaged builds
            # that also listen on :8787 (e.g. legacy Deskline.exe).
            "edition": "local-python",
        }

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        st = tracker.status()
        st["version"] = __version__
        st["app"] = APP_NAME
        return st

    @app.get("/api/summary/today")
    def summary_today(
        project_id: int | None = None,
        task_id: int | None = None,
    ) -> dict[str, Any]:
        return db.summary_for_day(date.today(), project_id=project_id, task_id=task_id)

    @app.get("/api/summary")
    def summary_range_api(
        from_ts: str | None = Query(default=None, alias="from"),
        to: str | None = None,
        project_id: int | None = None,
        task_id: int | None = None,
    ) -> dict[str, Any]:
        start, end = _range(from_ts, to)
        return db.summary_range(start, end, project_id=project_id, task_id=task_id)

    @app.get("/api/trends")
    def trends(
        days: int = 7,
        project_id: int | None = None,
        task_id: int | None = None,
    ) -> list[dict[str, Any]]:
        days = max(1, min(int(days), 31))
        return db.daily_trends(days=days, project_id=project_id, task_id=task_id)

    @app.get("/api/timeline/today")
    def timeline_today() -> list[dict[str, Any]]:
        return db.timeline_for_day(date.today())

    @app.get("/api/projects")
    def projects(include_archived: bool = False) -> list[dict[str, Any]]:
        return db.list_projects(include_archived=include_archived)

    @app.post("/api/projects")
    def create_project(body: ProjectCreate) -> dict[str, Any]:
        try:
            return db.create_project(body.name, body.color)
        except ProjectNameExists as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.put("/api/projects/{project_id}")
    def update_project(project_id: int, body: ProjectUpdate) -> dict[str, Any]:
        try:
            row = db.update_project(
                project_id, name=body.name, color=body.color, archived=body.archived
            )
        except ProjectNameExists as exc:
            raise HTTPException(409, str(exc)) from exc
        if not row:
            raise HTTPException(404, "Project not found")
        return row

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: int) -> dict[str, Any]:
        ok = db.delete_project(project_id)
        if not ok:
            raise HTTPException(404, "Project not found")
        return {"ok": True}

    @app.get("/api/tasks")
    def tasks(project_id: int | None = None) -> list[dict[str, Any]]:
        return db.list_tasks(project_id)

    @app.post("/api/tasks")
    def create_task(body: TaskCreate) -> dict[str, Any]:
        return db.create_task(body.project_id, body.name)

    @app.put("/api/tasks/{task_id}")
    def update_task(task_id: int, body: TaskUpdate) -> dict[str, Any]:
        row = db.update_task(task_id, name=body.name, done=body.done)
        if not row:
            raise HTTPException(404, "Task not found")
        return row

    @app.delete("/api/tasks/{task_id}")
    def delete_task(task_id: int) -> dict[str, Any]:
        ok = db.delete_task(task_id)
        if not ok:
            raise HTTPException(404, "Task not found")
        return {"ok": True}

    @app.post("/api/focus")
    def set_focus(body: FocusUpdate) -> dict[str, Any]:
        cfg = load_config()
        cfg["current_project_id"] = body.project_id
        cfg["current_task_id"] = body.task_id
        saved = save_config(cfg)
        tracker.apply_focus()
        return {
            "current_project_id": saved.get("current_project_id"),
            "current_task_id": saved.get("current_task_id"),
        }

    @app.get("/api/ratings")
    def ratings() -> list[dict[str, Any]]:
        return db.ratings_for_day(date.today())

    @app.get("/api/apps")
    def apps(
        from_ts: str | None = Query(default=None, alias="from"),
        to: str | None = None,
        project_id: int | None = None,
        task_id: int | None = None,
    ) -> list[dict[str, Any]]:
        start, end = _range(from_ts, to)
        return db.apps_range(start, end, project_id=project_id, task_id=task_id)

    @app.get("/api/sites")
    def sites(
        from_ts: str | None = Query(default=None, alias="from"),
        to: str | None = None,
        project_id: int | None = None,
        task_id: int | None = None,
    ) -> list[dict[str, Any]]:
        start, end = _range(from_ts, to)
        return db.sites_range(start, end, project_id=project_id, task_id=task_id)

    @app.get("/api/activities")
    def activities(
        from_ts: str | None = Query(default=None, alias="from"),
        to: str | None = None,
        project_id: int | None = None,
        task_id: int | None = None,
    ) -> list[dict[str, Any]]:
        start, end = _range(from_ts, to)
        return db.activities_range(start, end, project_id=project_id, task_id=task_id)

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
        path = resolve_screenshot_file(name)
        if path is None:
            raise HTTPException(404, "Screenshot not found")
        return FileResponse(path, media_type="image/jpeg")

    @app.get("/media/icons/{name}")
    def media_icon(name: str) -> FileResponse:
        from deskline.icons import (
            app_name_from_icon_filename,
            ensure_app_icon,
            ensure_site_icon,
            is_site_icon_name,
            is_weak_icon_cache,
            shared_placeholder_path,
            site_from_icon_name,
        )

        safe = Path(name).name
        path = ICONS_DIR / safe
        if is_weak_icon_cache(path):
            if is_site_icon_name(safe):
                host = site_from_icon_name(safe)
                if host:
                    path = ensure_site_icon(host)
            else:
                stem = app_name_from_icon_filename(safe)
                if stem and stem != "placeholder":
                    path = ensure_app_icon(stem, None)
        if is_weak_icon_cache(path) or not path.exists():
            path = shared_placeholder_path()
        return FileResponse(path, media_type="image/png")

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
        cfg = load_config()
        storage = screenshots_storage_info()
        return {
            **cfg,
            "screenshots_path": storage["path"],
            "screenshots_storage": storage,
            "screenshots_dir_effective": str(get_screenshots_dir(cfg)),
        }

    @app.put("/api/settings")
    def put_settings(body: SettingsUpdate) -> dict[str, Any]:
        cfg = load_config()
        data = body.model_dump(exclude_none=True)
        if "screenshots_dir" in data:
            data["screenshots_dir"] = _validate_screenshots_dir(str(data["screenshots_dir"]))
        cfg.update(data)
        saved = save_config(cfg)
        ensure_screenshots_dir(saved)
        tracker.reload_config()
        if "autostart" in data:
            _set_autostart(bool(saved.get("autostart")))
        storage = screenshots_storage_info()
        return {
            **saved,
            "screenshots_path": storage["path"],
            "screenshots_storage": storage,
            "screenshots_dir_effective": str(get_screenshots_dir(saved)),
        }

    @app.post("/api/screenshots/purge")
    def purge_screenshots() -> dict[str, Any]:
        result = tracker.purge_old_screenshots()
        storage = screenshots_storage_info()
        return {**result, "screenshots_storage": storage}

    @app.put("/api/rules/{key}")
    def put_rule(key: str, body: RuleUpdate) -> dict[str, str]:
        safe = key.strip().lower()
        if body.kind == "site":
            db.set_site_rule(safe, body.category)
            return {"kind": "site", "key": safe, "category": body.category}
        db.set_app_rule(safe, body.category)
        return {"kind": "app", "key": safe, "category": body.category}

    @app.delete("/api/rules/{key}")
    def delete_rule(key: str, kind: str = Query(default="app")) -> dict[str, Any]:
        safe = key.strip().lower()
        if kind == "site":
            db.delete_site_rule(safe)
        else:
            db.delete_app_rule(safe)
        return {"ok": True, "kind": kind, "key": safe}

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
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass


def autostart_command() -> str:
    """Command written to HKCU Run when 'Start with Windows' is enabled."""
    import os
    import sys

    desktop = (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Programs"
        / "Deskline"
        / "deskline-desktop.exe"
    )
    if desktop.is_file():
        return f'"{desktop}"'
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --no-browser'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pythonw if pythonw.exists() else sys.executable)
    return f'"{exe}" -m deskline --no-browser'


def open_dashboard() -> None:
    webbrowser.open(BASE_URL)


__all__ = ["create_app", "open_dashboard", "HOST", "PORT"]
