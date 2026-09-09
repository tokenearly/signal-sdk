"""Pieces shared by the sync and async clients."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Union

from ._version import __version__
from .errors import (
    AuthError,
    ContractError,
    ServerError,
    SignalError,
    SourceDisabledError,
    ValidationError,
)
from .event import Event

DEFAULT_ENDPOINT = "https://api.tokenearly.com/receive_signal"
# 5xx are retryable too (checked separately); these are the non-5xx retryable statuses.
RETRYABLE_STATUS = frozenset({408, 425, 429})

EventLike = Union[Event, Mapping[str, Any]]


@dataclass
class SignalResult:
    """Successful (HTTP 200 / 202) response."""

    status_code: int
    status: str  # "success" | "stored" | "pending_review"
    body: Dict[str, Any] = field(default_factory=dict)

    @property
    def pushed(self) -> bool:
        """True when Tokenearly accepted the event for delivery to subscribers."""
        return self.status == "success"

    @property
    def pending(self) -> bool:
        """True when the source is still waiting for review (HTTP 202)."""
        return self.status == "pending_review"

    @property
    def stored_only(self) -> bool:
        """True for ``silent`` events that were stored without notifying anyone."""
        return self.status == "stored"


@dataclass
class BatchResult:
    """Outcome of ``send_many``. ``results[i]`` is the result for ``events[i]`` or ``None`` if it failed."""

    results: List[Optional[SignalResult]]
    errors: Dict[int, SignalError]

    @property
    def sent(self) -> int:
        return sum(1 for r in self.results if r is not None)

    @property
    def failed(self) -> int:
        return len(self.errors)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_first(self) -> None:
        """Re-raise the first error, if any."""
        if self.errors:
            raise self.errors[min(self.errors)]


def build_headers(token: str, transport: str) -> Dict[str, str]:
    if not isinstance(token, str) or not token.strip():
        raise ValidationError("token must be a non-empty string (ask Tokenearly for one)")
    return {
        "Content-Type": "application/json",
        "X-Signal-Token": token.strip(),
        "User-Agent": f"tokenearly-signal-python/{__version__} ({transport})",
    }


def coerce_event(event: EventLike) -> Dict[str, Any]:
    """Accept an :class:`Event` or a plain dict and return the validated payload."""
    if isinstance(event, Event):
        return event.to_dict()
    if isinstance(event, Mapping):
        try:
            return Event(**dict(event)).to_dict()
        except TypeError as exc:  # unknown keyword → unknown field
            raise ValidationError(f"unknown event field: {exc}") from exc
    raise ValidationError("event must be an Event or a dict")


def backoff_delay(attempt: int, base: float, cap: float) -> float:
    """1s, 2s, 4s, ... capped (defaults follow the API reference: cap 15s)."""
    return min(base * (2 ** attempt), cap)


def is_retryable_status(status: int) -> bool:
    return status >= 500 or status in RETRYABLE_STATUS


def parse_body(text: Optional[str]) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return {"raw": text}
    return data if isinstance(data, dict) else {"raw": data}


def result_or_raise(status_code: int, body: Dict[str, Any]) -> SignalResult:
    """Map an HTTP response to a :class:`SignalResult` or raise the matching error."""
    if status_code in (200, 202):
        status = body.get("status") or ("pending_review" if status_code == 202 else "success")
        return SignalResult(status_code=status_code, status=str(status), body=body)

    code = body.get("code")
    msg = body.get("msg") or body.get("message") or body.get("detail") or ""
    if status_code == 400:
        raise ContractError(
            f"{code or 'contract_error'}: {msg or 'payload rejected'}",
            status_code=400, code=str(code or "contract_error"), response=body,
        )
    if status_code == 401:
        raise AuthError(
            "missing or invalid X-Signal-Token", status_code=401, code=str(code or "unauthorized"), response=body,
        )
    if status_code == 403:
        raise SourceDisabledError(
            f"{code or 'source_disabled'}: {msg or 'this source has been disabled'}",
            status_code=403, code=str(code or "source_disabled"), response=body,
        )
    if status_code >= 500 or status_code == 429:
        raise ServerError(
            f"Tokenearly returned HTTP {status_code} after retries", status_code=status_code,
            code=str(code) if code else None, response=body,
        )
    raise SignalError(
        f"unexpected HTTP {status_code}: {msg or body}", status_code=status_code,
        code=str(code) if code else None, response=body,
    )
