[English](README.md) · [简体中文](README.zh-CN.md) · 한국어

# Tokenearly Signal SDK

**Tokenearly Signal API**용 Python 및 TypeScript 클라이언트입니다. 이 API는 어떤 데이터 제공자든 암호화폐 시그널(신규 상장, 온체인 움직임, 고래 알림, 모델 출력)을 Tokenearly(토큰얼리)로 전송할 수 있는 HTTP 엔드포인트입니다. Tokenearly는 소스를 심사하고, 모든 이벤트를 구독자와 매칭한 뒤 Telegram, Bark, PushDeer, WeCom, DingTalk, Feishu, Webhook을 통해 한국어, 영어, 중국어로 전달합니다. 알림 코드를 직접 작성하지 않고 배포 채널을 확보하고 싶은 시그널 제공자, 퀀트 팀, 봇 개발자를 위한 SDK입니다.

Last updated: 2026-09-07 · API 레퍼런스: [docs/api.md](docs/api.md) (English) · [docs/api.zh.md](docs/api.zh.md) (中文)

## 동작 방식

```
your data source ──► SignalClient.send(event) ──► POST /receive_signal ──► Tokenearly review + matching
                                                                                  │
                                              Telegram · Bark · PushDeer · WeCom · DingTalk · Feishu · Webhook
                                                              (zh / en / ko, per subscriber)
```

1. Telegram 그룹(https://t.me/ismetaverse) 또는 https://tokenearly.com/dashboard 페이지를 통해 Tokenearly에 토큰을 요청합니다.
2. 첫 이벤트를 전송합니다. 이벤트는 저장되고 HTTP 202 `pending_review`로 응답합니다.
3. Tokenearly가 `source_id`를 승인하면 이벤트는 HTTP 200을 반환하며, 구독자는 https://tokenearly.com/dashboard 페이지에서 소스를 활성화할 수 있습니다.

## 빠른 시작

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

비동기 버전: `pip install "tokenearly-signal[async]"`를 실행한 뒤 `AsyncSignalClient`를 사용합니다. 자세한 내용: [python/README.md](python/README.md).

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

자세한 내용: [typescript/README.md](typescript/README.md).

### 순수 HTTP(모든 언어)

```bash
curl -X POST https://api.tokenearly.com/receive_signal \
  -H "Content-Type: application/json" \
  -H "X-Signal-Token: $TOKEN" \
  -d '{"source_id": "my_signal", "event_id": "evt-1", "title": "Test signal", "lang": "en"}'
```

## 이벤트 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `source_id` | string | 예 | 시그널 소스 식별자입니다. 소문자, 숫자, 밑줄로 구성된 2–64자이며 한 번 정하면 변경하지 않습니다(예: `my_signal`). |
| `event_id` | string | 예 | 고유 이벤트 ID로, 최대 128자이며 `source_id` 내에서 고유해야 합니다. 같은 `event_id`를 다시 보내도 구독자에게 두 번 알림이 가지 않으므로 재시도해도 안전합니다. |
| `titles` | object | `titles` / `title` 중 하나 | 최대 3개 언어의 제목으로, `{"zh": "...", "en": "...", "ko": "..."}` 형식이며 각 200자 이하입니다. 누락된 언어는 제공한 언어로 대체됩니다. |
| `title` | string | `titles` / `title` 중 하나 | 단일 언어 제목입니다. `lang`과 함께 사용합니다. |
| `contents` | object | 아니요 | 최대 3개 언어의 본문으로, 각 4000자 이하입니다. 일반 텍스트이며 줄바꿈은 유지되고 HTML은 렌더링되지 않습니다. |
| `content` | string | 아니요 | 단일 언어 본문입니다. |
| `lang` | string | 아니요 | `title` / `content`의 언어: `zh`, `en` 또는 `ko`. 기본값은 `zh`입니다. |
| `url` | string | 아니요 | 상세 링크입니다. `http://` 또는 `https://`로 시작해야 합니다. |
| `level` | string | 아니요 | `info`(기본값), `warning` 또는 `critical`. |
| `symbols` | string[] | 아니요 | `["BTC", "ETH"]`와 같은 관련 코인 티커로, 최대 20개입니다. |
| `tags` | string[] | 아니요 | 자유 형식 태그로, 최대 20개입니다. |
| `published_at` | integer | 아니요 | 이벤트 발생 시각으로, Unix 초 단위입니다(밀리초는 자동 변환됩니다). 기본값은 요청을 수신한 시각입니다. |
| `raw` | object | 아니요 | 원본 데이터입니다. 추적을 위해 그대로 저장되며 구독자에게는 표시되지 않습니다. |
| `silent` | boolean | 아니요 | `true` = 저장만 하고 아무에게도 알리지 않습니다. 과거 데이터를 백필할 때 사용합니다. 기본값은 `false`입니다. |
| `source` | object | 아니요 | 소스 표시 정보(`name`, `description`, `monitor_type`, `icon`)이며, 첫 요청 시 함께 보내는 것을 권장합니다. |

## 응답

| HTTP | 본문 | 의미 |
|---|---|---|
| 200 | `{"status": "success"}` | 접수됨. 구독자에게 푸시됩니다 |
| 200 | `{"status": "stored", "pushed": false}` | `silent: true` — 저장만 되고 아무에게도 알리지 않음 |
| 202 | `{"status": "pending_review"}` | 새 `source_id`로 Tokenearly 심사 대기 중. 이벤트는 저장됨 |
| 400 | `{"code": "contract_error", "msg": "..."}` | 필드 누락 또는 형식 오류. 수정 후 보내고 그대로 재시도하지 마십시오 |
| 401 | `{"code": "unauthorized"}` | 토큰이 없거나 잘못됨 |
| 403 | `{"code": "source_disabled"}` | Tokenearly가 소스를 비활성화함 |
| 5xx / 타임아웃 | — | 지수 백오프로 재시도(1초, 2초, 4초 … 최대 15초). 두 SDK 모두 기본적으로 이렇게 동작합니다 |

## 멱등성

`event_id`는 멱등성 키입니다. Tokenearly는 `source_id` + `event_id` 기준으로 중복을 제거하므로, 재시도되거나 중복된 요청이 구독자에게 두 번 알림을 보내는 일은 없습니다. 안정적이고 의미 있는 ID(예: `btc-breakout-20260905-1030`)를 사용하고, 같은 종류의 이벤트라도 날짜가 다르면 다른 ID를 사용하십시오.

## 저장소 구조

```
signal-sdk/
├── docs/api.md          API reference (English)
├── docs/api.zh.md       接口说明（中文）
├── python/              tokenearly-signal — SignalClient, AsyncSignalClient, Event, tests, examples
└── typescript/          @tokenearly/signal — SignalClient, sendSignal, vitest tests, examples
```

## 라이선스

MIT © Tokenearly — [LICENSE](LICENSE)를 참고하십시오.

---

Tokenearly(토큰얼리)는 암호화폐 거래소의 토큰 상장 공지, 뉴스, X(트위터) 활동을 실시간으로 모니터링하고 알림을 보내는 플랫폼입니다. Binance, OKX, Bybit, Bitget, MEXC, Gate.io, HTX, KuCoin, Upbit, Bithumb 10개 거래소 공지(바이낸스와 Gate.io는 거래소 공식 WebSocket 상시 연결로 실시간 수신해 폴링 대기가 없고, 나머지 거래소는 고빈도 폴링)와 8개 뉴스 소스를 모니터링하고, 지정한 X 계정의 게시물·답글·리포스트·새 팔로우·프로필 사진과 소개 변경을 서브초(게시부터 감지까지 최단 50ms)로 추적해 키워드로 필터링한 뒤 Telegram, Bark, PushDeer, WeCom, DingTalk, Feishu, Webhook으로 한국어·영어·중국어 알림을 제공합니다.
