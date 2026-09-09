"""Shared fakes. No test in this suite touches the network."""
from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest


class FakeResponse:
    def __init__(self, status_code: int, body: Any = None, text: str | None = None) -> None:
        self.status_code = status_code
        self.text = text if text is not None else (json.dumps(body) if body is not None else "")


class FakeSession:
    """Mimics the subset of ``requests.Session`` used by ``SignalClient``."""

    def __init__(self, script: List[Any]) -> None:
        self.script = list(script)
        self.calls: List[Dict[str, Any]] = []
        self.closed = False

    def post(self, url: str, json: Any = None, headers: Any = None, timeout: Any = None) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if not self.script:
            raise AssertionError("unexpected extra request")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        self.closed = True


class _AsyncCtx:
    def __init__(self, response: "FakeAsyncResponse") -> None:
        self._response = response

    async def __aenter__(self) -> "FakeAsyncResponse":
        return self._response

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class FakeAsyncResponse:
    def __init__(self, status: int, body: Any = None, text: str | None = None) -> None:
        self.status = status
        self._text = text if text is not None else (json.dumps(body) if body is not None else "")

    async def text(self) -> str:
        return self._text


class FakeAsyncSession:
    """Mimics the subset of ``aiohttp.ClientSession`` used by ``AsyncSignalClient``."""

    def __init__(self, script: List[Any]) -> None:
        self.script = list(script)
        self.calls: List[Dict[str, Any]] = []
        self.closed = False

    def post(self, url: str, json: Any = None, headers: Any = None, timeout: Any = None) -> _AsyncCtx:
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if not self.script:
            raise AssertionError("unexpected extra request")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return _AsyncCtx(item)

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def sleeps() -> List[float]:
    return []
