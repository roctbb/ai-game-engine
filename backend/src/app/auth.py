from __future__ import annotations

from typing import Callable

from fastapi import Depends, Header, Request

from app.dependencies import ServiceContainer, get_container
from identity.domain.model import AppSession, UserRole
from shared.config.settings import settings
from shared.kernel import ForbiddenError, UnauthorizedError


def _extract_session_header(request: Request, explicit_header: str | None) -> str:
    if explicit_header:
        return explicit_header
    fallback = request.headers.get('X-Dev-Session')
    if fallback:
        return fallback
    query_session = request.query_params.get('session_id')
    if query_session:
        return query_session
    raise UnauthorizedError('Не передан заголовок X-Session-Id')


def get_current_session(
    request: Request,
    x_session_id: str | None = Header(default=None, alias='X-Session-Id'),
    container: ServiceContainer = Depends(get_container),
) -> AppSession:
    session_id = _extract_session_header(request, x_session_id)
    return container.identity.get_session(session_id)


def require_roles(*allowed_roles: UserRole) -> Callable[[AppSession], AppSession]:
    allowed = set(allowed_roles)

    def _dependency(session: AppSession = Depends(get_current_session)) -> AppSession:
        if session.role not in allowed:
            accepted = ', '.join(sorted(role.value for role in allowed))
            raise ForbiddenError(f'Доступ разрешен только для ролей: {accepted}')
        return session

    return _dependency


def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias='X-Internal-Token'),
) -> None:
    expected = settings.internal_api_token.strip()
    if not expected:
        raise ForbiddenError('Internal API token is not configured')
    if x_internal_token != expected:
        raise UnauthorizedError('Не передан или неверен X-Internal-Token')
