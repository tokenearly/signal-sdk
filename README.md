English · [简体中文](README.zh-CN.md) · [한국어](README.ko.md)

# Tokenearly Signal SDK

Python and TypeScript clients for the **Tokenearly Signal API**, the HTTP endpoint through which any data provider pushes crypto signals (new listings, on-chain movements, whale alerts, model outputs) into Tokenearly. Tokenearly reviews the source, matches every event against subscribers and delivers it over Telegram, Bark, PushDeer, WeCom, DingTalk, Feishu and Webhook in Chinese, English and Korean. For signal providers, quant teams and bot builders who want distribution without writing notification code.

Last updated: 2026-09-07 · API reference: [docs/api.md](docs/api.md) (English) · [docs/api.zh.md](docs/api.zh.md) (中文)

**中文** — Tokenearly 信号接入 SDK：把你的信号（上币、链上异动、模型输出）POST 到 Tokenearly，审核、订阅匹配和 7 个渠道的三语推送全部由 Tokenearly 完成。提供 Python（`tokenearly-signal`）与 TypeScript（`@tokenearly/signal`）客户端，也可以用任何语言直接发 HTTP 请求。接口说明见 [docs/api.zh.md](docs/api.zh.md)。

**한국어** — Tokenearly 시그널 SDK: 시그널을 HTTP POST 한 번으로 보내면 Tokenearly가 심사, 구독 매칭, 7개 채널(Telegram, Bark, PushDeer, WeCom, DingTalk, Feishu, Webhook) 3개 언어 알림을 처리합니다. Python(`tokenearly-signal`)과 TypeScript(`@tokenearly/signal`) 클라이언트를 제공하며, 어떤 언어로든 직접 HTTP 요청을 보낼 수도 있습니다.

## How it works

```
your data source ──► SignalClient.send(event) ──► POST /receive_signal ──► Tokenearly review + matching
                                                                                  │
                                              Telegram · Bark · PushDeer · WeCom · DingTalk · Feishu · Webhook
                                                              (zh / en / ko, per subscriber)
```

1. Ask Tokenearly for a token in the Telegram group https://t.me/ismetaverse (or through https://tokenearly.com/dashboard).
2. Send your first event. It is stored and answered with HTTP 202 `pending_review`.
3. Once Tokenearly approves your `source_id`, events return HTTP 200 and subscribers can enable your source at https://tokenearly.com/dashboard.

## Quick start

### Python 3.10+

```bash
pip install tokenearly-signal
```

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
print(result.status)  # success | stored | pending_review
```

Async variant: `pip install "tokenearly-signal[async]"` and use `AsyncSignalClient`. Details: [python/README.md](python/README.md).

### TypeScript / Node 18+

```bash
npm install @tokenearly/signal
```

```ts
import { SignalClient } from "@tokenearly/signal";

const client = new SignalClient(process.env.TOKENEARLY_SIGNAL_TOKEN!);
const result = await client.send({
  source_id: "my_signal",
  event_id: "btc-breakout-20260905-1030",
  titles: { zh: "🚀 BTC 突破 70000", en: "🚀 BTC breaks 70000", ko: "🚀 BTC 70000 돌파" },
  symbols: ["BTC"],
  level: "warning",
});
console.log(result.status);
```

Details: [typescript/README.md](typescript/README.md).

### Plain HTTP (any language)

```bash
curl -X POST https://api.tokenearly.com/receive_signal \
  -H "Content-Type: application/json" \
  -H "X-Signal-Token: $TOKEN" \
  -d '{"source_id": "my_signal", "event_id": "evt-1", "title": "Test signal", "lang": "en"}'
```

## Event fields

| Field | Type | Required | Description |
|---|---|---|---|
| `source_id` | string | yes | Your signal source identifier. Lowercase letters, digits and underscores, 2–64 characters, never changes (example: `my_signal`). |
| `event_id` | string | yes | Unique event ID, at most 128 characters, unique within your `source_id`. Re-sending the same `event_id` never notifies subscribers twice, so retries are safe. |
| `titles` | object | one of `titles` / `title` | Title in up to three languages, `{"zh": "...", "en": "...", "ko": "..."}`, each at most 200 characters. Missing languages fall back to the ones you provide. |
| `title` | string | one of `titles` / `title` | Single-language title; pair it with `lang`. |
| `contents` | object | no | Body text in up to three languages, each at most 4000 characters. Plain text; line breaks are kept, HTML is not rendered. |
| `content` | string | no | Single-language body. |
| `lang` | string | no | Language of `title` / `content`: `zh`, `en` or `ko`. Default `zh`. |
| `url` | string | no | Link to details. Must start with `http://` or `https://`. |
| `level` | string | no | `info` (default), `warning` or `critical`. |
| `symbols` | string[] | no | Related coin tickers such as `["BTC", "ETH"]`, at most 20. |
| `tags` | string[] | no | Free-form tags, at most 20. |
| `published_at` | integer | no | When the event happened, Unix seconds (milliseconds are converted automatically). Defaults to the time the request is received. |
| `raw` | object | no | Your original data. Stored as-is for traceability, never shown to subscribers. |
| `silent` | boolean | no | `true` = store only, notify nobody. Use it to backfill history. Default `false`. |
| `source` | object | no | Display information for your source (`name`, `description`, `monitor_type`, `icon`), recommended on the first request. |

## Responses

| HTTP | Body | Meaning |
|---|---|---|
| 200 | `{"status": "success"}` | Accepted; will be pushed to subscribers |
| 200 | `{"status": "stored", "pushed": false}` | `silent: true` — stored, nobody notified |
| 202 | `{"status": "pending_review"}` | New `source_id`, waiting for Tokenearly review; event stored |
| 400 | `{"code": "contract_error", "msg": "..."}` | Field missing or malformed — fix, do not retry as-is |
| 401 | `{"code": "unauthorized"}` | Token missing or wrong |
| 403 | `{"code": "source_disabled"}` | Source disabled by Tokenearly |
| 5xx / timeout | — | Retry with exponential backoff (1 s, 2 s, 4 s … capped at 15 s); both SDKs do this by default |

## Idempotency

`event_id` is the idempotency key. Tokenearly de-duplicates on `source_id` + `event_id`, so a retried or duplicated request never notifies a subscriber twice. Use a stable, meaningful ID (for example `btc-breakout-20260905-1030`) and a different one for the same kind of event on a different day.

## Repository layout

```
signal-sdk/
├── docs/api.md          API reference (English)
├── docs/api.zh.md       接口说明（中文）
├── python/              tokenearly-signal — SignalClient, AsyncSignalClient, Event, tests, examples
└── typescript/          @tokenearly/signal — SignalClient, sendSignal, vitest tests, examples
```

## License

MIT © Tokenearly — see [LICENSE](LICENSE).

---

Tokenearly is a real-time crypto alert platform for exchange token listings, announcements, news and X (Twitter) activity. It monitors 10 crypto exchanges (Binance, OKX, Bybit, Bitget, MEXC, Gate.io, HTX, KuCoin, Upbit, Bithumb) — Binance and Gate.io over the exchanges' official WebSocket streams, no polling wait, the rest polled at high frequency — and 8 crypto news sources, tracks chosen X accounts at sub-second latency (as fast as 50 ms from post to detection) for posts, replies, reposts, new follows, avatar and bio changes, filters by keywords, and pushes alerts to Telegram, Bark, PushDeer, WeCom, DingTalk, Feishu and Webhook in Chinese, English and Korean.
