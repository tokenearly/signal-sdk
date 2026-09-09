import { describe, expect, it } from "vitest";

import {
  AuthError,
  ContractError,
  DEFAULT_ENDPOINT,
  ServerError,
  SignalClient,
  SourceDisabledError,
  TransportError,
  ValidationError,
  normalizePublishedAt,
  sendSignal,
  toPayload,
  type SignalEvent,
} from "../src/index";

const EVENT: SignalEvent = { source_id: "my_signal", event_id: "evt-1", title: "Test signal", lang: "en" };

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

function fakeFetch(script: Array<Response | Error>) {
  const calls: Array<{ url: string; init: RequestInit }> = [];
  const fn = async (url: string, init: RequestInit): Promise<Response> => {
    calls.push({ url, init });
    const next = script.shift();
    if (!next) throw new Error("unexpected extra request");
    if (next instanceof Error) throw next;
    return next;
  };
  return { fn, calls };
}

function makeClient(script: Array<Response | Error>, sleeps: number[], extra: Record<string, unknown> = {}) {
  const { fn, calls } = fakeFetch(script);
  const client = new SignalClient("tok-123", {
    fetch: fn,
    sleep: async (ms) => {
      sleeps.push(ms);
    },
    ...extra,
  });
  return { client, calls };
}

describe("toPayload", () => {
  it("builds the minimal payload and omits undefined fields", () => {
    expect(toPayload(EVENT)).toEqual({ source_id: "my_signal", event_id: "evt-1", title: "Test signal", lang: "en" });
  });

  it("upper-cases symbols, converts published_at and keeps silent only when true", () => {
    const body = toPayload({
      source_id: "my_signal",
      event_id: "e",
      titles: { zh: "你好", en: "Hello", ko: "안녕" },
      symbols: ["btc", " eth "],
      published_at: new Date("2025-09-05T10:30:00Z"),
      silent: true,
      source: { name: { en: "My Signal" }, icon: "https://example.com/favicon.ico" },
    });
    expect(body.symbols).toEqual(["BTC", "ETH"]);
    expect(body.published_at).toBe(1757068200);
    expect(body.silent).toBe(true);
    expect(body.source).toEqual({ name: { en: "My Signal" }, icon: "https://example.com/favicon.ico" });
    expect(toPayload({ ...EVENT, silent: false })).not.toHaveProperty("silent");
  });

  it("rejects contract violations", () => {
    expect(() => toPayload({ ...EVENT, source_id: "Bad-ID" })).toThrow(ValidationError);
    expect(() => toPayload({ ...EVENT, event_id: "x".repeat(129) })).toThrow(ValidationError);
    expect(() => toPayload({ source_id: "ok", event_id: "e" })).toThrow(/titles/);
    expect(() => toPayload({ ...EVENT, titles: { fr: "Bonjour" } as never })).toThrow(/unsupported language/);
    expect(() => toPayload({ ...EVENT, title: "x".repeat(201) })).toThrow(ValidationError);
    expect(() => toPayload({ ...EVENT, content: "x".repeat(4001) })).toThrow(ValidationError);
    expect(() => toPayload({ ...EVENT, url: "ftp://x" })).toThrow(ValidationError);
    expect(() => toPayload({ ...EVENT, level: "urgent" as never })).toThrow(ValidationError);
    expect(() => toPayload({ ...EVENT, symbols: new Array(21).fill("BTC") })).toThrow(ValidationError);
    expect(() => toPayload({ ...EVENT, bogus: 1 } as never)).toThrow(/unknown event field/);
  });

  it("normalizes millisecond timestamps", () => {
    expect(normalizePublishedAt(1757068200123)).toBe(1757068200);
    expect(normalizePublishedAt(1757068200.9)).toBe(1757068200);
    expect(() => normalizePublishedAt(-1)).toThrow(ValidationError);
  });
});

describe("SignalClient", () => {
  it("sends the expected request and parses success", async () => {
    const sleeps: number[] = [];
    const { client, calls } = makeClient([json(200, { status: "success" })], sleeps);
    const result = await client.send(EVENT);
    expect(result.pushed).toBe(true);
    expect(result.pending).toBe(false);
    expect(result.statusCode).toBe(200);
    expect(calls[0].url).toBe(DEFAULT_ENDPOINT);
    const headers = calls[0].init.headers as Record<string, string>;
    expect(headers["X-Signal-Token"]).toBe("tok-123");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(calls[0].init.body as string)).toEqual(toPayload(EVENT));
    expect(sleeps).toEqual([]);
  });

  it("supports a custom endpoint", async () => {
    const { client, calls } = makeClient([json(200, { status: "success" })], [], { endpoint: "https://signals.example.com/receive_signal" });
    await client.send(EVENT);
    expect(calls[0].url).toBe("https://signals.example.com/receive_signal");
  });

  it("reports pending_review and stored", async () => {
    const { client } = makeClient([json(202, { status: "pending_review" }), json(200, { status: "stored", pushed: false })], []);
    const pending = await client.send(EVENT);
    expect(pending.pending).toBe(true);
    expect(pending.statusCode).toBe(202);
    const stored = await client.send({ ...EVENT, silent: true });
    expect(stored.storedOnly).toBe(true);
    expect(stored.pushed).toBe(false);
  });

  it("never sends invalid events", async () => {
    const { client, calls } = makeClient([], []);
    await expect(client.send({ ...EVENT, source_id: "Bad ID" })).rejects.toBeInstanceOf(ValidationError);
    expect(calls).toHaveLength(0);
  });

  it("does not retry 400 / 401 / 403", async () => {
    const sleeps: number[] = [];
    const { client, calls } = makeClient(
      [json(400, { code: "contract_error", msg: "titles missing" }), json(401, { code: "unauthorized" }), json(403, { code: "source_disabled" })],
      sleeps,
    );
    await expect(client.send(EVENT)).rejects.toMatchObject({ name: "ContractError", statusCode: 400, code: "contract_error" });
    await expect(client.send(EVENT)).rejects.toBeInstanceOf(AuthError);
    await expect(client.send(EVENT)).rejects.toBeInstanceOf(SourceDisabledError);
    expect(calls).toHaveLength(3);
    expect(sleeps).toEqual([]);
  });

  it("retries 5xx with exponential backoff then succeeds", async () => {
    const sleeps: number[] = [];
    const { client, calls } = makeClient([json(503, {}), new Response("oops", { status: 500 }), json(200, { status: "success" })], sleeps);
    const result = await client.send(EVENT);
    expect(result.pushed).toBe(true);
    expect(calls).toHaveLength(3);
    expect(sleeps).toEqual([1000, 2000]);
  });

  it("gives up after maxRetries and caps the backoff", async () => {
    const sleeps: number[] = [];
    const script = Array.from({ length: 7 }, () => json(502, {}));
    const { client, calls } = makeClient(script, sleeps, { maxRetries: 6 });
    await expect(client.send(EVENT)).rejects.toBeInstanceOf(ServerError);
    expect(calls).toHaveLength(7);
    expect(sleeps).toEqual([1000, 2000, 4000, 8000, 15000, 15000]);
  });

  it("retries network errors and finally throws TransportError", async () => {
    const sleeps: number[] = [];
    const { client } = makeClient([new Error("ECONNRESET"), json(200, { status: "success" })], sleeps);
    expect((await client.send(EVENT)).pushed).toBe(true);
    expect(sleeps).toEqual([1000]);

    const failing = makeClient([new Error("down"), new Error("down")], [], { maxRetries: 1 });
    await expect(failing.client.send(EVENT)).rejects.toBeInstanceOf(TransportError);
  });

  it("sendMany collects errors and preserves order", async () => {
    const { client } = makeClient(
      [json(200, { status: "success" }), json(400, { code: "contract_error" }), json(202, { status: "pending_review" })],
      [],
      { maxRetries: 0 },
    );
    const events: SignalEvent[] = [0, 1, 2].map((i) => ({ source_id: "my_signal", event_id: `evt-${i}`, title: "t" }));
    const batch = await client.sendMany(events, { concurrency: 1 });
    expect(batch.sent).toBe(2);
    expect(batch.failed).toBe(1);
    expect(batch.ok).toBe(false);
    expect(batch.results[1]).toBeUndefined();
    expect(batch.errors.get(1)).toBeInstanceOf(ContractError);
    expect(batch.results[2]?.pending).toBe(true);
  });

  it("sendMany stopOnError rejects", async () => {
    const { client } = makeClient([json(400, { code: "contract_error" })], [], { maxRetries: 0 });
    await expect(client.sendMany([EVENT, EVENT], { concurrency: 1, stopOnError: true })).rejects.toBeInstanceOf(ContractError);
  });

  it("rejects an empty token", () => {
    expect(() => new SignalClient("  ")).toThrow(ValidationError);
  });

  it("sendSignal helper works", async () => {
    const { fn } = fakeFetch([json(200, { status: "success" })]);
    const result = await sendSignal("tok", EVENT, { fetch: fn });
    expect(result.pushed).toBe(true);
  });
});
