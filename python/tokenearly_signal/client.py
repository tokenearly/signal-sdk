"""Synchronous client (uses ``requests``)."""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterable, Optional

import requests

from ._common import (
    DEFAULT_ENDPOINT,
    BatchResult,
    EventLike,
    SignalResult,
    backoff_delay,
    build_headers,
    coerce_event,
    is_retryable_status,
    parse_body,
    result_or_raise,
)
from .errors import SignalError, TransportError

__all__ = ["SignalClient", "SignalResult", "BatchResult", "DEFAULT_ENDPOINT"]


class SignalClient:
    """Send events to the Tokenearly Signal API.

    Args:
        token: the ``X-Signal-Token`` Tokenearly issued to you.
        endpoint: defaults to ``https://api.tokenearly.com/receive_signal``.
        timeout: per-request timeout in seconds (default 10).
        max_retries: retries after the first attempt for network errors, timeouts,
            HTTP 5xx and 429 (default 3, i.e. up to 4 attempts).
        backoff_base / backoff_max: exponential backoff 1s, 2s, 4s … capped at 15s.
        session: optional ``requests.Session`` (or any object with a compatible ``post``).
        sleep: sleep function used between retries (injectable for tests).

    HTTP 400 / 401 / 403 are never retried; they raise ``ContractError`` /
    ``AuthError`` / ``SourceDisabledError`` immediately.
    """

    def __init__(
        self,
        token: str,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        backoff_max: float = 15.0,
        session: Optional[Any] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self._headers = build_headers(token, "requests")
        self._session = session if session is not None else requests.Session()
        self._owns_session = session is None
        self._sleep = sleep

    # -- context manager -----------------------------------------------------
    def __enter__(self) -> "SignalClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_session:
            close = getattr(self._session, "close", None)
            if callable(close):
                close()

    # -- public API ----------------------------------------------------------
    def send(self, event: EventLike) -> SignalResult:
        """Validate and send one event. Returns a :class:`SignalResult` or raises a ``SignalError``."""
        return self._post(coerce_event(event))

    def send_many(self, events: Iterable[EventLike], *, stop_on_error: bool = False) -> BatchResult:
        """Send events one after another (order preserved).

        With ``stop_on_error=False`` (default) failures are collected in ``BatchResult.errors``
        and the remaining events are still sent.
        """
        results = []
        errors: Dict[int, SignalError] = {}
        for index, event in enumerate(events):
            try:
                results.append(self.send(event))
            except SignalError as exc:
                if stop_on_error:
                    raise
                errors[index] = exc
                results.append(None)
        return BatchResult(results=results, errors=errors)

    # -- internals -----------------------------------------------------------
    def _post(self, payload: Dict[str, Any]) -> SignalResult:
        attempt = 0
        while True:
            try:
                response = self._session.post(
                    self.endpoint, json=payload, headers=self._headers, timeout=self.timeout
                )
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    self._sleep(backoff_delay(attempt, self.backoff_base, self.backoff_max))
                    attempt += 1
                    continue
                raise TransportError(
                    f"could not reach {self.endpoint} after {attempt + 1} attempts: {exc}"
                ) from exc

            status = int(response.status_code)
            if is_retryable_status(status) and attempt < self.max_retries:
                self._sleep(backoff_delay(attempt, self.backoff_base, self.backoff_max))
                attempt += 1
                continue
            return result_or_raise(status, parse_body(getattr(response, "text", "")))
