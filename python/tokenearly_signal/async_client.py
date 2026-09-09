"""Asynchronous client (uses ``aiohttp``; install with ``pip install "tokenearly-signal[async]"``)."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional

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

try:  # aiohttp is optional
    import aiohttp
except ImportError:  # pragma: no cover - exercised only without the extra installed
    aiohttp = None  # type: ignore[assignment]

_RETRYABLE_EXC: tuple = (asyncio.TimeoutError, OSError)
if aiohttp is not None:
    _RETRYABLE_EXC = _RETRYABLE_EXC + (aiohttp.ClientError,)

__all__ = ["AsyncSignalClient"]


class AsyncSignalClient:
    """Async twin of :class:`tokenearly_signal.SignalClient`.

    Use as ``async with AsyncSignalClient(token) as client:``. Pass ``session`` to reuse an
    existing ``aiohttp.ClientSession`` (the client will not close it).
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
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self._headers = build_headers(token, "aiohttp")
        self._session = session
        self._owns_session = session is None
        self._sleep = sleep

    async def __aenter__(self) -> "AsyncSignalClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    def _get_session(self) -> Any:
        if self._session is None:
            if aiohttp is None:
                raise SignalError(
                    "aiohttp is required for AsyncSignalClient: pip install 'tokenearly-signal[async]'"
                )
            self._session = aiohttp.ClientSession()
        return self._session

    # -- public API ----------------------------------------------------------
    async def send(self, event: EventLike) -> SignalResult:
        """Validate and send one event."""
        return await self._post(coerce_event(event))

    async def send_many(
        self,
        events: Iterable[EventLike],
        *,
        concurrency: int = 4,
        stop_on_error: bool = False,
    ) -> BatchResult:
        """Send events concurrently (at most ``concurrency`` in flight).

        Failures are collected in ``BatchResult.errors``; with ``stop_on_error=True`` the first
        error is raised once the batch has finished.
        """
        items = list(events)
        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def one(index: int, event: EventLike):
            async with semaphore:
                try:
                    return index, await self.send(event), None
                except SignalError as exc:
                    return index, None, exc

        outcomes = await asyncio.gather(*(one(i, ev) for i, ev in enumerate(items)))
        batch = BatchResult(results=[None] * len(items), errors={})
        for index, result, error in outcomes:
            if error is not None:
                batch.errors[index] = error
            else:
                batch.results[index] = result
        if stop_on_error:
            batch.raise_first()
        return batch

    # -- internals -----------------------------------------------------------
    async def _post(self, payload: Dict[str, Any]) -> SignalResult:
        session = self._get_session()
        timeout: Any = aiohttp.ClientTimeout(total=self.timeout) if aiohttp is not None else self.timeout
        attempt = 0
        while True:
            try:
                async with session.post(
                    self.endpoint, json=payload, headers=self._headers, timeout=timeout
                ) as response:
                    status = int(response.status)
                    text = await response.text()
            except _RETRYABLE_EXC as exc:
                if attempt < self.max_retries:
                    await self._sleep(backoff_delay(attempt, self.backoff_base, self.backoff_max))
                    attempt += 1
                    continue
                raise TransportError(
                    f"could not reach {self.endpoint} after {attempt + 1} attempts: {exc}"
                ) from exc

            if is_retryable_status(status) and attempt < self.max_retries:
                await self._sleep(backoff_delay(attempt, self.backoff_base, self.backoff_max))
                attempt += 1
                continue
            return result_or_raise(status, parse_body(text))
