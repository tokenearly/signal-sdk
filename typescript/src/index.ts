/**
 * @tokenearly/signal — TypeScript client for the Tokenearly Signal API.
 *
 * One event = one HTTP POST to https://api.tokenearly.com/receive_signal with the
 * `X-Signal-Token` header. Tokenearly stores the event, matches subscribers and delivers it
 * over Telegram, Bark, PushDeer, WeCom, DingTalk, Feishu and Webhook in Chinese, English and Korean.
 *
 * Zero runtime dependencies: uses the global `fetch` (Node 18+, browsers, Deno, Bun, workers).
 */

export const DEFAULT_ENDPOINT = "https://api.tokenearly.com/receive_signal";
export const SDK_VERSION = "0.1.0";

export type Lang = "zh" | "en" | "ko";
export type Level = "info" | "warning" | "critical";
export type LocalizedText = Partial<Record<Lang, string>>;

export const LANGS: readonly Lang[] = ["zh", "en", "ko"];
export const LEVELS: readonly Level[] = ["info", "warning", "critical"];

const SOURCE_ID_RE = /^[a-z0-9_]{2,64}$/;
const MAX_EVENT_ID_LEN = 128;
const MAX_TITLE_LEN = 200;
const MAX_CONTENT_LEN = 4000;
const MAX_LIST_LEN = 20;
const MS_THRESHOLD = 10_000_000_000;

/** Display information for a source (shown to subscribers). Send it with the first event. */
export interface SignalSource {
  name: string | LocalizedText;
  description?: string | LocalizedText;
  monitor_type?: string | LocalizedText;
  icon?: string;
}

/** One signal event. Field rules follow docs/api.md. */
export interface SignalEvent {
  /** ^[a-z0-9_]{2,64}$ — never changes */
  source_id: string;
  /** Idempotency key, <=128 chars, unique within source_id */
  event_id: string;
  /** Title per language (each <=200 chars). Either `titles` or `title` is required. */
  titles?: LocalizedText;
  title?: string;
  /** Body per language (each <=4000 chars, plain text) */
  contents?: LocalizedText;
  content?: string;
  /** Language of `title` / `content`; default zh on the server */
  lang?: Lang;
  /** Must start with http:// or https:// */
  url?: string;
  level?: Level;
  /** Up to 20 tickers; upper-cased */
  symbols?: string[];
  tags?: string[];
  /** Unix seconds; Date and millisecond values are converted */
  published_at?: number | Date;
  /** Stored as-is, never shown to subscribers */
  raw?: Record<string, unknown>;
  /** true = store only, notify nobody (backfill) */
  silent?: boolean;
  source?: SignalSource;
}

export type SignalStatus = "success" | "stored" | "pending_review";

export interface SignalResult {
  statusCode: number;
  status: SignalStatus | string;
  /** true when Tokenearly accepted the event for delivery */
  pushed: boolean;
  /** true when the source is still waiting for review (HTTP 202) */
  pending: boolean;
  /** true for silent events that were stored without notifying anyone */
  storedOnly: boolean;
  body: Record<string, unknown>;
}

export interface BatchResult {
  /** results[i] belongs to events[i]; undefined when it failed */
  results: Array<SignalResult | undefined>;
  errors: Map<number, SignalError>;
  sent: number;
  failed: number;
  ok: boolean;
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export interface SignalErrorOptions {
  statusCode?: number;
  code?: string;
  body?: unknown;
  cause?: unknown;
}

export class SignalError extends Error {
  readonly statusCode?: number;
  readonly code?: string;
  readonly body?: unknown;
  readonly cause?: unknown;
  constructor(message: string, options: SignalErrorOptions = {}) {
    super(options.statusCode !== undefined ? `[HTTP ${options.statusCode}] ${message}` : message);
    this.name = new.target.name;
    this.statusCode = options.statusCode;
    this.code = options.code;
    this.body = options.body;
    this.cause = options.cause;
  }
}
/** Event failed client-side validation; nothing was sent. */
export class ValidationError extends SignalError {}
/** HTTP 400 (contract_error / invalid_json). Fix the event; do not retry as-is. */
export class ContractError extends SignalError {}
/** HTTP 401: missing or wrong X-Signal-Token. */
export class AuthError extends SignalError {}
/** HTTP 403: the source_id has been disabled by Tokenearly. */
export class SourceDisabledError extends SignalError {}
/** HTTP 5xx / 429 still failing after all retries. */
export class ServerError extends SignalError {}
/** Network error / timeout still failing after all retries. */
export class TransportError extends SignalError {}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function checkUrl(value: unknown, field: string): string {
  if (typeof value !== "string" || !(value.startsWith("http://") || value.startsWith("https://"))) {
    throw new ValidationError(`${field} must start with http:// or https://`);
  }
  return value;
}

function checkText(value: unknown, field: string, maxLen: number): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new ValidationError(`${field} must be a non-empty string`);
  }
  if (value.length > maxLen) throw new ValidationError(`${field} is longer than ${maxLen} characters`);
  return value;
}

function checkLocalized(value: unknown, field: string, maxLen: number): LocalizedText {
  if (!isPlainObject(value) || Object.keys(value).length === 0) {
    throw new ValidationError(`${field} must be a non-empty object such as {zh: "...", en: "...", ko: "..."}`);
  }
  const out: LocalizedText = {};
  for (const [lang, text] of Object.entries(value)) {
    if (!(LANGS as readonly string[]).includes(lang)) {
      throw new ValidationError(`${field}: unsupported language '${lang}' (use zh, en or ko)`);
    }
    out[lang as Lang] = checkText(text, `${field}.${lang}`, maxLen);
  }
  return out;
}

function checkStringList(value: unknown, field: string, upper: boolean): string[] {
  if (!Array.isArray(value)) throw new ValidationError(`${field} must be an array of strings`);
  const items = value.map((item) => {
    if (typeof item !== "string" || item.trim() === "") {
      throw new ValidationError(`${field} must only contain non-empty strings`);
    }
    const trimmed = item.trim();
    return upper ? trimmed.toUpperCase() : trimmed;
  });
  if (items.length > MAX_LIST_LEN) throw new ValidationError(`${field} may contain at most ${MAX_LIST_LEN} entries`);
  return items;
}

function displayText(value: unknown, field: string): string | LocalizedText {
  return typeof value === "string" ? checkText(value, field, MAX_TITLE_LEN) : checkLocalized(value, field, MAX_TITLE_LEN);
}

/** Convert Date / millisecond / float timestamps to Unix seconds. */
export function normalizePublishedAt(value: number | Date): number {
  let ts: number;
  if (value instanceof Date) ts = value.getTime() / 1000;
  else if (typeof value === "number" && Number.isFinite(value)) ts = value;
  else throw new ValidationError("published_at must be a Unix timestamp or Date");
  if (ts < 0) throw new ValidationError("published_at must not be negative");
  if (ts > MS_THRESHOLD) ts = ts / 1000;
  return Math.floor(ts);
}

function sourceToPayload(source: SignalSource): Record<string, unknown> {
  if (!isPlainObject(source)) throw new ValidationError("source must be an object");
  const out: Record<string, unknown> = { name: displayText(source.name, "source.name") };
  if (source.description !== undefined) out.description = displayText(source.description, "source.description");
  if (source.monitor_type !== undefined) out.monitor_type = displayText(source.monitor_type, "source.monitor_type");
  if (source.icon !== undefined) out.icon = checkUrl(source.icon, "source.icon");
  return out;
}

const KNOWN_FIELDS = new Set([
  "source_id", "event_id", "titles", "title", "contents", "content", "lang", "url", "level",
  "symbols", "tags", "published_at", "raw", "silent", "source",
]);

/** Validate an event and return the JSON body to send (undefined fields omitted). Throws ValidationError. */
export function toPayload(event: SignalEvent): Record<string, unknown> {
  if (!isPlainObject(event)) throw new ValidationError("event must be an object");
  for (const key of Object.keys(event)) {
    if (!KNOWN_FIELDS.has(key)) throw new ValidationError(`unknown event field: ${key}`);
  }
  if (typeof event.source_id !== "string" || !SOURCE_ID_RE.test(event.source_id)) {
    throw new ValidationError("source_id must match ^[a-z0-9_]{2,64}$ (lowercase letters, digits, underscores)");
  }
  if (typeof event.event_id !== "string" || event.event_id.trim() === "") {
    throw new ValidationError("event_id must be a non-empty string");
  }
  if (event.event_id.length > MAX_EVENT_ID_LEN) {
    throw new ValidationError(`event_id is longer than ${MAX_EVENT_ID_LEN} characters`);
  }
  if (event.titles === undefined && event.title === undefined) {
    throw new ValidationError("either titles ({zh/en/ko}) or title is required");
  }

  const body: Record<string, unknown> = { source_id: event.source_id, event_id: event.event_id };
  if (event.titles !== undefined) body.titles = checkLocalized(event.titles, "titles", MAX_TITLE_LEN);
  if (event.title !== undefined) body.title = checkText(event.title, "title", MAX_TITLE_LEN);
  if (event.contents !== undefined) body.contents = checkLocalized(event.contents, "contents", MAX_CONTENT_LEN);
  if (event.content !== undefined) body.content = checkText(event.content, "content", MAX_CONTENT_LEN);
  if (event.lang !== undefined) {
    if (!(LANGS as readonly string[]).includes(event.lang)) throw new ValidationError("lang must be zh, en or ko");
    body.lang = event.lang;
  }
  if (event.url !== undefined) body.url = checkUrl(event.url, "url");
  if (event.level !== undefined) {
    if (!(LEVELS as readonly string[]).includes(event.level)) throw new ValidationError("level must be info, warning or critical");
    body.level = event.level;
  }
  if (event.symbols !== undefined) body.symbols = checkStringList(event.symbols, "symbols", true);
  if (event.tags !== undefined) body.tags = checkStringList(event.tags, "tags", false);
  if (event.published_at !== undefined) body.published_at = normalizePublishedAt(event.published_at);
  if (event.raw !== undefined) {
    if (!isPlainObject(event.raw)) throw new ValidationError("raw must be an object");
    body.raw = event.raw;
  }
  if (event.silent) body.silent = true;
  if (event.source !== undefined) body.source = sourceToPayload(event.source);
  return body;
}

/** Throws ValidationError if the event violates the API contract. */
export function validateEvent(event: SignalEvent): void {
  toPayload(event);
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export type FetchLike = (input: string, init: RequestInit) => Promise<Response>;

export interface SignalClientOptions {
  /** Defaults to https://api.tokenearly.com/receive_signal */
  endpoint?: string;
  /** Per-request timeout, default 10000 ms */
  timeoutMs?: number;
  /** Retries after the first attempt for network errors, timeouts, HTTP 5xx and 429. Default 3. */
  maxRetries?: number;
  /** Exponential backoff base, default 1000 ms (1s, 2s, 4s …) */
  backoffBaseMs?: number;
  /** Backoff cap, default 15000 ms */
  backoffMaxMs?: number;
  /** Custom fetch (tests, proxies, older runtimes) */
  fetch?: FetchLike;
  /** Custom sleep (tests) */
  sleep?: (ms: number) => Promise<void>;
}

const RETRYABLE_STATUS = new Set([408, 425, 429]);

function isRetryableStatus(status: number): boolean {
  return status >= 500 || RETRYABLE_STATUS.has(status);
}

async function parseBody(response: Response): Promise<Record<string, unknown>> {
  const text = await response.text();
  if (!text) return {};
  try {
    const data: unknown = JSON.parse(text);
    return isPlainObject(data) ? data : { raw: data };
  } catch {
    return { raw: text };
  }
}

function resultOrThrow(statusCode: number, body: Record<string, unknown>): SignalResult {
  if (statusCode === 200 || statusCode === 202) {
    const status = typeof body.status === "string" ? body.status : statusCode === 202 ? "pending_review" : "success";
    return {
      statusCode,
      status,
      pushed: status === "success",
      pending: status === "pending_review",
      storedOnly: status === "stored",
      body,
    };
  }
  const code = typeof body.code === "string" ? body.code : undefined;
  const msg = [body.msg, body.message, body.detail].find((v) => typeof v === "string") as string | undefined;
  if (statusCode === 400) {
    throw new ContractError(`${code ?? "contract_error"}: ${msg ?? "payload rejected"}`, { statusCode, code: code ?? "contract_error", body });
  }
  if (statusCode === 401) {
    throw new AuthError("missing or invalid X-Signal-Token", { statusCode, code: code ?? "unauthorized", body });
  }
  if (statusCode === 403) {
    throw new SourceDisabledError(`${code ?? "source_disabled"}: ${msg ?? "this source has been disabled"}`, { statusCode, code: code ?? "source_disabled", body });
  }
  if (statusCode >= 500 || statusCode === 429) {
    throw new ServerError(`Tokenearly returned HTTP ${statusCode} after retries`, { statusCode, code, body });
  }
  throw new SignalError(`unexpected HTTP ${statusCode}: ${msg ?? JSON.stringify(body)}`, { statusCode, code, body });
}

const defaultSleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

export class SignalClient {
  readonly endpoint: string;
  readonly timeoutMs: number;
  readonly maxRetries: number;
  readonly backoffBaseMs: number;
  readonly backoffMaxMs: number;
  private readonly headers: Record<string, string>;
  private readonly fetchFn: FetchLike;
  private readonly sleep: (ms: number) => Promise<void>;

  constructor(token: string, options: SignalClientOptions = {}) {
    if (typeof token !== "string" || token.trim() === "") {
      throw new ValidationError("token must be a non-empty string (ask Tokenearly for one)");
    }
    this.endpoint = options.endpoint ?? DEFAULT_ENDPOINT;
    this.timeoutMs = options.timeoutMs ?? 10_000;
    this.maxRetries = Math.max(0, options.maxRetries ?? 3);
    this.backoffBaseMs = options.backoffBaseMs ?? 1_000;
    this.backoffMaxMs = options.backoffMaxMs ?? 15_000;
    this.headers = {
      "Content-Type": "application/json",
      "X-Signal-Token": token.trim(),
      "User-Agent": `tokenearly-signal-js/${SDK_VERSION}`,
    };
    const f = options.fetch ?? (globalThis.fetch as FetchLike | undefined);
    if (!f) throw new SignalError("global fetch is not available; pass options.fetch");
    this.fetchFn = f;
    this.sleep = options.sleep ?? defaultSleep;
  }

  /** Validate and send one event. Resolves to a SignalResult or rejects with a SignalError. */
  async send(event: SignalEvent): Promise<SignalResult> {
    return this.post(toPayload(event));
  }

  /** Send events with limited concurrency. Failures are collected unless stopOnError is true. */
  async sendMany(
    events: SignalEvent[],
    options: { concurrency?: number; stopOnError?: boolean } = {},
  ): Promise<BatchResult> {
    const concurrency = Math.max(1, options.concurrency ?? 4);
    const results: Array<SignalResult | undefined> = new Array(events.length).fill(undefined);
    const errors = new Map<number, SignalError>();
    let next = 0;

    const worker = async (): Promise<void> => {
      while (next < events.length) {
        const index = next++;
        try {
          results[index] = await this.send(events[index]);
        } catch (err) {
          const error = err instanceof SignalError ? err : new SignalError(String(err), { cause: err });
          errors.set(index, error);
          if (options.stopOnError) throw error;
        }
      }
    };

    await Promise.all(Array.from({ length: Math.min(concurrency, events.length) }, worker));
    const failed = errors.size;
    return { results, errors, sent: events.length - failed, failed, ok: failed === 0 };
  }

  private backoff(attempt: number): number {
    return Math.min(this.backoffBaseMs * 2 ** attempt, this.backoffMaxMs);
  }

  private async post(payload: Record<string, unknown>): Promise<SignalResult> {
    const bodyText = JSON.stringify(payload);
    let attempt = 0;
    for (;;) {
      let response: Response;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeoutMs);
      try {
        response = await this.fetchFn(this.endpoint, {
          method: "POST",
          headers: this.headers,
          body: bodyText,
          signal: controller.signal,
        });
      } catch (err) {
        clearTimeout(timer);
        if (attempt < this.maxRetries) {
          await this.sleep(this.backoff(attempt));
          attempt += 1;
          continue;
        }
        throw new TransportError(`could not reach ${this.endpoint} after ${attempt + 1} attempts: ${String(err)}`, { cause: err });
      }
      clearTimeout(timer);

      if (isRetryableStatus(response.status) && attempt < this.maxRetries) {
        await this.sleep(this.backoff(attempt));
        attempt += 1;
        continue;
      }
      return resultOrThrow(response.status, await parseBody(response));
    }
  }
}

/** One-shot helper: `await sendSignal(token, event)`. */
export async function sendSignal(token: string, event: SignalEvent, options: SignalClientOptions = {}): Promise<SignalResult> {
  return new SignalClient(token, options).send(event);
}
