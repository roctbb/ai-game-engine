from __future__ import annotations


class DomainError(Exception):
    """Base domain/application error with stable machine code."""

    code = "domain_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    code = "not_found"


class ConflictError(DomainError):
    code = "conflict"


class InvariantViolationError(DomainError):
    code = "invariant_violation"


class ForbiddenError(DomainError):
    code = "forbidden"


class ExternalServiceError(DomainError):
    code = "external_service_error"
