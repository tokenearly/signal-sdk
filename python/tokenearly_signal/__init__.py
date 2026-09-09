"""tokenearly-signal: Python SDK for the Tokenearly Signal API.

Quick start::

    from tokenearly_signal import SignalClient, Event

    client = SignalClient(token="YOUR_TOKEN")
    result = client.send(Event(
        source_id="my_signal",
        event_id="btc-breakout-20260905-1030",
        titles={"zh": "BTC 突破 70000", "en": "BTC breaks 70000", "ko": "BTC 70000 돌파"},
        symbols=["BTC"],
    ))
    print(result.status)  # "success" | "stored" | "pending_review"
"""
from ._common import DEFAULT_ENDPOINT, BatchResult, SignalResult
from ._version import __version__
from .async_client import AsyncSignalClient
from .client import SignalClient
from .errors import (
    AuthError,
    ContractError,
    ServerError,
    SignalError,
    SourceDisabledError,
    TransportError,
    ValidationError,
)
from .event import LANGS, LEVELS, Event, Source

__all__ = [
    "__version__",
    "DEFAULT_ENDPOINT",
    "SignalClient",
    "AsyncSignalClient",
    "SignalResult",
    "BatchResult",
    "Event",
    "Source",
    "LANGS",
    "LEVELS",
    "SignalError",
    "ValidationError",
    "ContractError",
    "AuthError",
    "SourceDisabledError",
    "ServerError",
    "TransportError",
]
