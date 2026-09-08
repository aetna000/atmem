import type { APIErrorBody, CursorPage, MemoryResource, MutationResult, Role } from "./types.js";
export type { APIErrorBody, CursorPage, MemoryResource, MutationResult, Role } from "./types.js";

export class AtMemAPIError extends Error {
  constructor(public readonly status: number, public readonly body: APIErrorBody) { super(body.error.message); }
}

export interface AtMemClientOptions { endpoint: string; token: string; role?: Role; subjectId?: string; agentId?: string; timeoutMs?: number; fetch?: typeof globalThis.fetch }

export class AtMemClient {
  private readonly fetcher: typeof globalThis.fetch;
  constructor(private readonly options: AtMemClientOptions) {
    this.fetcher = options.fetch ?? globalThis.fetch;
    if (!this.fetcher) throw new Error("fetch is required");
  }
  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.options.timeoutMs ?? 5000);
    try {
      const response = await this.fetcher(`${this.options.endpoint.replace(/\/$/, "")}/v1/${path}`, {method, signal: controller.signal, headers: {Authorization: `Bearer ${this.options.token}`, "Content-Type": "application/json", "X-AtMem-Role": this.options.role ?? "agent", "X-AtMem-Subject": this.options.subjectId ?? "local-user", "X-AtMem-Agent": this.options.agentId ?? "main"}, body: body === undefined ? undefined : JSON.stringify(body)});
      const value = await response.json() as T | APIErrorBody;
      if (!response.ok) throw new AtMemAPIError(response.status, value as APIErrorBody);
      return value as T;
    } finally { clearTimeout(timer); }
  }
  health(): Promise<Record<string, unknown>> { return this.request("GET", "health"); }
  capabilities(): Promise<Record<string, unknown>> { return this.request("GET", "capabilities"); }
  memories(options: {query?: string; limit?: number; cursor?: string} = {}): Promise<CursorPage<MemoryResource>> {
    const query = new URLSearchParams();
    if (options.query) query.set("query", options.query);
    if (options.limit) query.set("limit", String(options.limit));
    if (options.cursor) query.set("cursor", options.cursor);
    return this.request("GET", `memories?${query}`);
  }
  remember(message: string, idempotencyKey: string, sessionId?: string): Promise<MutationResult> { return this.request("POST", "memories", {message, idempotency_key: idempotencyKey, session_id: sessionId}); }
  query(query: string): Promise<Record<string, unknown>> { return this.request("POST", "query", {query}); }
}
