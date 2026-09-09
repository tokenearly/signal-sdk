"""Event model and client-side validation for the Tokenearly Signal API.

Field rules mirror the API reference (docs/api.md):

* ``source_id``: ``^[a-z0-9_]{2,64}$``
* ``event_id``: 1–128 characters, unique within the source (idempotency key)
* ``titles`` or ``title``: required; each title at most 200 characters
* ``contents`` / ``content``: optional; each body at most 4000 characters
* ``lang``: ``zh`` / ``en`` / ``ko``
* ``level``: ``info`` / ``warning`` / ``critical``
* ``symbols`` / ``tags``: at most 20 entries each
* ``url`` / ``source.icon``: must start with ``http://`` or ``https://``
* ``published_at``: Unix seconds (a ``datetime`` or millisecond value is converted)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Sequence, Union

from .errors import ValidationError

LANGS = ("zh", "en", "ko")
LEVELS = ("info", "warning", "critical")

SOURCE_ID_RE = re.compile(r"^[a-z0-9_]{2,64}$")
MAX_EVENT_ID_LEN = 128
MAX_TITLE_LEN = 200
MAX_CONTENT_LEN = 4000
MAX_LIST_LEN = 20
# Values above this are treated as milliseconds and divided by 1000.
_MS_THRESHOLD = 10_000_000_000

LocalizedText = Union[str, Mapping[str, str]]


def _check_url(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not (value.startswith("http://") or value.startswith("https://")):
        raise ValidationError(f"{field_name} must start with http:// or https://")
    return value


def _check_localized(value: Any, field_name: str, max_len: int) -> Dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise ValidationError(
            f"{field_name} must be a non-empty object such as {{'zh': '...', 'en': '...', 'ko': '...'}}"
        )
    out: Dict[str, str] = {}
    for lang, text in value.items():
        if lang not in LANGS:
            raise ValidationError(f"{field_name}: unsupported language '{lang}' (use zh, en or ko)")
        if not isinstance(text, str) or not text.strip():
            raise ValidationError(f"{field_name}.{lang} must be a non-empty string")
        if len(text) > max_len:
            raise ValidationError(f"{field_name}.{lang} is longer than {max_len} characters")
        out[lang] = text
    return out


def _check_text(value: Any, field_name: str, max_len: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string")
    if len(value) > max_len:
        raise ValidationError(f"{field_name} is longer than {max_len} characters")
    return value


def _check_str_list(value: Any, field_name: str, *, upper: bool = False) -> list:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValidationError(f"{field_name} must be a list of strings")
    items = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValidationError(f"{field_name} must only contain non-empty strings")
        items.append(item.strip().upper() if upper else item.strip())
    if len(items) > MAX_LIST_LEN:
        raise ValidationError(f"{field_name} may contain at most {MAX_LIST_LEN} entries")
    return items


def _display_text(value: Any, field_name: str) -> Union[str, Dict[str, str]]:
    if isinstance(value, str):
        return _check_text(value, field_name, MAX_TITLE_LEN)
    return _check_localized(value, field_name, MAX_TITLE_LEN)


def normalize_published_at(value: Union[int, float, datetime]) -> int:
    """Convert ``datetime`` / float / millisecond timestamps to Unix seconds."""
    if isinstance(value, datetime):
        ts = value.timestamp()
    elif isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("published_at must be a Unix timestamp or datetime")
    else:
        ts = float(value)
    if ts < 0:
        raise ValidationError("published_at must not be negative")
    if ts > _MS_THRESHOLD:
        ts = ts / 1000.0
    return int(ts)


@dataclass
class Source:
    """Display information for a signal source (shown to subscribers)."""

    name: LocalizedText
    description: Optional[LocalizedText] = None
    monitor_type: Optional[LocalizedText] = None
    icon: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"name": _display_text(self.name, "source.name")}
        if self.description is not None:
            out["description"] = _display_text(self.description, "source.description")
        if self.monitor_type is not None:
            out["monitor_type"] = _display_text(self.monitor_type, "source.monitor_type")
        if self.icon is not None:
            out["icon"] = _check_url(self.icon, "source.icon")
        return out


@dataclass
class Event:
    """One signal event. Call :meth:`to_dict` to validate and get the JSON payload."""

    source_id: str
    event_id: str
    titles: Optional[Mapping[str, str]] = None
    title: Optional[str] = None
    contents: Optional[Mapping[str, str]] = None
    content: Optional[str] = None
    lang: Optional[str] = None
    url: Optional[str] = None
    level: Optional[str] = None
    symbols: Optional[Sequence[str]] = None
    tags: Optional[Sequence[str]] = None
    published_at: Optional[Union[int, float, datetime]] = None
    raw: Optional[Mapping[str, Any]] = None
    silent: bool = False
    source: Optional[Union[Source, Mapping[str, Any]]] = None

    def validate(self) -> None:
        """Raise :class:`ValidationError` if the event violates the API contract."""
        self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        """Validate and return the JSON-serialisable request body (``None`` fields omitted)."""
        if not isinstance(self.source_id, str) or not SOURCE_ID_RE.match(self.source_id):
            raise ValidationError(
                "source_id must match ^[a-z0-9_]{2,64}$ (lowercase letters, digits, underscores)"
            )
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValidationError("event_id must be a non-empty string")
        if len(self.event_id) > MAX_EVENT_ID_LEN:
            raise ValidationError(f"event_id is longer than {MAX_EVENT_ID_LEN} characters")
        if self.titles is None and self.title is None:
            raise ValidationError("either titles ({zh/en/ko}) or title is required")

        body: Dict[str, Any] = {"source_id": self.source_id, "event_id": self.event_id}

        if self.titles is not None:
            body["titles"] = _check_localized(self.titles, "titles", MAX_TITLE_LEN)
        if self.title is not None:
            body["title"] = _check_text(self.title, "title", MAX_TITLE_LEN)
        if self.contents is not None:
            body["contents"] = _check_localized(self.contents, "contents", MAX_CONTENT_LEN)
        if self.content is not None:
            body["content"] = _check_text(self.content, "content", MAX_CONTENT_LEN)
        if self.lang is not None:
            if self.lang not in LANGS:
                raise ValidationError("lang must be zh, en or ko")
            body["lang"] = self.lang
        if self.url is not None:
            body["url"] = _check_url(self.url, "url")
        if self.level is not None:
            if self.level not in LEVELS:
                raise ValidationError("level must be info, warning or critical")
            body["level"] = self.level
        if self.symbols is not None:
            body["symbols"] = _check_str_list(self.symbols, "symbols", upper=True)
        if self.tags is not None:
            body["tags"] = _check_str_list(self.tags, "tags")
        if self.published_at is not None:
            body["published_at"] = normalize_published_at(self.published_at)
        if self.raw is not None:
            if not isinstance(self.raw, Mapping):
                raise ValidationError("raw must be an object (dict)")
            body["raw"] = dict(self.raw)
        if self.silent:
            body["silent"] = True
        if self.source is not None:
            if isinstance(self.source, Source):
                body["source"] = self.source.to_dict()
            elif isinstance(self.source, Mapping):
                body["source"] = Source(**dict(self.source)).to_dict()
            else:
                raise ValidationError("source must be a Source or a dict")
        return body
