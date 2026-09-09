// Send one signal with @tokenearly/signal (Node 18+).
//
//   npm install @tokenearly/signal
//   TOKENEARLY_SIGNAL_TOKEN=... node basic.mjs
//
// Inside this repository, run `npm run build` first and import from "../dist/index.js".
import { SignalClient, SignalError } from "@tokenearly/signal";

const token = process.env.TOKENEARLY_SIGNAL_TOKEN;
if (!token) {
  console.error("set TOKENEARLY_SIGNAL_TOKEN first");
  process.exit(1);
}

const client = new SignalClient(token); // endpoint defaults to https://api.tokenearly.com/receive_signal

try {
  const result = await client.send({
    source_id: "example_signal",
    event_id: `example-${Date.now()}`,
    titles: { zh: "🚀 BTC 突破 70000", en: "🚀 BTC breaks 70000", ko: "🚀 BTC 70000 돌파" },
    contents: { zh: "现价: $70120\n24h: +4.2%", en: "Price: $70120\n24h: +4.2%", ko: "현재가: $70120\n24h: +4.2%" },
    url: "https://example.com/btc",
    level: "warning",
    symbols: ["BTC"],
    published_at: new Date(),
    source: {
      name: { zh: "示例信号", en: "Example Signal", ko: "예시 시그널" },
      monitor_type: { zh: "异动提醒", en: "Movement alerts", ko: "변동 알림" },
    },
  });
  console.log(`HTTP ${result.statusCode} status=${result.status} pushed=${result.pushed} pending=${result.pending}`);
  if (result.pending) console.log("First event from this source_id: ask Tokenearly to approve the source.");
} catch (err) {
  if (err instanceof SignalError) {
    console.error(`failed: ${err.message} (code=${err.code ?? "-"})`);
  } else {
    throw err;
  }
}
