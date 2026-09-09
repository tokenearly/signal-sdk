"""Send a single signal event.

    export TOKENEARLY_SIGNAL_TOKEN=...   # token issued by Tokenearly
    python examples/send_one.py
"""
import os
import time

from tokenearly_signal import Event, SignalClient, SignalError, Source

token = os.environ.get("TOKENEARLY_SIGNAL_TOKEN")
if not token:
    raise SystemExit("set TOKENEARLY_SIGNAL_TOKEN first")

event = Event(
    source_id="example_signal",
    event_id=f"example-{int(time.time())}",
    titles={"zh": "🚀 BTC 突破 70000", "en": "🚀 BTC breaks 70000", "ko": "🚀 BTC 70000 돌파"},
    contents={"zh": "现价: $70120\n24h: +4.2%", "en": "Price: $70120\n24h: +4.2%", "ko": "현재가: $70120\n24h: +4.2%"},
    url="https://example.com/btc",
    level="warning",
    symbols=["BTC"],
    tags=["breakout"],
    published_at=int(time.time()),
    raw={"price": 70120, "change24h": 4.2},
    # Send display info with the first event; Tokenearly staff can edit it later.
    source=Source(
        name={"zh": "示例信号", "en": "Example Signal", "ko": "예시 시그널"},
        description={"zh": "SDK 示例", "en": "SDK example", "ko": "SDK 예시"},
        monitor_type={"zh": "异动提醒", "en": "Movement alerts", "ko": "변동 알림"},
    ),
)

with SignalClient(token) as client:
    try:
        result = client.send(event)
    except SignalError as exc:
        raise SystemExit(f"failed: {exc}")

print(f"HTTP {result.status_code} status={result.status} pushed={result.pushed} pending={result.pending}")
if result.pending:
    print("First event from this source_id: ask Tokenearly to approve the source.")
