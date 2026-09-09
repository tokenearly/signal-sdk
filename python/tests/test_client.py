from unittest import mock

import pytest
import requests

from tokenearly_signal import (
    AuthError,
    ContractError,
    Event,
    ServerError,
    SignalClient,
    SourceDisabledError,
    TransportError,
    ValidationError,
)
from tokenearly_signal.client import DEFAULT_ENDPOINT

from conftest import FakeResponse, FakeSession

EVENT = Event(source_id="my_signal", event_id="evt-1", title="Test signal", lang="en")


def make_client(script, sleeps, **kw):
    session = FakeSession(script)
    client = SignalClient("tok-123", session=session, sleep=sleeps.append, **kw)
    return client, session


def test_success_sends_expected_request(sleeps):
    client, session = make_client([FakeResponse(200, {"status": "success"})], sleeps)
    result = client.send(EVENT)

    assert result.pushed and not result.pending and result.status_code == 200
    call = session.calls[0]
    assert call["url"] == DEFAULT_ENDPOINT
    assert call["headers"]["X-Signal-Token"] == "tok-123"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["headers"]["User-Agent"].startswith("tokenearly-signal-python/")
    assert call["json"] == {"source_id": "my_signal", "event_id": "evt-1", "title": "Test signal", "lang": "en"}
    assert call["timeout"] == 10.0
    assert sleeps == []


def test_custom_endpoint():
    client, session = make_client([FakeResponse(200, {"status": "success"})], [], endpoint="https://signals.example.com/receive_signal")
    client.send(EVENT)
    assert session.calls[0]["url"] == "https://signals.example.com/receive_signal"


def test_pending_review(sleeps):
    client, _ = make_client([FakeResponse(202, {"status": "pending_review"})], sleeps)
    result = client.send(EVENT)
    assert result.pending and not result.pushed and result.status_code == 202


def test_silent_stored(sleeps):
    client, session = make_client([FakeResponse(200, {"status": "stored", "pushed": False})], sleeps)
    result = client.send(Event(source_id="my_signal", event_id="old-1", title="old", silent=True))
    assert result.stored_only and not result.pushed
    assert session.calls[0]["json"]["silent"] is True


def test_dict_event_is_accepted(sleeps):
    client, session = make_client([FakeResponse(200, {"status": "success"})], sleeps)
    client.send({"source_id": "my_signal", "event_id": "evt-2", "titles": {"en": "hi"}})
    assert session.calls[0]["json"]["titles"] == {"en": "hi"}


def test_invalid_event_never_hits_network(sleeps):
    client, session = make_client([], sleeps)
    with pytest.raises(ValidationError):
        client.send(Event(source_id="Bad ID", event_id="e", title="t"))
    with pytest.raises(ValidationError):
        client.send({"source_id": "ok", "event_id": "e", "title": "t", "bogus": 1})
    assert session.calls == []


def test_contract_error_is_not_retried(sleeps):
    client, session = make_client([FakeResponse(400, {"code": "contract_error", "msg": "titles missing"})], sleeps)
    with pytest.raises(ContractError) as info:
        client.send(EVENT)
    assert info.value.status_code == 400
    assert info.value.code == "contract_error"
    assert "titles missing" in str(info.value)
    assert len(session.calls) == 1 and sleeps == []


def test_auth_error(sleeps):
    client, _ = make_client([FakeResponse(401, {"code": "unauthorized"})], sleeps)
    with pytest.raises(AuthError):
        client.send(EVENT)


def test_source_disabled(sleeps):
    client, _ = make_client([FakeResponse(403, {"code": "source_disabled"})], sleeps)
    with pytest.raises(SourceDisabledError) as info:
        client.send(EVENT)
    assert info.value.code == "source_disabled"


def test_retries_5xx_with_backoff_then_succeeds(sleeps):
    client, session = make_client(
        [FakeResponse(503, text="bad gateway"), FakeResponse(500, {}), FakeResponse(200, {"status": "success"})],
        sleeps,
    )
    result = client.send(EVENT)
    assert result.pushed
    assert len(session.calls) == 3
    assert sleeps == [1.0, 2.0]


def test_gives_up_after_max_retries(sleeps):
    client, session = make_client([FakeResponse(502, {})] * 4, sleeps, max_retries=3)
    with pytest.raises(ServerError) as info:
        client.send(EVENT)
    assert info.value.status_code == 502
    assert len(session.calls) == 4
    assert sleeps == [1.0, 2.0, 4.0]


def test_backoff_is_capped(sleeps):
    client, _ = make_client([FakeResponse(500, {})] * 7, sleeps, max_retries=6)
    with pytest.raises(ServerError):
        client.send(EVENT)
    assert sleeps == [1.0, 2.0, 4.0, 8.0, 15.0, 15.0]


def test_network_errors_are_retried(sleeps):
    client, session = make_client(
        [requests.ConnectionError("boom"), requests.Timeout("slow"), FakeResponse(200, {"status": "success"})],
        sleeps,
    )
    assert client.send(EVENT).pushed
    assert len(session.calls) == 3
    assert sleeps == [1.0, 2.0]


def test_transport_error_after_retries(sleeps):
    client, _ = make_client([requests.Timeout("slow")] * 2, sleeps, max_retries=1)
    with pytest.raises(TransportError):
        client.send(EVENT)
    assert sleeps == [1.0]


def test_send_many_collects_errors(sleeps):
    client, _ = make_client(
        [FakeResponse(200, {"status": "success"}), FakeResponse(400, {"code": "contract_error"}),
         FakeResponse(202, {"status": "pending_review"})],
        sleeps,
    )
    events = [EVENT, Event(source_id="my_signal", event_id="evt-2", title="x"),
              Event(source_id="my_signal", event_id="evt-3", title="y")]
    batch = client.send_many(events)
    assert batch.sent == 2 and batch.failed == 1 and not batch.ok
    assert batch.results[1] is None and isinstance(batch.errors[1], ContractError)
    assert batch.results[2].pending
    with pytest.raises(ContractError):
        batch.raise_first()


def test_send_many_stop_on_error(sleeps):
    client, session = make_client([FakeResponse(400, {"code": "contract_error"})], sleeps)
    with pytest.raises(ContractError):
        client.send_many([EVENT, EVENT], stop_on_error=True)
    assert len(session.calls) == 1


def test_empty_token_rejected():
    with pytest.raises(ValidationError):
        SignalClient("   ")


def test_context_manager_closes_owned_session():
    with mock.patch.object(requests.Session, "post") as post:
        post.return_value = FakeResponse(200, {"status": "success"})
        with SignalClient("tok") as client:
            assert client.send(EVENT).pushed
        kwargs = post.call_args.kwargs
        assert kwargs["headers"]["X-Signal-Token"] == "tok"
        assert kwargs["json"]["event_id"] == "evt-1"


def test_injected_session_is_not_closed(sleeps):
    client, session = make_client([FakeResponse(200, {"status": "success"})], sleeps)
    client.send(EVENT)
    client.close()
    assert session.closed is False
