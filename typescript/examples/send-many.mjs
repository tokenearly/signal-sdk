// Backfill history with silent=true (stored, nobody notified), 4 requests in flight.
import { SignalClient } from "@tokenearly/signal";

const token = process.env.TOKENEARLY_SIGNAL_TOKEN;
if (!token) {
  console.error("set TOKENEARLY_SIGNAL_TOKEN first");
  process.exit(1);
}

const history = [
  { id: "2026-09-01-btc", en: "BTC closed above 65000", zh: "BTC 收于 65000 上方", ts: 1756742400 },
  { id: "2026-09-02-eth", en: "ETH closed above 3200", zh: "ETH 收于 3200 上方", ts: 1756828800 },
];

const client = new SignalClient(token);
const batch = await client.sendMany(
  history.map((item) => ({
    source_id: "example_signal",
    event_id: `backfill-${item.id}`,
    titles: { zh: item.zh, en: item.en },
    published_at: item.ts,
    silent: true,
  })),
  { concurrency: 4 },
);

console.log(`sent=${batch.sent} failed=${batch.failed}`);
for (const [index, error] of batch.errors) console.log(`  #${index}: ${error.message}`);
