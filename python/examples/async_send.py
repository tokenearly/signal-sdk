"""Send events concurrently with the aiohttp-based client.

    pip install "tokenearly-signal[async]"
"""
import asyncio
import os
import time

from tokenearly_signal import AsyncSignalClient, Event

token = os.environ.get("TOKENEARLY_SIGNAL_TOKEN") or exit("set TOKENEARLY_SIGNAL_TOKEN first")


async def main() -> None:
    now = int(time.time())
    events = [
        Event(source_id="example_signal", event_id=f"async-{now}-{i}",
              title=f"Async example #{i}", lang="en", published_at=now)
        for i in range(5)
    ]
    async with AsyncSignalClient(token) as client:
        batch = await client.send_many(events, concurrency=3)
    print(f"sent={batch.sent} failed={batch.failed}")


asyncio.run(main())
