"""Minimal polling adapter: poll any HTTP API, turn new items into signal events, de-duplicate locally.

Replace ``fetch_items`` with your own data source. State (already-sent event ids) is kept in a JSON
file so a restart never re-sends old items.

    export TOKENEARLY_SIGNAL_TOKEN=...
    export ADAPTER_STATE_FILE=./example_signal.state.json   # optional
    python examples/polling_adapter.py
"""
import json
import os
import signal
import time
from pathlib import Path

import requests

from tokenearly_signal import Event, SignalClient, SignalError

SOURCE_ID = "example_signal"
INTERVAL_SECONDS = 30
STATE_FILE = Path(os.environ.get("ADAPTER_STATE_FILE", f"./{SOURCE_ID}.state.json"))
MAX_REMEMBERED = 5000


def fetch_items() -> list[dict]:
    """Return a list of dicts with at least ``id``, ``title`` and ``url``. Replace with your API."""
    url = os.environ.get("ADAPTER_SOURCE_URL")
    if not url:
        return []
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else data.get("items", [])


def load_state() -> list[str]:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return []


def save_state(sent_ids: list[str]) -> None:
    STATE_FILE.write_text(json.dumps(sent_ids[-MAX_REMEMBERED:]))


def to_event(item: dict) -> Event:
    return Event(
        source_id=SOURCE_ID,
        event_id=str(item["id"]),
        title=str(item["title"])[:200],
        lang="en",
        url=item.get("url"),
        published_at=item.get("ts"),
        raw=item,
    )


def main() -> None:
    token = os.environ.get("TOKENEARLY_SIGNAL_TOKEN") or exit("set TOKENEARLY_SIGNAL_TOKEN first")
    sent_ids = load_state()
    seen = set(sent_ids)
    first_round = not sent_ids  # on a fresh state, only register items, do not push history
    running = True

    def stop(*_: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    with SignalClient(token) as client:
        while running:
            try:
                items = fetch_items()
            except Exception as exc:  # noqa: BLE001 - keep polling
                print(f"fetch failed: {exc}")
                items = []
            for item in items:
                event_id = str(item["id"])
                if event_id in seen:
                    continue
                if first_round:
                    seen.add(event_id)
                    sent_ids.append(event_id)
                    continue
                try:
                    result = client.send(to_event(item))
                    print(f"{event_id}: {result.status}")
                    seen.add(event_id)
                    sent_ids.append(event_id)
                except SignalError as exc:
                    print(f"{event_id}: {exc}")
            first_round = False
            save_state(sent_ids)
            for _ in range(INTERVAL_SECONDS):
                if not running:
                    break
                time.sleep(1)


if __name__ == "__main__":
    main()
