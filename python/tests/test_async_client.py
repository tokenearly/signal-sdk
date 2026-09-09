import asyncio

import pytest

from tokenearly_signal import AsyncSignalClient, ContractError, Event, ServerError, TransportError

from conftest import FakeAsyncResponse, FakeAsyncSession

EVENT = Event(source_id="my_signal", event_id="evt-1", title="Test signal", lang="en")


def run(coro):
    return asyncio.run(coro)


def make_client(script, sleeps, **kw):
    session = FakeAsyncSession(script)

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    return AsyncSignalClient("tok-async", session=session, sleep=fake_sleep, **kw), session


def test_async_success(sleeps):
    client, session = make_client([FakeAsyncResponse(200, {"status": "success"})], sleeps)

    async def main():
        async with client:
            return await client.send(EVENT)

    result = run(main())
    assert result.pushed
    assert session.calls[0]["headers"]["X-Signal-Token"] == "tok-async"
    assert session.calls[0]["json"]["event_id"] == "evt-1"
    assert session.closed is False  # injected session is left open


def test_async_retry_then_success(sleeps):
    client, session = make_client(
        [FakeAsyncResponse(503, text="down"), asyncio.TimeoutError(), FakeAsyncResponse(202, {"status": "pending_review"})],
        sleeps,
    )
    result = run(client.send(EVENT))
    assert result.pending
    assert len(session.calls) == 3
    assert sleeps == [1.0, 2.0]


def test_async_contract_error(sleeps):
    client, _ = make_client([FakeAsyncResponse(400, {"code": "contract_error", "msg": "bad"})], sleeps)
    with pytest.raises(ContractError):
        run(client.send(EVENT))


def test_async_gives_up(sleeps):
    client, _ = make_client([FakeAsyncResponse(500, {})] * 3, sleeps, max_retries=2)
    with pytest.raises(ServerError):
        run(client.send(EVENT))
    assert sleeps == [1.0, 2.0]


def test_async_transport_error(sleeps):
    client, _ = make_client([OSError("no route")] * 2, sleeps, max_retries=1)
    with pytest.raises(TransportError):
        run(client.send(EVENT))


def test_async_send_many(sleeps):
    client, session = make_client(
        [FakeAsyncResponse(200, {"status": "success"}), FakeAsyncResponse(400, {"code": "contract_error"}),
         FakeAsyncResponse(200, {"status": "success"})],
        sleeps,
    )
    events = [Event(source_id="my_signal", event_id=f"evt-{i}", title="t") for i in range(3)]
    batch = run(client.send_many(events, concurrency=2))
    assert batch.sent == 2 and batch.failed == 1
    assert len(session.calls) == 3


def test_async_send_many_stop_on_error(sleeps):
    client, _ = make_client([FakeAsyncResponse(400, {"code": "contract_error"})], sleeps)
    with pytest.raises(ContractError):
        run(client.send_many([EVENT], stop_on_error=True))
