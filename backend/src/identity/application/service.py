from __future__ import annotations

import time

import jwt

from identity.application.repositories import SessionRepository
from identity.domain.model import AppSession, AuthProvider, UserRole
from shared.kernel import ForbiddenError, NotFoundError


class IdentityService:
    def __init__(self, sessions: SessionRepository) -> None:
        self._sessions = sessions

    def dev_login(self, nickname: str, role: UserRole) -> AppSession:
        session = AppSession.create(
            external_user_id=f"dev:{nickname}",
            nickname=nickname,
            role=role,
            provider=AuthProvider.DEV,
        )
        self._sessions.save(session)
        return session

    def geekclass_login_by_token(
        self,
        token: str,
        jwt_secret: str,
        max_age_seconds: int = 60,
    ) -> AppSession:
        try:
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        except Exception as exc:
            raise ForbiddenError(f"Invalid GeekClass token: {exc}") from exc

        iat_raw = payload.get("iat")
        iat = int(iat_raw) if isinstance(iat_raw, (int, float, str)) and str(iat_raw).isdigit() else 0
        if time.time() - iat > max_age_seconds:
            raise ForbiddenError("GeekClass token expired")

        external_id = str(payload.get("id") or "").strip()
        if not external_id:
            raise ForbiddenError("GeekClass token does not contain user id")
        nickname = str(payload.get("name") or "Unknown").strip() or "Unknown"
        role_raw = str(payload.get("role") or "student").strip().lower()
        role = _parse_role(role_raw)

        session = AppSession.create(
            external_user_id=external_id,
            nickname=nickname,
            role=role,
            provider=AuthProvider.GEEKCLASS,
        )
        self._sessions.save(session)
        return session

    def get_session(self, session_id: str) -> AppSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise NotFoundError("Сессия не найдена")
        return session

    def logout(self, session_id: str) -> None:
        self._sessions.delete(session_id)


def _parse_role(value: str) -> UserRole:
    if value == UserRole.ADMIN.value:
        return UserRole.ADMIN
    if value == UserRole.TEACHER.value:
        return UserRole.TEACHER
    return UserRole.STUDENT
