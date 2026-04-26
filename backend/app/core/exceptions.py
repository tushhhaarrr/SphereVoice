"""Structured HTTP exceptions.

All API errors follow a consistent response schema:
``{"error": {"code": "...", "message": "...", "details": {...}}}``
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


class SphereVoiceException(HTTPException):
    """Base exception for all SphereVoice API errors."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.error_message = message
        self.details = details or {}
        super().__init__(
            status_code=status_code,
            detail={
                "error": {
                    "code": code,
                    "message": message,
                    "details": self.details,
                }
            },
        )


class NotFoundError(SphereVoiceException):
    """Resource not found (404)."""

    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"{resource} not found",
            details={"resource": resource, "id": resource_id},
        )


class ConflictError(SphereVoiceException):
    """Resource conflict (409) — e.g. duplicate email."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT",
            message=message,
            details=details,
        )


class ForbiddenError(SphereVoiceException):
    """Forbidden (403) — user lacks required role/permission."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=message,
        )


class UnauthorizedError(SphereVoiceException):
    """Unauthorized (401) — missing or invalid credentials."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message=message,
        )


class ValidationError(SphereVoiceException):
    """Validation error (422) — request payload failed validation."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message=message,
            details=details,
        )


class ProviderError(SphereVoiceException):
    """External provider error (502) — STT/LLM/TTS/telephony failure."""

    def __init__(self, provider: str, message: str) -> None:
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="PROVIDER_ERROR",
            message=f"Provider error ({provider}): {message}",
            details={"provider": provider},
        )
