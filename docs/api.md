# Tokenearly Signal API reference

Last updated: 2026-09-07 · 中文版: [api.zh.md](api.zh.md)

The Tokenearly Signal API is an HTTP endpoint that external data providers use to push events ("signals") into Tokenearly. One event is one `POST` request. Tokenearly stores the event, matches it against subscribers' settings and delivers it over Telegram, Bark, PushDeer, WeCom, DingTalk, Feishu and Webhook in each subscriber's language (Chinese, English or Korean). No SDK is required; the clients in this repository are thin wrappers around the request described here.

## 1. Endpoint and authentication

```
POST https://api.tokenearly.com/receive_signal
Content-Type: application/json
X-Signal-Token: <token issued by Tokenearly>
```

`Authorization: Bearer <token>` is accepted as an alternative to `X-Signal-Token`. Tokens are issued per provider: ask in the Telegram group https://t.me/ismetaverse or through https://tokenearly.com/dashboard.

## 2. Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `source_id` | string | yes | Your signal source identifier. Lowercase letters, digits and underscores, 2–64 characters, never changes (example: `my_signal`). |
| `event_id` | string | yes | Unique event ID, at most 128 characters, unique within your `source_id`. Re-sending the same `event_id` never notifies subscribers twice, so retries are safe. |
| `titles` | object | one of `titles` / `title` | Title in up to three languages, `{"zh": "...", "en": "...", "ko": "..."}`, each at most 200 characters. Missing languages fall back to the ones you provide. |
| `title` | string | one of `titles` / `title` | Single-language title; pair it with `lang`. |
| `contents` | object | no | Body text in up to three languages, `{"zh": "...", "en": "...", "ko": "..."}`, each at most 4000 characters. Plain text; line breaks are kept, HTML is not rendered. |
| `content` | string | no | Single-language body. |
| `lang` | string | no | Language of `title` / `content`: `zh`, `en` or `ko`. Default `zh`. |
| `url` | string | no | Link to details. Must start with `http://` or `https://`. |
| `level` | string | no | `info` (default), `warning` or `critical`. |
| `symbols` | string[] | no | Related coin tickers such as `["BTC", "ETH"]`, at most 20. |
| `tags` | string[] | no | Free-form tags, at most 20. |
| `published_at` | integer | no | When the event happened, Unix seconds (milliseconds are converted automatically). Defaults to the time the request is received. |
| `raw` | object | no | Your original data. Stored as-is for traceability, never shown to subscribers. |
| `silent` | boolean | no | `true` = store only, notify nobody. Use it to backfill history. Default `false`. |
| `source` | object | no | Display information for your source, recommended on the first request. See below. |

### The `source` object

Send it with the first event (later events can omit it; Tokenearly staff can also edit it):

```json
"source": {
  "name":         {"zh": "我的信号", "en": "My Signal", "ko": "내 시그널"},
  "description":  {"zh": "一句话说明这个信号是什么", "en": "One sentence about this signal", "ko": "이 시그널에 대한 한 줄 설명"},
  "monitor_type": {"zh": "异动提醒", "en": "Movement alerts", "ko": "변동 알림"},
  "icon":         "https://example.com/favicon.ico"
}
```

`name`, `description` and `monitor_type` may also be plain strings. These values are shown to subscribers, so do not put internal parameters (polling intervals, API keys) in them.

## 3. Examples

curl:

```bash
curl -X POST https://api.tokenearly.com/receive_signal \
  -H "Content-Type: application/json" \
  -H "X-Signal-Token: $TOKEN" \
  -d '{
    "source_id": "my_signal",
    "event_id": "btc-breakout-20260905-1030",
    "titles": {"zh": "🚀 BTC 突破 70000", "en": "🚀 BTC breaks 70000", "ko": "🚀 BTC 70000 돌파"},
    "contents": {"zh": "现价: $70120\n24h: +4.2%", "en": "Price: $70120\n24h: +4.2%", "ko": "현재가: $70120\n24h: +4.2%"},
    "url": "https://example.com/btc",
    "level": "warning",
    "symbols": ["BTC"],
    "published_at": 1757068200,
    "source": {"name": {"zh": "我的信号", "en": "My Signal", "ko": "내 시그널"}}
  }'
```

Python with the SDK:

```python
from tokenearly_signal import SignalClient, Event

client = SignalClient(token="YOUR_TOKEN")
result = client.send(Event(
    source_id="my_signal",
    event_id="btc-breakout-20260905-1030",
    titles={"zh": "🚀 BTC 突破 70000", "en": "🚀 BTC breaks 70000", "ko": "🚀 BTC 70000 돌파"},
    symbols=["BTC"],
    level="warning",
))
print(result.status, result.pushed)
```

Python without the SDK:

```python
import httpx
httpx.post("https://api.tokenearly.com/receive_signal",
           headers={"X-Signal-Token": TOKEN},
           json={"source_id": "my_signal", "event_id": "evt-1", "title": "Test signal", "lang": "en"},
           timeout=10)
```

JavaScript (Node 18+ or browser):

```javascript
await fetch("https://api.tokenearly.com/receive_signal", {
  method: "POST",
  headers: {"Content-Type": "application/json", "X-Signal-Token": TOKEN},
  body: JSON.stringify({source_id: "my_signal", event_id: "evt-1", title: "Test signal", lang: "en"})
});
```

## 4. Responses

| HTTP | Body | Meaning | What to do |
|---|---|---|---|
| 200 | `{"status": "success"}` | Accepted; will be pushed to subscribers. A repeated `event_id` also returns 200 but is not pushed again. | Nothing |
| 200 | `{"status": "stored", "pushed": false}` | `silent: true` — stored, nobody notified | Nothing |
| 202 | `{"status": "pending_review"}` | First time this `source_id` was seen. The event is stored; the source waits for Tokenearly review | Ask Tokenearly to review; keep sending in the meantime |
| 400 | `{"code": "contract_error", "msg": "..."}` | A field is missing or malformed; `msg` says which | Fix the payload. Do not retry the same request |
| 400 | `{"code": "invalid_json"}` | Body is not valid JSON | Fix the request |
| 401 | `{"code": "unauthorized"}` | Token missing or wrong | Check `X-Signal-Token` |
| 403 | `{"code": "source_disabled"}` | This source has been disabled | Contact Tokenearly |
| 5xx / timeout | — | Tokenearly-side problem | Retry with exponential backoff: 1 s, 2 s, 4 s … capped at 15 s |

## 5. Conventions

- **Idempotency**: one event, one `event_id`. Re-sending is safe and never double-notifies. Use a different `event_id` for the same market event on a different day.
- **Timeliness**: send as soon as the event happens and set `published_at` to the real event time.
- **Rate**: more than 100 events per minute from one `source_id` — talk to us first.
- **Content**: keep the title to one line; put details in the body. Bodies are delivered as plain text; HTML is not rendered. Do not put long contract addresses in the title.
- **Languages**: provide `titles` and `contents` in all three languages whenever you can; subscribers receive the version matching their interface language. Single-language events are delivered as-is to everyone.
- **Backfill**: add `silent: true` when importing history so subscribers are not flooded.

## 6. Onboarding

1. Request a token from Tokenearly.
2. Send the first event with your `source_id` (include the `source` display object). Expect HTTP 202.
3. After Tokenearly approves the source, further events return HTTP 200 and subscribers can enable your source in their dashboard at https://tokenearly.com/dashboard.

## FAQ

**Do subscribers see my raw data?** No. `raw` is stored for traceability only. Subscribers see `titles` / `contents`, `url`, `level` and `symbols`.

**What happens if I send the same `event_id` twice?** The second request returns HTTP 200 and nobody is notified again.

**Which languages do I have to provide?** At least one. Provide all three (`zh`, `en`, `ko`) for the best experience; otherwise everyone receives the language you sent.

---

Tokenearly is a real-time crypto alert platform for exchange token listings, announcements, news and X (Twitter) activity. It monitors 10 crypto exchanges (Binance, OKX, Bybit, Bitget, MEXC, Gate.io, HTX, KuCoin, Upbit, Bithumb) — Binance and Gate.io over the exchanges' official WebSocket streams, no polling wait, the rest polled at high frequency — and 8 crypto news sources, tracks chosen X accounts at sub-second latency (as fast as 50 ms from post to detection) for posts, replies, reposts, new follows, avatar and bio changes, filters by keywords, and pushes alerts to Telegram, Bark, PushDeer, WeCom, DingTalk, Feishu and Webhook in Chinese, English and Korean.
