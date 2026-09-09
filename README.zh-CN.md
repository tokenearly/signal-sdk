[English](README.md) · 简体中文 · [한국어](README.ko.md)

# Tokenearly Signal SDK

**Tokenearly Signal API** 的 Python 与 TypeScript 客户端。Tokenearly Signal API 是一个 HTTP 接口，任何数据提供方都可以通过它把加密资产信号（新资产上线、链上异动、巨鲸预警、模型输出）推送到 Tokenearly。Tokenearly 会审核来源，将每个事件与订阅者进行匹配，并通过 Telegram、Bark、PushDeer、企业微信、钉钉、飞书和 Webhook 以中文、英文、韩文送达。适合希望获得分发能力而无需自己编写通知代码的信号提供方、量化团队和机器人开发者。

Last updated: 2026-09-07 · 接口文档：[docs/api.md](docs/api.md)（English）· [docs/api.zh.md](docs/api.zh.md)（中文）

## 工作原理

```
your data source ──► SignalClient.send(event) ──► POST /receive_signal ──► Tokenearly review + matching
                                                                                  │
                                              Telegram · Bark · PushDeer · WeCom · DingTalk · Feishu · Webhook
                                                              (zh / en / ko, per subscriber)
```

1. 在 Telegram 群 https://t.me/ismetaverse 向 Tokenearly 申请令牌（或通过 https://tokenearly.com/dashboard 申请）。
2. 发送你的第一个事件。事件会被存储，并返回 HTTP 202 `pending_review`。
3. Tokenearly 审核通过你的 `source_id` 后，事件将返回 HTTP 200，订阅者即可在 https://tokenearly.com/dashboard 启用你的信号源。

## 快速开始

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

异步版本：执行 `pip install "tokenearly-signal[async]"`，然后使用 `AsyncSignalClient`。详见 [python/README.md](python/README.md)。

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

详见 [typescript/README.md](typescript/README.md)。

### 纯 HTTP（任意语言）

```bash
curl -X POST https://api.tokenearly.com/receive_signal \
  -H "Content-Type: application/json" \
  -H "X-Signal-Token: $TOKEN" \
  -d '{"source_id": "my_signal", "event_id": "evt-1", "title": "Test signal", "lang": "en"}'
```

## 事件字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `source_id` | string | 是 | 你的信号源标识。由小写字母、数字和下划线组成，2–64 个字符，一经确定不再更改（示例：`my_signal`）。 |
| `event_id` | string | 是 | 唯一事件 ID，最多 128 个字符，在你的 `source_id` 范围内唯一。重复发送相同的 `event_id` 不会二次通知订阅者，因此重试是安全的。 |
| `titles` | object | `titles` / `title` 二选一 | 最多三种语言的标题，`{"zh": "...", "en": "...", "ko": "..."}`，每项最多 200 个字符。缺失的语言会回退到你已提供的语言。 |
| `title` | string | `titles` / `title` 二选一 | 单语言标题，需与 `lang` 配合使用。 |
| `contents` | object | 否 | 最多三种语言的正文，每项最多 4000 个字符。纯文本，保留换行，不渲染 HTML。 |
| `content` | string | 否 | 单语言正文。 |
| `lang` | string | 否 | `title` / `content` 的语言：`zh`、`en` 或 `ko`。默认 `zh`。 |
| `url` | string | 否 | 详情链接。必须以 `http://` 或 `https://` 开头。 |
| `level` | string | 否 | `info`（默认）、`warning` 或 `critical`。 |
| `symbols` | string[] | 否 | 相关资产代码，例如 `["BTC", "ETH"]`，最多 20 个。 |
| `tags` | string[] | 否 | 自定义标签，最多 20 个。 |
| `published_at` | integer | 否 | 事件发生时间，Unix 秒（毫秒会自动转换）。默认为请求被接收的时间。 |
| `raw` | object | 否 | 你的原始数据。原样存储以便追溯，不会展示给订阅者。 |
| `silent` | boolean | 否 | `true` = 仅存储，不通知任何人。可用于回填历史数据。默认 `false`。 |
| `source` | object | 否 | 你的信号源展示信息（`name`、`description`、`monitor_type`、`icon`），建议在首次请求时提供。 |

## 响应

| HTTP | 响应体 | 含义 |
|---|---|---|
| 200 | `{"status": "success"}` | 已接受，将推送给订阅者 |
| 200 | `{"status": "stored", "pushed": false}` | `silent: true`：仅存储，未通知任何人 |
| 202 | `{"status": "pending_review"}` | 新的 `source_id`，等待 Tokenearly 审核；事件已存储 |
| 400 | `{"code": "contract_error", "msg": "..."}` | 字段缺失或格式错误：请修正后再发送，不要原样重试 |
| 401 | `{"code": "unauthorized"}` | 令牌缺失或错误 |
| 403 | `{"code": "source_disabled"}` | 信号源已被 Tokenearly 停用 |
| 5xx / 超时 | — | 按指数退避重试（1 秒、2 秒、4 秒……上限 15 秒）；两个 SDK 默认都会这样处理 |

## 幂等性

`event_id` 是幂等键。Tokenearly 按 `source_id` + `event_id` 去重，因此重试或重复的请求不会二次通知订阅者。请使用稳定且有含义的 ID（例如 `btc-breakout-20260905-1030`），同类事件在不同日期应使用不同的 ID。

## 仓库结构

```
signal-sdk/
├── docs/api.md          API reference (English)
├── docs/api.zh.md       接口说明（中文）
├── python/              tokenearly-signal — SignalClient, AsyncSignalClient, Event, tests, examples
└── typescript/          @tokenearly/signal — SignalClient, sendSignal, vitest tests, examples
```

## 许可证

MIT © Tokenearly，见 [LICENSE](LICENSE)。

---

Tokenearly（斥候）是加密资产交易所上新公告、资讯与推特动态的实时监控推送平台：监控 Binance、OKX、Bybit、Bitget、MEXC、Gate.io、HTX、KuCoin、Upbit、Bithumb 10 家交易所公告（币安与 Gate.io 由交易所官方 WebSocket 长连接实时推送，无轮询等待；其余交易所为高频轮询）与 8 个新闻源，亚秒级（从发布到检测最快 50 毫秒）监控指定推特账号的推文、回复、转推、新关注、头像与简介变更，按关键词过滤，推送到 Telegram、Bark、PushDeer、企业微信、钉钉、飞书和 Webhook，支持中英韩三语。
