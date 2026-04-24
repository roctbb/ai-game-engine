from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from shared.kernel import new_id, utc_now


class UserRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class AuthProvider(StrEnum):
    DEV = "dev"
    GEEKCLASS = "geekclass"


@dataclass(frozen=True, slots=True)
class AppSession:
    session_id: str
    external_user_id: str
    nickname: str
    role: UserRole
    provider: AuthProvider
    created_at: object

    @staticmethod
    def create(
        external_user_id: str,
        nickname: str,
        role: UserRole,
        provider: AuthProvider,
    ) -> "AppSession":
        return AppSession(
            session_id=new_id("devsess"),
            external_user_id=external_user_id,
            nickname=nickname,
            role=role,
            provider=provider,
            created_at=utc_now(),
        )
