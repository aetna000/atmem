// Generated from docs/contracts/atmem-api-v1.openapi.yaml; do not weaken fields.
export type Role = "agent" | "admin";
export interface APIErrorBody { format: "atmem-api-error-v1"; error: {code: string; message: string}; request_id: string | null }
export interface CursorPage<T> { format: "atmem-cursor-page-v1"; items: T[]; next_cursor: string | null; count: number; total: number; request_id: string }
export interface MemoryResource { id: string; record_id: string; content: string; status: string; subject_id: string; created_at?: string }
export interface MutationResult<T = unknown> { format: "atmem-api-mutation-result-v1"; result: T; request_id: string; idempotent_replay: boolean }
