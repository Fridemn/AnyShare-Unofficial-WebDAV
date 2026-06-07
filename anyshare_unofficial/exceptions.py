"""Custom exceptions for the AnyShare Unofficial API library."""

from __future__ import annotations


class AnyShareError(Exception):
    """Base exception for all AnyShare client errors."""

    def __init__(self, message: str, *args: object) -> None:
        super().__init__(message, *args)


class AnyShareNetworkError(AnyShareError):
    """Raised when a network-level error occurs (connection, timeout, etc.)."""

    def __init__(self, message: str, *, original: Exception | None = None) -> None:
        super().__init__(message)
        self.original = original


class AnyShareAuthError(AnyShareError):
    """Raised when authentication or authorization fails (401, 403)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AnyShareAPIError(AnyShareError):
    """Raised when the AnyShare server returns an API-level error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: int | None = None,
        cause_detail: str | None = None,
        response_body: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.cause_detail = cause_detail
        self.response_body = response_body or {}


class AnyShareInputError(AnyShareError):
    """Raised when the user provides invalid input (e.g. malformed GNS path)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
