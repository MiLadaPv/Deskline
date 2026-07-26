from __future__ import annotations

import json
import urllib.parse
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
    SESSION_TTL_REMEMBER_SEC,
    authenticate,
    change_password,
    create_session_token,
    ensure_recovery_code,
    google_email,
    has_recovery_code,
    is_auth_configured,
    is_google_linked,
    is_password_set,
    is_public_path,
    link_google_account,
    register_user,
    reset_password_with_recovery,
    session_username,
    setup_with_google,
    unlink_google_account,
    username_exists,
    username_for_google_sub,
    validate_session_token,
    verify_google_sub,
)
from deskline.google_oauth import (
    OAUTH_STATE_COOKIE,
    build_authorize_url,
    exchange_code,
    is_google_oauth_configured,
    load_google_oauth_config,
    make_oauth_state,
    make_pkce_pair,
    pop_oauth_pending,
    redirect_uri,
    resolve_google_identity,
    save_oauth_pending,
)
from deskline.capture import resolve_screenshot_file, screenshots_storage_info
from deskline.config import (
    APP_NAME,
    BASE_URL,
    HOST,
    PORT,
    ICONS_DIR,
    SUPPORT_EMAIL,
    WEB_ROOT,
    brand_template_context,
    ensure_screenshots_dir,
    get_screenshots_dir,
    load_config,
    save_config,
)
from deskline.db import Database, ProjectNameExists, parse_iso_datetime
from deskline.entitlements import (
    FREE_HISTORY_DAYS,
    FREE_MAX_PROJECTS,
    ensure_first_run,
    entitlements_public_dict,
    resolve_entitlements,
)
from deskline.license_client import activate_license, current_license, deactivate_local
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
    theme: str | None = Field(default=None, pattern="^(system|light|dark)$")
    company_mode: bool | None = None
    company_display_name: str | None = Field(default=None, max_length=120)
    listen_host: str | None = Field(default=None, max_length=64)
    hub_url: str | None = Field(default=None, max_length=300)
    hub_ingest_token: str | None = Field(default=None, max_length=200)
    rdp_vision_enabled: bool | None = None
    rdp_vision_consent: bool | None = None
    rdp_vision_api_key: str | None = Field(default=None, max_length=500)
    rdp_vision_interval_sec: int | None = Field(default=None, ge=120, le=300)
    rdp_vision_base_url: str | None = Field(default=None, max_length=300)
    rdp_vision_model: str | None = Field(default=None, max_length=120)


class EmployeeCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="member", pattern="^(admin|member)$")


class EmployeeUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    active: bool | None = None
    role: str | None = Field(default=None, pattern="^(admin|member)$")


class IngestSessionItem(BaseModel):
    app_name: str = Field(min_length=1, max_length=260)
    window_title: str = ""
    url_hint: str | None = None
    started_at: str
    ended_at: str | None = None
    duration_sec: float = 0
    category: str = "neutral"
    display_name: str | None = None
    activity_kind: str | None = None
    activity_label: str | None = None
    app_path: str | None = None
    idle_sec: float = 0
    project_id: int | None = None
    task_id: int | None = None
    ingest_key: str | None = None


class IngestBody(BaseModel):
    hostname: str | None = Field(default=None, max_length=120)
    sessions: list[IngestSessionItem] = Field(default_factory=list, max_length=500)


class LicenseActivateBody(BaseModel):
    key: str = Field(min_length=4, max_length=200)


class FunnelEventBody(BaseModel):
    event: str = Field(min_length=2, max_length=64)
    meta: dict[str, Any] | None = None


class OnboardingBody(BaseModel):
    done: bool = True


class RdpVisionConfirmBody(BaseModel):
    label: str | None = Field(default=None, max_length=80)
    session_id: int | None = None


class ExtensionEventBody(BaseModel):
    """Browser-extension tab heartbeat / closed segment."""

    url: str = Field(default="", max_length=2000)
    title: str = Field(default="", max_length=500)
    host: str | None = Field(default=None, max_length=260)
    started_at: str | None = None
    ended_at: str | None = None
    duration_sec: float = Field(default=0, ge=0, le=86_400)


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
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=4, max_length=128)
    remember: bool = False


class RecoverPasswordBody(BaseModel):
    username: str = Field(default="", max_length=32)
    recovery_code: str = Field(min_length=8, max_length=64)
    new_password: str = Field(min_length=4, max_length=128)
    remember: bool = False


class ChangePasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=4, max_length=128)


def _set_session_cookie(response: Response, token: str, *, remember: bool = False) -> None:
    # Default: session cookie (cleared when the browser is closed).
    # Remember me: persist for SESSION_TTL_REMEMBER_SEC.
    kwargs: dict[str, Any] = {
        "key": COOKIE_NAME,
        "value": token,
        "httponly": True,
        "samesite": "strict",
        "path": "/",
    }
    if remember:
        kwargs["max_age"] = SESSION_TTL_REMEMBER_SEC
    response.set_cookie(**kwargs)


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
        auth_ready = is_auth_configured()

        if not auth_ready:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "password setup required"}, status_code=401)
            return RedirectResponse(url="/login", status_code=303)

        if not authed:
            if path.startswith("/api/") or path.startswith("/media/"):
                return JSONResponse({"detail": "authentication required"}, status_code=401)
            return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)


def _load_entitlements():
    cfg = load_config()
    stamped = ensure_first_run(cfg)
    if stamped.get("first_run_at") != cfg.get("first_run_at"):
        cfg = save_config(stamped)
    return resolve_entitlements(cfg, current_license()), cfg


def _pro_required(feature: str) -> None:
    ent, _ = _load_entitlements()
    if ent.is_pro:
        return
    raise HTTPException(
        status_code=402,
        detail={
            "code": "pro_required",
            "feature": feature,
            "message": "Доступно в Deskline Pro",
            "entitlements": entitlements_public_dict(ent),
        },
    )


def _team_required(feature: str) -> None:
    ent, _ = _load_entitlements()
    if ent.is_team:
        return
    raise HTTPException(
        status_code=402,
        detail={
            "code": "team_required",
            "feature": feature,
            "message": "Режим компании доступен в Deskline Team — активируйте ключ Team",
            "entitlements": entitlements_public_dict(ent),
        },
    )


def _assert_day_allowed(day: date) -> None:
    ent, _ = _load_entitlements()
    if ent.day_allowed(day):
        return
    raise HTTPException(
        status_code=402,
        detail={
            "code": "history_limit",
            "feature": "history",
            "message": f"На Free доступны последние {FREE_HISTORY_DAYS} дней",
            "entitlements": entitlements_public_dict(ent),
        },
    )


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
            brand_template_context(),
        )

    @app.get("/welcome", response_class=HTMLResponse)
    def welcome_page(request: Request) -> HTMLResponse:
        try:
            from deskline.funnel import record_funnel_event

            record_funnel_event("welcome_view")
        except Exception:
            pass
        return templates.TemplateResponse(
            request,
            "welcome.html",
            brand_template_context(),
        )

    @app.get("/docs/compare", response_class=HTMLResponse)
    def compare_page(request: Request) -> HTMLResponse:
        ctx = brand_template_context()
        ctx["compare_cards"] = [
            {
                "title": "vs Time Doctor / Hubstaff",
                "body": "Та же идея фокуса и картины дня, но активность не обязана жить в облаке вендора.",
            },
            {
                "title": "vs RescueTime",
                "body": "Личная продуктивность плюс нативный Windows desktop, проекты и Team LAN hub.",
            },
            {
                "title": "vs Yaware / Kickidler",
                "body": "Не видеоэкрана и не DLP — мягкий учёт фокуса для себя и маленькой команды.",
            },
            {
                "title": "vs Toggl / Clockify",
                "body": "Автотрекинг активного окна, а не ручные таймшиты и биллинг.",
            },
        ]
        return templates.TemplateResponse(request, "compare.html", ctx)

    @app.get("/logos", response_class=HTMLResponse)
    def logos_page(request: Request) -> HTMLResponse:
        from deskline.logo_gallery import load_logo_cards

        ctx = brand_template_context()
        ctx["logo_cards"] = load_logo_cards()
        return templates.TemplateResponse(
            request,
            "logos.html",
            ctx,
        )

    @app.get("/about", response_class=HTMLResponse)
    def about_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "about.html",
            brand_template_context(),
        )

    @app.get("/privacy", response_class=HTMLResponse)
    def privacy_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "privacy.html",
            brand_template_context(),
        )

    @app.get("/terms", response_class=HTMLResponse)
    def terms_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "terms.html",
            brand_template_context(),
        )

    @app.get("/api/auth/status")
    def auth_status(request: Request) -> dict[str, Any]:
        token = request.cookies.get(COOKIE_NAME)
        user = session_username(token)
        return {
            "password_set": is_password_set(),
            "auth_configured": is_auth_configured(),
            "authenticated": validate_session_token(token),
            "username": user,
            "has_recovery": has_recovery_code(user) if user else has_recovery_code(),
            "google_configured": is_google_oauth_configured(),
            "google_linked": is_google_linked(user) if user else is_google_linked(),
            "google_email": google_email(user) if user else google_email(),
            "google_redirect_uri": redirect_uri() if is_google_oauth_configured() else None,
            "support_email": SUPPORT_EMAIL,
        }

    def _oauth_error_redirect(message: str) -> RedirectResponse:
        q = urllib.parse.urlencode({"google_error": message})
        return RedirectResponse(url=f"/login?{q}", status_code=303)

    def _google_error_message(error: str, description: str | None = None) -> str:
        err = (error or "").strip().lower()
        desc = (description or "").strip()
        if err == "redirect_uri_mismatch" or "redirect_uri" in desc.lower():
            return (
                "Google отклонил redirect URI. В Google Cloud → Clients добавьте: "
                f"{redirect_uri()}"
            )
        if err in {"access_denied", "consent_required"}:
            return "Вход через Google отменён"
        if desc:
            return f"Google: {desc[:180]}"
        return "Вход через Google не удался"

    @app.get("/api/auth/google/start")
    def auth_google_start(request: Request, bind: int = 0) -> Response:
        cfg = load_google_oauth_config()
        if cfg is None:
            raise HTTPException(400, "Google OAuth не настроен")
        want_bind = bool(bind)
        if want_bind and not validate_session_token(request.cookies.get(COOKIE_NAME)):
            raise HTTPException(401, "Сначала войдите паролем, чтобы привязать Google")
        sess_user = session_username(request.cookies.get(COOKIE_NAME))
        if not want_bind and is_password_set() and not is_google_linked(sess_user):
            return _oauth_error_redirect(
                "Сначала войдите паролем, затем Настройки → Привязать Google"
            )
        state = make_oauth_state()
        verifier, challenge = make_pkce_pair()
        save_oauth_pending(state, verifier=verifier, bind=want_bind)
        payload = json.dumps(
            {"state": state, "verifier": verifier, "bind": want_bind},
            separators=(",", ":"),
        )
        url = build_authorize_url(cfg, state=state, code_challenge=challenge)
        response = RedirectResponse(url=url, status_code=303)
        response.set_cookie(
            key=OAUTH_STATE_COOKIE,
            value=payload,
            httponly=True,
            samesite="lax",
            path="/",
            max_age=600,
        )
        return response

    @app.get("/api/auth/google/callback")
    def auth_google_callback(
        request: Request,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
        error_description: str | None = None,
    ) -> Response:
        if error:
            return _oauth_error_redirect(_google_error_message(error, error_description))
        if not code or not state:
            return _oauth_error_redirect(
                "Некорректный ответ Google. Проверьте redirect URI: "
                f"{redirect_uri()}"
            )

        pending = pop_oauth_pending(state)
        raw_cookie = request.cookies.get(OAUTH_STATE_COOKIE) or ""
        try:
            cookie_meta = json.loads(raw_cookie) if raw_cookie else {}
        except json.JSONDecodeError:
            cookie_meta = {}
        if not isinstance(cookie_meta, dict):
            cookie_meta = {}

        meta = pending if isinstance(pending, dict) else None
        if meta is None and cookie_meta.get("state") == state:
            meta = cookie_meta
        if meta is None:
            return _oauth_error_redirect("Сессия Google устарела — попробуйте снова")

        verifier = str(meta.get("verifier") or "")
        want_bind = bool(meta.get("bind"))
        if not verifier:
            return _oauth_error_redirect("Сессия Google повреждена")

        cfg = load_google_oauth_config()
        if cfg is None:
            return _oauth_error_redirect("Google OAuth не настроен")

        try:
            tokens = exchange_code(cfg, code=code, code_verifier=verifier)
            sub, email = resolve_google_identity(tokens)
        except RuntimeError as exc:
            msg = str(exc)
            if "redirect_uri" in msg.lower():
                return _oauth_error_redirect(
                    "Google отклонил redirect URI. Добавьте в Clients: "
                    f"{redirect_uri()}"
                )
            return _oauth_error_redirect("Не удалось подтвердить аккаунт Google")

        recovery_code: str | None = None
        session_user = session_username(request.cookies.get(COOKIE_NAME))
        try:
            if want_bind:
                if not validate_session_token(request.cookies.get(COOKIE_NAME)):
                    return _oauth_error_redirect("Сначала войдите паролем")
                link_google_account(sub, email, username=session_user)
                login_as = session_user or ""
            elif verify_google_sub(sub):
                login_as = username_for_google_sub(sub) or session_user or ""
            elif not is_auth_configured():
                recovery_code = setup_with_google(sub, email)
                login_as = username_for_google_sub(sub) or ""
            elif is_google_linked():
                return _oauth_error_redirect("Этот Google-аккаунт не привязан")
            else:
                return _oauth_error_redirect(
                    "Привяжите Google в Настройках после входа по паролю"
                )
        except PermissionError:
            return _oauth_error_redirect("Уже привязан другой Google-аккаунт")
        except ValueError as exc:
            return _oauth_error_redirect(str(exc) or "Аккаунт уже настроен")

        token = create_session_token(login_as, remember=True)
        if recovery_code:
            q = urllib.parse.urlencode({"google_recovery": recovery_code})
            response = RedirectResponse(url=f"/login?{q}", status_code=303)
        elif want_bind:
            response = RedirectResponse(url="/#settings", status_code=303)
        else:
            response = RedirectResponse(url="/", status_code=303)
        _set_session_cookie(response, token, remember=True)
        response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
        return response

    @app.post("/api/auth/google/unlink")
    def auth_google_unlink(request: Request) -> dict[str, Any]:
        if not validate_session_token(request.cookies.get(COOKIE_NAME)):
            raise HTTPException(401, "authentication required")
        user = session_username(request.cookies.get(COOKIE_NAME))
        if not is_password_set():
            raise HTTPException(
                400,
                "Сначала задайте пароль — иначе нельзя отвязать единственный способ входа",
            )
        unlink_google_account(username=user)
        return {"ok": True, "google_linked": False}

    @app.post("/api/auth/setup")
    def auth_setup(body: PasswordBody) -> Response:
        try:
            if username_exists(body.username):
                raise HTTPException(400, "Логин уже зарегистрирован")
            recovery_code = register_user(body.username, body.password, issue_recovery=True)
        except HTTPException:
            raise
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        token = create_session_token(body.username, remember=body.remember)
        response = JSONResponse({"ok": True, "recovery_code": recovery_code})
        _set_session_cookie(response, token, remember=body.remember)
        return response

    @app.post("/api/auth/login")
    def auth_login(body: PasswordBody) -> Response:
        try:
            user = authenticate(body.username, body.password)
        except LookupError as exc:
            raise HTTPException(401, str(exc) or "Такого логина нет") from exc
        except PermissionError as exc:
            raise HTTPException(401, str(exc) or "Неверный пароль") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        issued = ensure_recovery_code(user)
        token = create_session_token(user, remember=body.remember)
        payload: dict[str, Any] = {"ok": True, "has_recovery": True, "username": user}
        if issued:
            payload["recovery_code"] = issued
        response = JSONResponse(payload)
        _set_session_cookie(response, token, remember=body.remember)
        return response

    @app.post("/api/auth/recover")
    def auth_recover(body: RecoverPasswordBody) -> Response:
        try:
            recovery_code = reset_password_with_recovery(
                body.recovery_code,
                body.new_password,
                username=body.username or None,
            )
        except LookupError as exc:
            raise HTTPException(401, str(exc) or "Такого логина нет") from exc
        except PermissionError as exc:
            raise HTTPException(401, "Неверный код восстановления") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        user = (body.username or "").strip().lower()
        token = create_session_token(user, remember=body.remember)
        response = JSONResponse({"ok": True, "recovery_code": recovery_code})
        _set_session_cookie(response, token, remember=body.remember)
        return response

    @app.post("/api/auth/logout")
    def auth_logout() -> Response:
        response = JSONResponse({"ok": True})
        _clear_session_cookie(response)
        return response

    @app.post("/api/auth/change-password")
    def auth_change_password(request: Request, body: ChangePasswordBody) -> dict[str, Any]:
        user = session_username(request.cookies.get(COOKIE_NAME))
        try:
            recovery_code = change_password(
                body.current_password,
                body.new_password,
                username=user,
            )
        except PermissionError as exc:
            raise HTTPException(401, "Неверный текущий пароль") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"ok": True, "recovery_code": recovery_code}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            brand_template_context(),
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

    @app.get("/api/extension/status")
    def extension_status() -> dict[str, Any]:
        """Public probe for the Chrome extension (desktop available?)."""
        st = tracker.status()
        return {
            "ok": True,
            "app": APP_NAME,
            "version": __version__,
            "desktop": True,
            "recording": bool(st.get("recording")),
            "paused": bool(st.get("paused")),
            "download_hint": "Install Deskline Desktop for full app + screenshot tracking.",
        }

    @app.post("/api/extension/event")
    def extension_event(body: ExtensionEventBody) -> dict[str, Any]:
        """Accept a browser tab segment from the Chrome extension when Desktop is running."""
        from urllib.parse import urlparse

        from deskline.classify import resolve_activity

        host = (body.host or "").strip().lower()
        if not host and body.url:
            try:
                host = (urlparse(body.url).hostname or "").lower()
            except Exception:
                host = ""
        title = (body.title or host or "Browser").strip()[:500]
        url_hint = host or None
        user_apps = db.get_app_rules()
        user_sites = db.get_site_rules()
        meta = resolve_activity("chrome.exe", title, url_hint, user_apps, user_sites)
        started = parse_iso_datetime(body.started_at) if body.started_at else None
        ended = parse_iso_datetime(body.ended_at) if body.ended_at else None
        duration = float(body.duration_sec or 0)
        if duration <= 0 and started and ended:
            duration = max(0.0, (ended - started).total_seconds())
        if duration < 1.0:
            return {"ok": True, "ignored": True, "reason": "too_short"}
        sid = db.start_session(
            app_name="chrome.exe",
            window_title=title,
            url_hint=url_hint,
            category=meta.get("category") or "neutral",
            started_at=started,
            display_name=meta.get("display_name"),
            activity_kind=meta.get("activity_kind") or "site",
            activity_label=meta.get("activity_label") or host or title,
            app_path=None,
            ingest_key=f"extension:{host}:{body.started_at or ''}",
        )
        if ended is not None:
            db.end_session(sid, ended_at=ended)
        elif duration > 0 and started is not None:
            from datetime import timedelta

            db.end_session(sid, ended_at=started + timedelta(seconds=duration))
        else:
            db.end_session(sid)
        return {"ok": True, "session_id": sid}

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        st = tracker.status()
        st["version"] = __version__
        st["app"] = APP_NAME
        ent, _ = _load_entitlements()
        st["entitlements"] = entitlements_public_dict(ent)
        return st

    @app.get("/api/summary/today")
    def summary_today(
        project_id: int | None = None,
        task_id: int | None = None,
        employee_id: int | None = None,
    ) -> dict[str, Any]:
        return db.summary_for_day(
            date.today(),
            project_id=project_id,
            task_id=task_id,
            employee_id=employee_id,
        )

    @app.get("/api/summary")
    def summary_range_api(
        from_ts: str | None = Query(default=None, alias="from"),
        to: str | None = None,
        project_id: int | None = None,
        task_id: int | None = None,
        employee_id: int | None = None,
    ) -> dict[str, Any]:
        start, end = _range(from_ts, to)
        _assert_day_allowed(start.date())
        _assert_day_allowed(end.date())
        return db.summary_range(
            start, end, project_id=project_id, task_id=task_id, employee_id=employee_id
        )

    @app.get("/api/trends")
    def trends(
        days: int = 7,
        project_id: int | None = None,
        task_id: int | None = None,
        employee_id: int | None = None,
    ) -> list[dict[str, Any]]:
        ent, _ = _load_entitlements()
        max_days = ent.history_days or 31
        days = max(1, min(int(days), min(31, max_days)))
        return db.daily_trends(
            days=days, project_id=project_id, task_id=task_id, employee_id=employee_id
        )

    @app.get("/api/timeline/today")
    def timeline_today(employee_id: int | None = None) -> list[dict[str, Any]]:
        return db.timeline_for_day(date.today(), employee_id=employee_id)

    @app.get("/api/timeline")
    def timeline(
        day: str | None = Query(default=None, description="YYYY-MM-DD local calendar day"),
        employee_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if not day:
            return db.timeline_for_day(date.today(), employee_id=employee_id)
        try:
            target = date.fromisoformat(day)
        except ValueError as exc:
            raise HTTPException(400, "Invalid day; use YYYY-MM-DD") from exc
        _assert_day_allowed(target)
        return db.timeline_for_day(target, employee_id=employee_id)

    @app.get("/api/projects")
    def projects(include_archived: bool = False) -> list[dict[str, Any]]:
        return db.list_projects(include_archived=include_archived)

    @app.post("/api/projects")
    def create_project(body: ProjectCreate) -> dict[str, Any]:
        ent, _ = _load_entitlements()
        if ent.max_projects is not None:
            active = [p for p in db.list_projects(include_archived=False) if not p.get("archived")]
            if len(active) >= ent.max_projects:
                raise HTTPException(
                    status_code=402,
                    detail={
                        "code": "project_limit",
                        "feature": "projects",
                        "message": f"На Free — до {FREE_MAX_PROJECTS} проектов. Оформите Pro.",
                        "entitlements": entitlements_public_dict(ent),
                    },
                )
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
        _assert_day_allowed(start.date())
        return db.apps_range(start, end, project_id=project_id, task_id=task_id)

    @app.get("/api/sites")
    def sites(
        from_ts: str | None = Query(default=None, alias="from"),
        to: str | None = None,
        project_id: int | None = None,
        task_id: int | None = None,
    ) -> list[dict[str, Any]]:
        start, end = _range(from_ts, to)
        _assert_day_allowed(start.date())
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
        _pro_required("screenshots")
        d = date.fromisoformat(day) if day else date.today()
        _assert_day_allowed(d)
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
                    from deskline.icons import recalled_app_path

                    path = ensure_app_icon(stem, recalled_app_path(stem))
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
        ent, cfg = _load_entitlements()
        storage = screenshots_storage_info()
        return {
            **cfg,
            "screenshots_path": storage["path"],
            "screenshots_storage": storage,
            "screenshots_dir_effective": str(get_screenshots_dir(cfg)),
            "entitlements": entitlements_public_dict(ent),
        }

    @app.put("/api/settings")
    def put_settings(body: SettingsUpdate) -> dict[str, Any]:
        ent, cfg = _load_entitlements()
        data = body.model_dump(exclude_none=True)
        if "screenshots_dir" in data:
            data["screenshots_dir"] = _validate_screenshots_dir(str(data["screenshots_dir"]))
        if data.get("screenshots_enabled") and not ent.screenshots:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "pro_required",
                    "feature": "screenshots",
                    "message": "Скриншоты доступны в Pro / trial",
                    "entitlements": entitlements_public_dict(ent),
                },
            )
        if data.get("company_mode") and not ent.company_hub:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "team_required",
                    "feature": "company_hub",
                    "message": "LAN hub доступен в Deskline Team — активируйте ключ Team",
                    "entitlements": entitlements_public_dict(ent),
                },
            )
        if "company_mode" in data:
            if data["company_mode"]:
                data.setdefault("listen_host", "0.0.0.0")
                if not str(data.get("company_display_name") or cfg.get("company_display_name") or "").strip():
                    data["company_display_name"] = "Команда"
                db.ensure_default_employee()
            elif "listen_host" not in data:
                data["listen_host"] = "127.0.0.1"
        if "listen_host" in data:
            host = str(data["listen_host"] or "").strip() or "127.0.0.1"
            if host not in {"127.0.0.1", "0.0.0.0", "localhost"}:
                raise HTTPException(400, "listen_host: используйте 127.0.0.1 или 0.0.0.0")
            data["listen_host"] = "127.0.0.1" if host == "localhost" else host
        if "hub_url" in data:
            data["hub_url"] = str(data["hub_url"] or "").strip().rstrip("/")
        if data.get("rdp_vision_enabled"):
            if not ent.is_pro:
                raise HTTPException(
                    status_code=402,
                    detail={
                        "code": "pro_required",
                        "feature": "rdp_vision",
                        "message": "RDP vision доступен в Pro",
                        "entitlements": entitlements_public_dict(ent),
                    },
                )
            consent = data.get("rdp_vision_consent", cfg.get("rdp_vision_consent"))
            key = str(data.get("rdp_vision_api_key", cfg.get("rdp_vision_api_key") or "")).strip()
            if not consent or not key:
                raise HTTPException(
                    400,
                    "Для RDP vision нужны явное согласие и ваш API-ключ",
                )
        if "rdp_vision_interval_sec" in data and data["rdp_vision_interval_sec"] is not None:
            data["rdp_vision_interval_sec"] = max(120, min(300, int(data["rdp_vision_interval_sec"])))
        cfg.update(data)
        saved = save_config(cfg)
        ensure_screenshots_dir(saved)
        tracker.reload_config()
        if "autostart" in data:
            _set_autostart(bool(saved.get("autostart")))
        storage = screenshots_storage_info()
        ent2, _ = _load_entitlements()
        return {
            **saved,
            "screenshots_path": storage["path"],
            "screenshots_storage": storage,
            "screenshots_dir_effective": str(get_screenshots_dir(saved)),
            "restart_required_for_bind": True,
            "entitlements": entitlements_public_dict(ent2),
        }

    @app.get("/api/company")
    def company_status() -> dict[str, Any]:
        ent, cfg = _load_entitlements()
        employees = db.list_employees()
        return {
            "company_mode": bool(cfg.get("company_mode")),
            "company_display_name": cfg.get("company_display_name") or "",
            "listen_host": cfg.get("listen_host") or HOST,
            "port": PORT,
            "local_employee_id": cfg.get("local_employee_id"),
            "employees": employees,
            "devices": db.list_devices(),
            "hub_url": cfg.get("hub_url") or "",
            "has_hub_token": bool(str(cfg.get("hub_ingest_token") or "").strip()),
            "entitlements": entitlements_public_dict(ent),
            "team_locked": not ent.company_hub,
        }

    @app.get("/api/company/team")
    def company_team(
        from_ts: str | None = Query(default=None, alias="from"),
        to: str | None = None,
        project_id: int | None = None,
        task_id: int | None = None,
    ) -> list[dict[str, Any]]:
        _team_required("company_hub")
        start, end = _range(from_ts, to)
        return db.team_summary(start, end, project_id=project_id, task_id=task_id)

    @app.get("/api/company/summary")
    def company_summary(
        from_ts: str | None = Query(default=None, alias="from"),
        to: str | None = None,
        project_id: int | None = None,
        task_id: int | None = None,
    ) -> dict[str, Any]:
        _team_required("company_hub")
        start, end = _range(from_ts, to)
        summary = db.summary_range(start, end, project_id=project_id, task_id=task_id)
        summary["team"] = db.team_summary(start, end, project_id=project_id, task_id=task_id)
        return summary

    @app.post("/api/company/employees")
    def company_create_employee(body: EmployeeCreate) -> dict[str, Any]:
        _team_required("company_hub")
        return db.create_employee(body.display_name, role=body.role)

    @app.put("/api/company/employees/{employee_id}")
    def company_update_employee(employee_id: int, body: EmployeeUpdate) -> dict[str, Any]:
        _team_required("company_hub")
        row = db.update_employee(
            employee_id,
            display_name=body.display_name,
            active=body.active,
            role=body.role,
        )
        if not row:
            raise HTTPException(404, "Employee not found")
        return row

    @app.post("/api/company/employees/{employee_id}/token")
    def company_rotate_token(employee_id: int) -> dict[str, Any]:
        _team_required("company_hub")
        row = db.rotate_employee_token(employee_id)
        if not row:
            raise HTTPException(404, "Employee not found")
        return row

    @app.post("/api/ingest/sessions")
    def ingest_sessions(request: Request, body: IngestBody) -> dict[str, Any]:
        auth = request.headers.get("Authorization") or ""
        token = ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if not token:
            token = (request.headers.get("X-Deskline-Token") or "").strip()
        if not token:
            raise HTTPException(401, "Missing ingest token")
        emp = db.find_employee_by_token(token)
        if not emp:
            raise HTTPException(401, "Invalid ingest token")
        sessions = [item.model_dump() for item in body.sessions]
        result = db.ingest_sessions(
            int(emp["id"]), sessions, hostname=body.hostname
        )
        return {"ok": True, "employee_id": emp["id"], **result}

    @app.post("/api/screenshots/purge")
    def purge_screenshots() -> dict[str, Any]:
        _pro_required("screenshots")
        result = tracker.purge_old_screenshots()
        storage = screenshots_storage_info()
        return {**result, "screenshots_storage": storage}

    @app.get("/api/license/status")
    def license_status() -> dict[str, Any]:
        ent, cfg = _load_entitlements()
        return {
            "entitlements": entitlements_public_dict(ent),
            "onboarding_done": bool(cfg.get("onboarding_done")),
            "first_run_at": cfg.get("first_run_at") or "",
            "version": __version__,
        }

    @app.post("/api/license/activate")
    def license_activate(body: LicenseActivateBody) -> dict[str, Any]:
        try:
            activate_license(body.key)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        ent, _ = _load_entitlements()
        try:
            from deskline.funnel import record_funnel_event

            if ent.is_team:
                record_funnel_event("team_activate")
            elif ent.is_pro:
                record_funnel_event("pro_activate")
        except Exception:
            pass
        return {"ok": True, "entitlements": entitlements_public_dict(ent)}

    @app.post("/api/funnel")
    def funnel_post(body: FunnelEventBody) -> dict[str, Any]:
        from deskline.funnel import record_funnel_event

        ok = record_funnel_event(body.event, body.meta)
        if not ok:
            raise HTTPException(400, "Unknown or failed funnel event")
        return {"ok": True}

    @app.get("/api/funnel")
    def funnel_get(limit: int = 50) -> dict[str, Any]:
        from deskline.funnel import read_funnel_tail

        return {"events": read_funnel_tail(limit)}

    @app.post("/api/license/deactivate")
    def license_deactivate() -> dict[str, Any]:
        deactivate_local()
        ent, _ = _load_entitlements()
        return {"ok": True, "entitlements": entitlements_public_dict(ent)}

    @app.get("/api/rdp-vision/pending")
    def rdp_vision_pending() -> dict[str, Any]:
        from deskline import rdp_vision

        return {"pending": rdp_vision.get_pending()}

    @app.post("/api/rdp-vision/confirm")
    def rdp_vision_confirm(body: RdpVisionConfirmBody | None = None) -> dict[str, Any]:
        _pro_required("rdp_vision")
        from deskline import rdp_vision

        pending = rdp_vision.get_pending()
        if not pending:
            raise HTTPException(404, "Нет предложения RDP vision")
        label = str((body.label if body else None) or pending["label"]).strip()
        sid = (body.session_id if body else None) or pending.get("session_id")
        ok = tracker.apply_rdp_vision_label(label, session_id=int(sid) if sid else None)
        rdp_vision.clear_pending()
        return {"ok": ok, "label": label, "status": tracker.status()}

    @app.post("/api/rdp-vision/skip")
    def rdp_vision_skip() -> dict[str, Any]:
        from deskline import rdp_vision

        rdp_vision.clear_pending()
        return {"ok": True}

    @app.post("/api/onboarding/complete")
    def onboarding_complete(body: OnboardingBody) -> dict[str, Any]:
        cfg = load_config()
        cfg = ensure_first_run(cfg)
        cfg["onboarding_done"] = bool(body.done)
        save_config(cfg)
        return {"ok": True, "onboarding_done": True}

    @app.get("/api/export/json")
    def export_json() -> Response:
        _pro_required("export")
        payload = {
            "app": APP_NAME,
            "version": __version__,
            "exported_at": datetime.now().astimezone().isoformat(),
            "config": {k: v for k, v in load_config().items() if k not in {"hub_ingest_token"}},
            "projects": db.list_projects(include_archived=True),
            "tasks": db.list_tasks(None),
            "trends": db.daily_trends(days=31),
        }
        raw = json.dumps(payload, ensure_ascii=False, indent=2)
        return Response(
            content=raw,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="deskline-export.json"'},
        )

    @app.get("/api/export/csv")
    def export_csv() -> Response:
        _pro_required("export")
        import csv
        import io

        rows = db.daily_trends(days=31)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["day", "total_sec", "active_sec", "idle_sec", "focus_pct", "productive_sec", "neutral_sec", "distracting_sec"]
        )
        for r in rows:
            cats = r.get("by_category") or {}
            writer.writerow(
                [
                    r.get("day"),
                    int(r.get("total_sec") or 0),
                    int(r.get("active_sec") or 0),
                    int(r.get("idle_sec") or 0),
                    r.get("focus_pct") or 0,
                    int(cats.get("productive") or 0),
                    int(cats.get("neutral") or 0),
                    int(cats.get("distracting") or 0),
                ]
            )
        return Response(
            content=buf.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="deskline-trends.csv"'},
        )

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
