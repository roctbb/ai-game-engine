from __future__ import annotations

from urllib.parse import quote, urlencode, urlparse

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import RedirectResponse

from app.dependencies import ServiceContainer, get_container
from identity.api.schemas import AuthOptionsResponse, DevLoginRequest, LogoutResponse, SessionResponse
from shared.config.settings import settings
from shared.kernel import InvariantViolationError

router = APIRouter(tags=["identity"])


def _to_session_response(session: object) -> SessionResponse:
    from identity.domain.model import AppSession

    typed = session if isinstance(session, AppSession) else None
    assert typed is not None
    return SessionResponse(
        session_id=typed.session_id,
        external_user_id=typed.external_user_id,
        nickname=typed.nickname,
        role=typed.role,
        provider=typed.provider,
    )


def _sanitize_next_url(next_url: str | None) -> str:
    raw = (next_url or "").strip()
    if not raw:
        return "/"

    frontend_base = settings.frontend_url.rstrip("/")
    frontend_netloc = urlparse(frontend_base).netloc
    parsed = urlparse(raw)
    if parsed.scheme or parsed.netloc:
        if parsed.netloc and parsed.netloc != frontend_netloc:
            return "/"
        path = parsed.path or "/"
        if not path.startswith("/"):
            path = "/" + path
        if parsed.query:
            path = f"{path}?{parsed.query}"
        if parsed.fragment:
            path = f"{path}#{parsed.fragment}"
        return path

    if not raw.startswith("/"):
        return "/"
    return raw


def _frontend_redirect(next_path: str, session_id: str | None = None) -> RedirectResponse:
    frontend_base = settings.frontend_url.rstrip("/")
    target = next_path or "/"
    if session_id:
        separator = "&" if "?" in target else "?"
        target = f"{target}{separator}{urlencode({'session_id': session_id})}"
    if target == "/":
        return RedirectResponse(frontend_base)
    return RedirectResponse(frontend_base + target)


def _extract_session_header(request: Request, explicit_header: str | None) -> str:
    if explicit_header:
        return explicit_header
    fallback = request.headers.get("X-Dev-Session")
    if fallback:
        return fallback
    raise InvariantViolationError("Не передан заголовок X-Session-Id")


@router.get("/auth/options", response_model=AuthOptionsResponse)
def auth_options() -> AuthOptionsResponse:
    return AuthOptionsResponse(
        dev_login_enabled=settings.enable_dev_login,
        geekclass_enabled=settings.enable_geekclass_login,
    )


@router.post("/auth/login/geekclass", response_model=SessionResponse)
def login_geekclass(
    request: Request,
    token_query: str | None = Query(default=None, alias="token"),
    container: ServiceContainer = Depends(get_container),
) -> SessionResponse:
    if not settings.enable_geekclass_login:
        raise InvariantViolationError("GeekClass login disabled")

    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else token_query
    if not token:
        raise InvariantViolationError("Missing token")

    session = container.identity.geekclass_login_by_token(
        token=token,
        jwt_secret=settings.jwt_secret,
        max_age_seconds=settings.jwt_max_age_seconds,
    )
    return _to_session_response(session)


@router.get("/auth/login")
def login_redirect(next_url: str | None = Query(default=None, alias="next")) -> RedirectResponse:
    if not settings.enable_geekclass_login:
        raise InvariantViolationError("GeekClass login disabled")
    next_path = _sanitize_next_url(next_url)
    backend_base = settings.backend_url.rstrip("/")
    callback_url = backend_base + "/api/v1/auth/callback?next=" + quote(next_path, safe="")
    geekclass_host = settings.geekclass_host.rstrip("/")
    jwt_url = geekclass_host + "/insider/jwt?redirect_url=" + quote(callback_url, safe="")
    return RedirectResponse(jwt_url)


@router.get("/auth/callback")
def login_callback(
    token: str | None = Query(default=None),
    next_url: str | None = Query(default=None, alias="next"),
    container: ServiceContainer = Depends(get_container),
) -> RedirectResponse:
    next_path = _sanitize_next_url(next_url)
    if not token:
        return _frontend_redirect(next_path)
    try:
        session = container.identity.geekclass_login_by_token(
            token=token,
            jwt_secret=settings.jwt_secret,
            max_age_seconds=settings.jwt_max_age_seconds,
        )
    except Exception:
        return _frontend_redirect(next_path)
    return _frontend_redirect(next_path, session_id=session.session_id)


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    container: ServiceContainer = Depends(get_container),
) -> LogoutResponse:
    session_id = _extract_session_header(request, x_session_id)
    container.identity.logout(session_id)
    return LogoutResponse(status="ok")


@router.post("/auth/dev-login", response_model=SessionResponse)
@router.post("/identity/dev-login", response_model=SessionResponse)
def dev_login(
    request: DevLoginRequest,
    container: ServiceContainer = Depends(get_container),
) -> SessionResponse:
    if not settings.enable_dev_login:
        raise InvariantViolationError("Dev login disabled")
    session = container.identity.dev_login(nickname=request.nickname, role=request.role)
    return _to_session_response(session)


@router.get("/me", response_model=SessionResponse)
@router.get("/identity/me", response_model=SessionResponse)
def me(
    request: Request,
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    container: ServiceContainer = Depends(get_container),
) -> SessionResponse:
    session_id = _extract_session_header(request, x_session_id)
    session = container.identity.get_session(session_id)
    return _to_session_response(session)
