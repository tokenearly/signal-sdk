"""Exception types raised by tokenearly-signal.

Hierarchy::

    SignalError
    ├── ValidationError      client-side, nothing was sent
    ├── ContractError        HTTP 400 (contract_error / invalid_json)
    ├── AuthError            HTTP 401
    ├── SourceDisabledError  HTTP 403
    ├── ServerError          HTTP 5xx after all retries
    └── TransportError       network error / timeout after all retries
"""
from __future__ import annotations

from typing import Any, Optional


class SignalError(Exception):
    """Base class for every error raised by this SDK."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
        response: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.response = response

    def __str__(self) -> str:
        if self.status_code is not None:
            return f"[HTTP {self.status_code}] {self.message}"
        return self.message


class ValidationError(SignalError, ValueError):
    """The event failed client-side validation. Nothing was sent."""


class ContractError(SignalError):
    """HTTP 400: the server rejected the payload (``contract_error`` or ``invalid_json``).

    Fix the event before sending again; retrying the same request will fail again.
    """


class AuthError(SignalError):
    """HTTP 401: the ``X-Signal-Token`` header is missing or wrong."""


class SourceDisabledError(SignalError):
    """HTTP 403: this ``source_id`` has been disabled by Tokenearly (``source_disabled``)."""


class ServerError(SignalError):
    """HTTP 5xx (or 429) still failing after all retries."""


class TransportError(SignalError):
    """Network failure or timeout still failing after all retries."""
