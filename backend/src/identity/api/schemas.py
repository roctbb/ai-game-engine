from __future__ import annotations

from pydantic import BaseModel, Field

from identity.domain.model import AuthProvider, UserRole


class DevLoginRequest(BaseModel):
    nickname: str = Field(min_length=2, max_length=120)
    role: UserRole


class SessionResponse(BaseModel):
    session_id: str
    external_user_id: str
    nickname: str
    role: UserRole
    provider: AuthProvider


class AuthOptionsResponse(BaseModel):
    dev_login_enabled: bool
    geekclass_enabled: bool


class LogoutResponse(BaseModel):
    status: str
