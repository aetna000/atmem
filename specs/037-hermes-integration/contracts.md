# Contract qualification — Hermes

Date: 2026-09-26. Scoped transport is implemented in source; installed packaging
and user-facing setup remain unqualified.

## Host boundary decision

Research pin `d0288be5b3330d2442e3907185b8e9d0958297bb` provides ordinary
memory-provider registration and per-turn recall. Its pre-request observer,
request middleware and execution middleware cannot serve as a fail-closed
authorization gate merely by raising an error. A callback error before downstream
execution is reported and skipped, then the original model call continues.

**Decision: proceed with `authorized-at-recall-v1` (user approved 2026-09-26).**
Per-model-call revocation enforcement is deferred, not a benchmark gate. This does not
mean Hermes cannot use AtMem memory. Authorization at fresh provider recall is a
narrower viable boundary, with already exposed content replayed by the host.
The selected profile authorizes fresh recall and withholds on failure. It must
not be called per-request revalidation or full-context governance. Capture coverage
is separately declared; memory support does not imply full model/tool capture.

Alternatives requiring a reviewed design decision:

1. A supported upstream fail-closed execution guard, including retries and
   alternate transports. Keep AtMem's plugin external; no permanent Hermes fork.
2. Explicitly scope the first release to fresh recall authorization, disclose
   retained-context replay, require conscious acceptance of incomplete capture,
   and forbid stronger revocation/Black Box claims.
3. A separately specified enforcing transport boundary. Do not silently add a
   model proxy or reroute user credentials to obtain a benchmark result.

No upstream issue/PR has been sent, and no user's Hermes config was changed.

## AtMem authentication audit and proposed binding

`atmem/control/web.py::_v1_principal` supports a local-session identity path,
an evidence-token path with server-stored scope, and a legacy shared bearer path
which accepts role/subject/agent/workspace headers. The last path is a trusted
local operator interface, not a suitable isolated Hermes agent credential.
`atmem/server/auth.py::KeyAuthority` is in-memory and is not by itself durable
profile credential provisioning. Do not reuse the dashboard CSRF bearer in a
Hermes provider.

New product binding must be created by an authenticated administrator and stored
with existing encrypted configuration/key custody. Minimal immutable fields:

| Field | Authority |
| --- | --- |
| binding ID and generation | AtMem issued; changes invalidate old credentials |
| adapter and qualified profile | `hermes` and exact tested capability profile |
| tenant, subject, agent, workspace | Administrator-approved server values |
| normalized Hermes profile identity | Pinned installation binding; no model override |
| allowed operations | Health, scoped recall and proposal submission only |
| state | ready, active, degraded, restoring, restored, revoked |
| credential digest/expiry | Server-side; secret never placed in prompt or log |
| previous provider/config digest | Conflict-aware restore, not a whole-file overwrite |

The service authenticates and looks up binding on every call. Request bodies may
carry bounded session/run/turn IDs but cannot redefine subject, workspace or
permissions. Derive namespaced IDs from the server binding plus host correlation
IDs. A locked store, stale generation or revoked token denies the call. Bindings
never confer evidence decryption/export/admin or other-profile access.

Proposed scoped operations, exact route schema still subject to gate resolution:
`status`, `recall`, `submit_observation`, `flush_status`. Administrative setup,
activation, restore and freeze are separate operations with separate authority.
Reject redirects and proxy environment inheritance for credentialed loopback
calls. Bound response bytes, payloads, timeouts and concurrency. Preserve secrets
as protected references; never serialize credential-bearing request headers.

## Checkpoint and write contracts

The product owns durable memory snapshots, not the benchmark. A freeze request
binds scope and a write watermark, drains all acknowledged work, rejects failures,
and records canonical/derived generation identities. Verify actual content after
restart. Evaluation grants cannot mutate memory through explicit tools, automatic
capture, extraction, graph updates or background jobs. Evidence and cost records
use a distinct append-only authorized sink. Returning an empty tool schema is not
authorization enforcement.

Observation IDs bind binding/session/turn/source position and payload digest.
Retrying an ID with different bytes is a conflict. Only a durable encrypted write
may be acknowledged as persisted; a queue acceptance is visibly pending. Memory
admission is a separate governed decision. Restore uses per-field compare-and-swap
against the installed generation and does not replace unrelated config changes.

## Implemented transport milestone

`POST /v1/hermes/status`, `/recall` and `/observe` accept only dedicated scoped
Hermes credentials. Scope headers and extra body fields cannot override their
server binding. General `/v1` APIs reject these credentials. Local administrator
service methods provision, activate/deactivate, rotate, revoke and list bindings;
user-facing provisioning still belongs to the installer milestone.

Authority records are in `hermes-bindings.enc.json` under the migration control
directory, encrypted with the existing identity-key custody (`EvidenceAccountStore`
key), not a new plaintext configuration or independent key. Evidence locking also
denies these operations. A separate, bounded-wait process lock and atomic writes
keep revocation independent of the slow execution database. Distinct Hermes
profiles require distinct memory subject/workspace scopes; ambiguous topology is
rejected. Rotation invalidates the old secret and requires reactivation.

Fresh recall is checked again after preparation. A completed revoke withholds a
still-preparing result, but cannot retract previously returned/in-flight HTTP
bytes. Preparation receipts are not proof that the model saw the context.
An observation accepted before revocation may finish; a changed binding during
its final check returns `observation_uncertain` (409), not a false claim that
nothing was written. Existing idempotent receipts retain the operation identity.

The beta deployment profile is a trusted, single-user local machine and trusted
Hermes CLI host. It is not hostile-local-user isolation: the scoped bearer uses
loopback HTTP. Installer credentials must be protected (0600 / qualified Windows
ACL equivalent), never returned to the model/browser/logs. The host attests human
source identity; ordinary AtMem admission policy still determines eligibility,
and is not claimed to require manual review under every policy. No model-facing
write tool is exposed by this profile.

The client uses literal `127.0.0.1`, no proxy or redirects, bounded bytes and
deadline checks between I/O operations with remaining-time socket timeouts.
This is not a hard real-time cancellation guarantee. The server bounds concurrent Hermes requests and socket reads;
client timeout does not cancel already accepted processing. Durable queue/drain
and checkpoint semantics are still separate unfinished work.

## AtFlows observation coordination

AtFlows Spec 006 `contracts/hermes-observation.md` owns the proposed independent
observer. Shared setup supplies non-secret profile/session mapping; no AtMem
credential goes to AtFlows. Session-level navigation uses the versioned canonical
session namespace with cross-repository test vectors. Numeric provider turn
counters are not native Hermes telemetry turn IDs; finer joins remain unavailable
until explicitly captured. This mapping is correlation, never authorization.

AtFlows T060–T064 add required receiver/storage/aggregation work for unknown
usage, redaction, retry deduplication, bounded export and installed qualification.
Planned release ordering is AtFlows 0.1.4b2 after redaction/product gates, verified
before AtMem 2.3.8b2 pins it. This is the coordinated prerelease checkpoint.
