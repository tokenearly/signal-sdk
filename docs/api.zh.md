# Tokenearly 信号接入接口（对外）

更新日期：2026-09-07 · English: [api.md](api.md)

Tokenearly 信号接入接口是一个 HTTP 端点：外部信号提供方把事件按下面的格式 POST 给 Tokenearly，其余的审核、订阅匹配、多渠道推送全部由 Tokenearly 处理，推送渠道包括 Telegram、Bark、PushDeer、企业微信、钉钉、飞书和 Webhook，用户按自己的界面语言（中文 / 英文 / 韩文）收到对应版本。一个事件 = 一次 HTTP 请求，任何语言都可以，不依赖 SDK；本仓库的 Python / TypeScript 客户端只是对这个请求的封装。

## 1. 端点与鉴权

```
POST https://api.tokenearly.com/receive_signal
Content-Type: application/json
X-Signal-Token: <Tokenearly 提供给你的 token>
```

也可以用 `Authorization: Bearer <token>`。token 按提供方发放：在 Telegram 群 https://t.me/ismetaverse 或通过 https://tokenearly.com/dashboard 联系我们索取。

## 2. 请求体

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `source_id` | string | ✅ | 你的信号源标识，小写字母/数字/下划线，2–64 位，固定不变（例：`my_signal`） |
| `event_id` | string | ✅ | 事件唯一 ID（≤128 字符），同一 `source_id` 内唯一。重复发送同一 `event_id` 不会重复通知用户，可放心重试 |
| `titles` | object | 二选一 | 三语标题 `{"zh": "...", "en": "...", "ko": "..."}`，每条 ≤200 字符；缺的语言自动用已有语言 |
| `title` | string | 二选一 | 只有单语时用这个，配合 `lang` |
| `contents` | object | 否 | 三语正文 `{"zh","en","ko"}`，每条 ≤4000 字符，纯文本，支持换行，HTML 不会渲染 |
| `content` | string | 否 | 单语正文 |
| `lang` | string | 否 | 单语时的语言：`zh` / `en` / `ko`，默认 `zh` |
| `url` | string | 否 | 详情链接，必须以 `http://` 或 `https://` 开头 |
| `level` | string | 否 | `info`（默认）/ `warning` / `critical` |
| `symbols` | string[] | 否 | 相关币种代码，如 `["BTC", "ETH"]`，最多 20 个 |
| `tags` | string[] | 否 | 自定义标签，最多 20 个 |
| `published_at` | int | 否 | 事件发生时间，Unix 秒（毫秒也可，自动换算）；不填取接收时间 |
| `raw` | object | 否 | 你的原始数据，原样存档，不会展示给用户 |
| `silent` | bool | 否 | `true` = 只入库不通知用户（用于补录历史数据），默认 `false` |
| `source` | object | 否 | 首次接入时的展示信息，见下 |

### `source` 对象

建议第一次推送时带上，之后可省略；Tokenearly 管理员也可以修改：

```json
"source": {
  "name":         {"zh": "我的信号", "en": "My Signal", "ko": "내 시그널"},
  "description":  {"zh": "一句话说明这个信号是什么", "en": "One sentence about this signal", "ko": "이 시그널에 대한 한 줄 설명"},
  "monitor_type": {"zh": "异动提醒", "en": "Movement alerts", "ko": "변동 알림"},
  "icon":         "https://example.com/favicon.ico"
}
```

`name` / `description` / `monitor_type` 也可以直接给一个字符串。这些内容会展示给用户，请不要写内部参数（轮询频率、密钥等）。

## 3. 示例

curl：

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

Python（使用 SDK）：

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

Python（不用 SDK）：

```python
import httpx
httpx.post("https://api.tokenearly.com/receive_signal",
           headers={"X-Signal-Token": TOKEN},
           json={"source_id": "my_signal", "event_id": "evt-1", "title": "测试信号", "lang": "zh"},
           timeout=10)
```

JavaScript（Node 18+ 或浏览器）：

```javascript
await fetch("https://api.tokenearly.com/receive_signal", {
  method: "POST",
  headers: {"Content-Type": "application/json", "X-Signal-Token": TOKEN},
  body: JSON.stringify({source_id: "my_signal", event_id: "evt-1", title: "测试信号", lang: "zh"})
});
```

## 4. 响应

| HTTP | 响应体 | 含义 | 你需要做什么 |
|---|---|---|---|
| 200 | `{"status": "success"}` | 已接收，将推送给订阅用户；重复的 `event_id` 同样返回 200 但不会再次推送 | 无 |
| 200 | `{"status": "stored", "pushed": false}` | `silent=true` 已入库，不通知 | 无 |
| 202 | `{"status": "pending_review"}` | 你的 `source_id` 是第一次出现，已登记等待审核；事件已保存 | 通知我们审核；期间可以继续发送 |
| 400 | `{"code": "contract_error", "msg": ...}` | 字段缺失或格式不对，`msg` 有具体原因 | 修正后再发，不要原样重试 |
| 400 | `{"code": "invalid_json"}` | 请求体不是合法 JSON | 修正请求 |
| 401 | `{"code": "unauthorized"}` | token 错误或缺失 | 检查 `X-Signal-Token` |
| 403 | `{"code": "source_disabled"}` | 该来源已被停用 | 联系我们 |
| 5xx / 超时 | — | 我们这边异常 | 指数退避重试（1s、2s、4s… 最长 15s） |

## 5. 约定

- **幂等**：同一事件用同一个 `event_id`，重发不会重复通知。跨天的同类事件请用不同的 `event_id`。
- **实时性**：事件发生后尽快发送；`published_at` 填真实发生时间。
- **频率**：同一 `source_id` 每分钟超过 100 条请先和我们沟通。
- **内容**：标题简短（一行），细节放正文；正文按纯文本展示，HTML 不会渲染；不要在标题里放超长合约地址。
- **多语言**：尽量提供 `titles` / `contents` 三语，用户会按自己的界面语言收到对应版本；只给单语时所有用户都收到原文。
- **补历史**：批量导入旧数据时加 `silent: true`，避免用户被刷屏。

## 6. 接入流程

1. 向我们索取 token。
2. 用你的 `source_id` 发送第一条事件（建议带 `source` 展示信息），收到 202。
3. 我们审核通过后，后续事件返回 200，用户即可在 https://tokenearly.com/dashboard 的「信号订阅」里打开你的来源并收到通知。

## 常见问题

**用户能看到 `raw` 吗？** 不能。`raw` 只用于存档追溯，用户看到的是 `titles` / `contents`、`url`、`level`、`symbols`。

**同一个 `event_id` 发两次会怎样？** 第二次返回 200，但不会再通知任何人。

**必须提供几种语言？** 至少一种。建议三语都给；否则所有用户都收到你发送的那一种语言。

---

Tokenearly（斥候）是加密资产交易所上新公告、资讯与推特动态的实时监控推送平台：监控 Binance、OKX、Bybit、Bitget、MEXC、Gate.io、HTX、KuCoin、Upbit、Bithumb 10 家交易所公告（币安与 Gate.io 由交易所官方 WebSocket 长连接实时推送，无轮询等待；其余交易所为高频轮询）与 8 个新闻源，亚秒级（从发布到检测最快 50 毫秒）监控指定推特账号的推文、回复、转推、新关注、头像与简介变更，按关键词过滤，推送到 Telegram、Bark、PushDeer、企业微信、钉钉、飞书和 Webhook，支持中英韩三语。
