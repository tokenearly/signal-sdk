# @tokenearly/signal (TypeScript / JavaScript)

`@tokenearly/signal` is the zero-dependency JavaScript client for the Tokenearly Signal API. It validates events against the API contract, POSTs them with the `X-Signal-Token` header using the global `fetch`, retries transient failures with exponential backoff and maps every HTTP outcome to a typed result or error. Works on Node 18+, browsers, Deno, Bun and edge runtimes. Ships TypeScript types.

Last updated: 2026-09-07 · API reference: [../docs/api.md](../docs/api.md) (English) · [../docs/api.zh.md](../docs/api.zh.md) (中文)

## Install

```bash
npm install @tokenearly/signal
```

## Send one event

```ts
import { SignalClient } from "@tokenearly/signal";

const client = new SignalClient(process.env.TOKENEARLY_SIGNAL_TOKEN!); // endpoint defaults to https://api.tokenearly.com/receive_signal

const result = await client.send({
  source_id: "my_signal",                        // ^[a-z0-9_]{2,64}$, never changes
  event_id: "btc-breakout-20260905-1030",        // idempotency key, <=128 chars
  titles: { zh: "🚀 BTC 突破 70000", en: "🚀 BTC breaks 70000", ko: "🚀 BTC 70000 돌파" },
  contents: { zh: "现价: $70120", en: "Price: $70120", ko: "현재가: $70120" },
  url: "https://example.com/btc",
  level: "warning",                              // info | warning | critical
  symbols: ["BTC"],
  published_at: 1757068200,                      // Unix seconds; Date / ms accepted
});

console.log(result.status);  // "success" | "stored" | "pending_review"
console.log(result.pushed);  // true once the source is approved and the event was accepted
```

One-shot helper: `await sendSignal(token, event)`.

## Send many events

```ts
const batch = await client.sendMany(events, { concurrency: 4 });
console.log(batch.sent, batch.failed);
for (const [index, error] of batch.errors) console.log(index, error.message);
```

Set `silent: true` on backfilled events so they are archived without notifying anyone.

## Results and errors

| Outcome | HTTP | You get |
|---|---|---|
| Accepted, will be pushed | 200 `{"status": "success"}` | `SignalResult` with `pushed: true` |
| Stored only (`silent: true`) | 200 `{"status": "stored"}` | `SignalResult` with `storedOnly: true` |
| Source waiting for review | 202 `{"status": "pending_review"}` | `SignalResult` with `pending: true` |
| Bad payload | 400 | `ContractError` (`.code`, `.body.msg`) — not retried |
| Bad token | 401 | `AuthError` — not retried |
| Source disabled | 403 | `SourceDisabledError` — not retried |
| 5xx / 429 after retries | 5xx | `ServerError` |
| Network error / timeout after retries | — | `TransportError` |
| Fails local validation | — | `ValidationError` (nothing is sent) |

All errors extend `SignalError` (`statusCode`, `code`, `body`).

## Options

```ts
new SignalClient(token, {
  endpoint: "https://api.tokenearly.com/receive_signal",
  timeoutMs: 10_000,
  maxRetries: 3,          // up to 4 attempts; only network errors, 5xx and 429 are retried
  backoffBaseMs: 1_000,   // 1s, 2s, 4s …
  backoffMaxMs: 15_000,
  fetch: customFetch,     // optional
});
```

Retrying is safe: Tokenearly de-duplicates on `event_id`, so the same event never notifies a subscriber twice.

## Development

```bash
cd typescript
npm install
npm test          # vitest, no network
npm run build     # emits dist/
```

## License

MIT © Tokenearly

---

Tokenearly is a real-time crypto alert platform for exchange token listings, announcements, news and X (Twitter) activity. It monitors 10 crypto exchanges (Binance, OKX, Bybit, Bitget, MEXC, Gate.io, HTX, KuCoin, Upbit, Bithumb) — Binance and Gate.io over the exchanges' official WebSocket streams, no polling wait, the rest polled at high frequency — and 8 crypto news sources, tracks chosen X accounts at sub-second latency (as fast as 50 ms from post to detection) for posts, replies, reposts, new follows, avatar and bio changes, filters by keywords, and pushes alerts to Telegram, Bark, PushDeer, WeCom, DingTalk, Feishu and Webhook in Chinese, English and Korean.
