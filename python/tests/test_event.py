from datetime import datetime, timezone

import pytest

from tokenearly_signal import Event, Source, ValidationError


def test_minimal_event_with_title():
    body = Event(source_id="my_signal", event_id="evt-1", title="Hello", lang="en").to_dict()
    assert body == {"source_id": "my_signal", "event_id": "evt-1", "title": "Hello", "lang": "en"}


def test_none_fields_and_false_silent_are_omitted():
    body = Event(source_id="my_signal", event_id="evt-1", titles={"zh": "你好"}).to_dict()
    assert "silent" not in body
    assert "contents" not in body
    assert "url" not in body


def test_full_event_round_trip():
    ev = Event(
        source_id="my_signal",
        event_id="btc-breakout-20260905-1030",
        titles={"zh": "🚀 BTC 突破 70000", "en": "🚀 BTC breaks 70000", "ko": "🚀 BTC 70000 돌파"},
        contents={"zh": "现价: $70120", "en": "Price: $70120", "ko": "현재가: $70120"},
        url="https://example.com/btc",
        level="warning",
        symbols=["btc", " eth "],
        tags=["breakout"],
        published_at=1757068200,
        raw={"price": 70120},
        silent=True,
        source=Source(name={"zh": "我的信号", "en": "My Signal", "ko": "내 시그널"},
                      icon="https://example.com/favicon.ico"),
    )
    body = ev.to_dict()
    assert body["symbols"] == ["BTC", "ETH"]
    assert body["silent"] is True
    assert body["published_at"] == 1757068200
    assert body["source"] == {
        "name": {"zh": "我的信号", "en": "My Signal", "ko": "내 시그널"},
        "icon": "https://example.com/favicon.ico",
    }


def test_source_as_plain_dict():
    body = Event(source_id="s1", event_id="e", title="t",
                 source={"name": "My Signal", "description": "desc"}).to_dict()
    assert body["source"] == {"name": "My Signal", "description": "desc"}


@pytest.mark.parametrize("source_id", ["", "A", "My-Signal", "x" * 65, "has space"])
def test_bad_source_id(source_id):
    with pytest.raises(ValidationError):
        Event(source_id=source_id, event_id="e", title="t").to_dict()


def test_event_id_limits():
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="", title="t").to_dict()
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="x" * 129, title="t").to_dict()
    Event(source_id="ok", event_id="x" * 128, title="t").to_dict()


def test_title_required():
    with pytest.raises(ValidationError, match="titles"):
        Event(source_id="ok", event_id="e").to_dict()


def test_title_length_and_language():
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="e", title="x" * 201).to_dict()
    with pytest.raises(ValidationError, match="unsupported language"):
        Event(source_id="ok", event_id="e", titles={"fr": "Bonjour"}).to_dict()
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="e", titles={}).to_dict()


def test_content_length():
    Event(source_id="ok", event_id="e", title="t", content="x" * 4000).to_dict()
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="e", title="t", content="x" * 4001).to_dict()


def test_lang_level_url():
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="e", title="t", lang="jp").to_dict()
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="e", title="t", level="urgent").to_dict()
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="e", title="t", url="ftp://x").to_dict()


def test_symbols_and_tags_limits():
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="e", title="t", symbols=["BTC"] * 21).to_dict()
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="e", title="t", tags="not-a-list").to_dict()
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="e", title="t", symbols=["BTC", ""]).to_dict()


def test_published_at_conversions():
    dt = datetime(2025, 9, 5, 10, 30, tzinfo=timezone.utc)
    assert Event(source_id="ok", event_id="e", title="t", published_at=dt).to_dict()["published_at"] == 1757068200
    assert Event(source_id="ok", event_id="e", title="t", published_at=1757068200123).to_dict()["published_at"] == 1757068200
    assert Event(source_id="ok", event_id="e", title="t", published_at=1757068200.9).to_dict()["published_at"] == 1757068200
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="e", title="t", published_at="yesterday").to_dict()
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="e", title="t", published_at=-5).to_dict()


def test_raw_must_be_dict():
    with pytest.raises(ValidationError):
        Event(source_id="ok", event_id="e", title="t", raw=[1, 2]).to_dict()
