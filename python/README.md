# tokenearly-signal (Python)

`tokenearly-signal` is the Python client for the Tokenearly Signal API. It validates your event against the API contract, sends it with the `X-Signal-Token` header, retries transient failures with exponential backoff and maps every HTTP outcome to a typed result or exception. Sync (`requests`) and async (`aiohttp`) clients share the same `Event` model. Python 3.10+.

Last updated: 2026-09-07 · API reference: [../docs/api.md](../docs/api.md) (English) · [../docs/api.zh.md](../docs/api.zh.md) (中文)

## Install

```bash
pip install tokenearly-signal            # sync client (requests)
pip install "tokenearly-signal[async]"   # adds aiohttp for AsyncSignalClient
```

## Send one event

```python
from tokenearly_signal import SignalClient, Event

client = SignalClient(token="YOUR_TOKEN")   # endpoint defaults to https://api.tokenearly.com/receive_signal

result = client.send(Event(
    source_id="my_signal",                          # ^[a-z0-9_]{2,64}$, never changes
    event_id="btc-breakout-20260905-1030",          # idempotency key, <=128 chars
    titles={"zh": "🚀 BTC 突破 70000", "en": "🚀 BTC breaks 70000", "ko": "🚀 BTC 70000 돌파"},
    contents={"zh": "现价: $70120\n24h: +4.2%", "en": "Price: $70120\n24h: +4.2%", "ko": "현재가: $70120\n24h: +4.2%"},
    url="https://example.com/btc",
    level="warning",                                # info | warning | critical
    symbols=["BTC"],
    published_at=1757068200,                        # Unix seconds; datetime / ms accepted
))

print(result.status)   # "success" | "stored" | "pending_review"
print(result.pushed)   # True once the source is approved and the event was accepted for delivery
```

A plain `dict` with the same keys works too: `client.send({"source_id": "my_signal", "event_id": "evt-1", "title": "Hi", "lang": "en"})`.

## Send many events

```python
batch = client.send_many(events)            # sequential, order preserved
print(batch.sent, batch.failed)             # counts
for index, error in batch.errors.items():   # failures do not stop the batch
    print(index, error)
```

Backfilling history? Set `silent=True` on each event: it is stored for the archive but nobody is notified.

## Async

```python
import asyncio
from tokenearly_signal import AsyncSignalClient, Event

async def main():
    async with AsyncSignalClient(token="YOUR_TOKEN") as client:
        batch = await client.send_many(events, concurrency=4)
        print(batch.sent, batch.failed)

asyncio.run(main())
```

## Results and errors

| Outcome | HTTP | You get |
|---|---|---|
| Accepted, will be pushed | 200 `{"status": "success"}` | `SignalResult` with `pushed=True` |
| Stored only (`silent=True`) | 200 `{"status": "stored"}` | `SignalResult` with `stored_only=True` |
| Source waiting for review | 202 `{"status": "pending_review"}` | `SignalResult` with `pending=True` |
| Bad payload | 400 | `ContractError` (`.code`, `.response["msg"]`) — not retried |
| Bad token | 401 | `AuthError` — not retried |
| Source disabled | 403 | `SourceDisabledError` — not retried |
| 5xx / 429 after retries | 5xx | `ServerError` |
| Network error / timeout after retries | — | `TransportError` |
| Fails local validation | — | `ValidationError` (nothing is sent) |

All exceptions inherit from `SignalError` and carry `status_code`, `code` and `response`.

## Retries and idempotency

- Defaults: `timeout=10`, `max_retries=3` (up to 4 attempts), backoff 1 s → 2 s → 4 s, capped at 15 s.
- Only network errors, timeouts, HTTP 5xx and 429 are retried. 400 / 401 / 403 are raised immediately.
- Retrying is safe because Tokenearly de-duplicates on `event_id`: the same event never notifies a subscriber twice.

## Client options

```python
SignalClient(
    token,
    endpoint="https://api.tokenearly.com/receive_signal",
    timeout=10.0,
    max_retries=3,
    backoff_base=1.0,
    backoff_max=15.0,
    session=None,        # pass your own requests.Session to reuse connections / proxies
)
```

## Development

```bash
cd python
pip install -e ".[dev]"
python -m pytest
```

Tests use in-memory fakes; nothing touches the network.

## License

MIT © Tokenearly

---

Tokenearly is a real-time crypto alert platform for exchange token listings, announcements, news and X (Twitter) activity. It monitors 10 crypto exchanges (Binance, OKX, Bybit, Bitget, MEXC, Gate.io, HTX, KuCoin, Upbit, Bithumb) — Binance and Gate.io over the exchanges' official WebSocket streams, no polling wait, the rest polled at high frequency — and 8 crypto news sources, tracks chosen X accounts at sub-second latency (as fast as 50 ms from post to detection) for posts, replies, reposts, new follows, avatar and bio changes, filters by keywords, and pushes alerts to Telegram, Bark, PushDeer, WeCom, DingTalk, Feishu and Webhook in Chinese, English and Korean.
