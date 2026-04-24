from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.kernel import (
    ConflictError,
    DomainError,
    ExternalServiceError,
    ForbiddenError,
    InvariantViolationError,
    NotFoundError,
    UnauthorizedError,
)


_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    InvariantViolationError: 422,
    UnauthorizedError: 401,
    ForbiddenError: 403,
    ExternalServiceError: 503,
}


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        status_code = 400
        for error_type, code in _STATUS_BY_ERROR.items():
            if isinstance(exc, error_type):
                status_code = code
                break

        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )
