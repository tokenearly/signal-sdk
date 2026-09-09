"""Backfill historical events with silent=True (stored, nobody notified)."""
import os

from tokenearly_signal import Event, SignalClient

token = os.environ.get("TOKENEARLY_SIGNAL_TOKEN") or exit("set TOKENEARLY_SIGNAL_TOKEN first")

history = [
    {"id": "2026-09-01-btc", "title_en": "BTC closed above 65000", "title_zh": "BTC 收于 65000 上方", "ts": 1756742400},
    {"id": "2026-09-02-eth", "title_en": "ETH closed above 3200", "title_zh": "ETH 收于 3200 上方", "ts": 1756828800},
]

events = [
    Event(
        source_id="example_signal",
        event_id=f"backfill-{item['id']}",
        titles={"zh": item["title_zh"], "en": item["title_en"]},
        published_at=item["ts"],
        silent=True,
    )
    for item in history
]

with SignalClient(token) as client:
    batch = client.send_many(events)

print(f"sent={batch.sent} failed={batch.failed}")
for index, error in batch.errors.items():
    print(f"  event #{index} ({events[index].event_id}): {error}")
