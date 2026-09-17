# HTTP API and clients

AtMem exposes an additive `/v1` contract on the existing loopback control
server. Obtain the local session credential from `/api/session`, then send it
as `Authorization: Bearer …`. Agent and administrator principals receive
different operation sets; an agent cannot access audit, configuration,
migration, or destructive operations.

The baseline machine-readable contract is
[`docs/contracts/atmem-api-v1.openapi.yaml`](contracts/atmem-api-v1.openapi.yaml).
Python applications can use `atmem.client.AtMemClient`; TypeScript applications
use `@atmem/client`. Both expose timeouts and structured errors without hiding
review, authority, or deletion results.

Memory-creation retries require an idempotency key. Reusing it with different bytes is
a conflict. List cursors are opaque and scope-bound; a cursor from another
principal is invalid rather than revealing whether that scope exists.

The initial server is local and single-user. It is not safe to bind to a
non-loopback address. Authenticated TLS, tenant keys, quotas and production
operations are supplied only by the explicitly enabled production profile.

## Authentication and exact scope

`GET /api/session` returns a local `csrf_token`; the compatibility `/v1` API
accepts this token as a bearer credential. It is not an evidence-role grant.
Local dashboard accounts instead use their authenticated session; session-backed
POST operations also require that session's `X-CSRF-Token`. A temporary-password
account must change its password first. Never embed credentials in a public page.

For compatibility bearer calls, `X-AtMem-Subject`, `X-AtMem-Agent` and
`X-AtMem-Workspace` select scope. The local compatibility transport is not a
multi-tenant authentication service: do not expose it beyond loopback. Exact
evidence operations require an authenticated evidence principal; merely sending
`X-AtMem-Role: admin` does not grant plaintext evidence access.

## Read health

With a local credential held in your shell, replacing the port with your server's:

```bash
curl --fail http://127.0.0.1:8765/v1/health \
  -H "Authorization: Bearer $ATMEM_TOKEN"
```

Illustrative response; request IDs and mode depend on your installation:

```json
{"format":"atmem-api-health-v1","status":"healthy","mode":"shadow","limitations":[],"request_id":"example-only"}
```

## Create memory

```http
POST /v1/memories
Authorization: Bearer <local-credential>
Content-Type: application/json
X-AtMem-Subject: demo-user

{"message":"My preferred editor is Vim.","idempotency_key":"demo-editor-1","session_id":"demo"}
```

Required body fields are non-empty `message` and `idempotency_key`; `session_id`
is optional. This creates durable state. Reuse the key only for the exact same
operation and payload. A conflict or unknown mutation outcome requires inspection,
not blindly generating another key. Use synthetic data for experiments.

## Retrieve memory

`GET /v1/memories` accepts `query`, `limit` (bounded to 1–100), and an opaque
`cursor`. Its `atmem-cursor-page-v1` result contains `items`, `next_cursor`,
`count`, `total` and `request_id`.

`POST /v1/query` accepts `{"query":"preferred editor"}` and returns an
`atmem-api-query-result-v1` envelope with `result` and `request_id`. This is
governed retrieval, not proof of model-input delivery.

## Operation inventory

Paths below are complete, including `/v1`. This inventory describes the 2.3.3
loopback handler; the linked baseline OpenAPI covers a smaller subset. Consult
capabilities before use. Session/evidence authority is enforced by the service.

| Method | Path | Inputs / purpose |
| --- | --- | --- |
| GET | `/v1/health` | Authenticated service health |
| GET | `/v1/capabilities` | Available and allowed operations |
| GET, POST | `/v1/memories` | Scoped list / idempotent memory creation |
| POST | `/v1/query` | Body: `query` |
| GET | `/v1/reviews` | Scope-safe review status |
| GET | `/v1/audit` | Administrator; query `limit`, `cursor` |
| GET | `/v1/configuration` | Administrator configuration |
| GET | `/v1/features/{feature}` | Runtime feature capability |
| GET | `/v1/lifecycle` | Query: `record_id`, optional `evaluated_at` |
| POST | `/v1/lifecycle` | `record_id`, `to_state`, `base_generation`, `reason`; optional `evidence` |
| POST | `/v1/interchange/plan` | Scoped dry run: `workspace_id`, `agent_id`, `records` |
| POST | `/v1/media/revoke` | `artifact_id`; revokes controlled media derivatives |
| GET | `/v1/executions` | Execution summaries; optional `limit` |
| GET | `/v1/executions/{execution_id}` | One execution |
| GET | `/v1/evidence/status` | Evidence protection status |
| GET | `/v1/evidence/runs/{run_id}` | Role-filtered run evidence |
| GET | `/v1/evidence/search` | Query: `query`; evidence-role checks apply |
| POST | `/v1/evidence/reconstruct` | `run_id`; reconstruction, not a new external action |
| POST | `/v1/evidence/replay-manifest` | `run_id`; replay description, not tool execution |
| POST | `/v1/evidence/export/plaintext` | `run_id`, exact `confirmation`; Collector/Admin only |
| POST | `/v1/evidence/delete` | `run_id`, exact `confirmation`; destructive |
| POST | `/v1/evidence/settings/rotate` | Exact `confirmation`; key rotation |
| POST | `/v1/evidence/settings/lock` | Exact `confirmation`; lock evidence |
| POST | `/v1/evidence/settings/unlock` | Exact `confirmation`; unlock evidence |
| POST | `/v1/evidence/settings/capture-mode` | `capture_mode`; privileged setting |
| POST | `/v1/evidence/grants` | `principal_id`, `role`; optional `workspace_id`, `run_id` |
| POST | `/v1/evidence/revoke` | `principal_id`; revoke a grant |

Use the dashboard's confirmed evidence actions rather than guessing confirmation
strings for destructive or export operations. Plaintext export returns a base64
payload; decoding it creates a copy no longer protected by AtMem encryption.

## Error interpretation

Errors use `atmem-api-error-v1` with `error.code`, `error.message` and `request_id`.
401 means missing/invalid authentication, 403 means insufficient permission or
failed CSRF, 404 means unknown resource, and 409 can signal a mutation/precondition
conflict. Preserve the request ID when diagnosing; do not publish credentials or
exact private session content in bug reports.
