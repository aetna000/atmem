# Feature Specification: Durable Execution Evidence and Coverage

**Product-wide requirements**: [Agent neutrality, standalone full-fidelity evidence and encrypted privileged plaintext](../product-requirements.md) (PR-001–PR-008). Applies to this feature's advertised capabilities; implementation status below remains authoritative.

**Feature directory**: `specs/020-durable-execution-evidence`
**Created**: 2026-09-09
**Status**: Earlier metadata-oriented OpenClaw capture is implemented, but the 2026-09-13 standalone full-fidelity M0 profile is reopened and not release-ready until T042–T053 pass
**Input**: Unified memory, governance and investigation product direction; [roadmap](../product-roadmap.md).

## Overview

An operator opens a 40-minute job containing retries and child agents and sees one ordered execution with explicit gaps, even after a process restart.

Product moment: **During execution**. This feature extends the existing product; the shared identity, application service, canonical authority and invariant owners remain as declared in [integration ownership](../integration-ownership.md).

## User scenarios and acceptance

### US1 — Complete the primary workflow (P1)

An operator opens a 40-minute job containing retries and child agents and sees one ordered execution with explicit gaps, even after a process restart.

**Independent test**: Execute the scoped synthetic primary journey through the public service and a supported host. Assert FR-001–FR-010 and SC-001–SC-004; record unavailable capabilities rather than infer them.

**Acceptance**: Given authenticated scope and configured capabilities, when the primary workflow runs, then its result identifies the exact decision/event evidence and preserves the claimed boundary.

### US2 — Understand a failure without overstating evidence (P1)

An operator receives a useful deterministic result when optional intelligence or a provider/host boundary is unavailable.

**Acceptance**: Given a denied, missing, stale, replayed or unavailable input, when the workflow executes, then its failure/coverage reason is explicit, no authority widens and no external outcome is invented.

### US3 — Adopt incrementally and retain history (P2)

An existing user enables this capability explicitly and retains native memory, trusted delegation, old receipts and host state.

**Acceptance**: Given pre-feature persisted state, when upgrade and rollback/recovery are exercised, then old evidence remains inspectable, no historical relationship is fabricated and disabled capabilities do not affect execution.

### US4 — Investigate independently after the agent is gone (P1)

An authorized user restores an AtMem evidence-store copy on a fresh process and
recovers the exact ordered multimodal run without the original agent, logs,
workspace, provider, model or network.

**Independent test**: Execute FR-024–FR-031 and SC-011–SC-015 using the golden
multimodal oracle, destructive dependency removal, exact artifact comparison,
deterministic inert replay and deliberately exhausted local capacity.

**Acceptance**: Full capture is the default; every acknowledged byte is present,
the readable story agrees with exact evidence, capacity failure is explicit,
and metadata/off/legacy runs are visibly non-reconstructable.

## Functional requirements

- **FR-001**: Extend Spec 007 ExecutionIdentity with a stable authenticated job/execution ID, parent execution, attempt and retry-of references; retain distinct session, run, turn, tool-call and optional task IDs. Never infer relationships from similar names, prompts or timestamps.
- **FR-002**: Record append-only typed events for model/context/tool boundaries, lifecycle, explicit progress, waiting, retry and child execution. Event identity binds producer instance/epoch and sequence; duplicate same-payload events replay idempotently, conflicting duplicates remain visible integrity findings.
- **FR-003**: Persist a bounded local capture spool and acknowledgment checkpoints; acknowledge only durable acceptance. Restart resends unacknowledged events without duplicate evidence. Disk-full, dropped events, producer reset and expired retention create explicit coverage gaps.
- **FR-004**: Retain event time and ingest time; use producer sequence and explicit dependencies for ordering, and label incomparable cross-producer ordering and clock skew. Render elapsed time without claiming a universal exact causal order.
- **FR-005**: Publish per-adapter/version/configuration coverage for supported, observed and enforced boundaries, including omitted hooks. Static availability or successful retrieval cannot prove model placement, tool completion or blocking. Use the public Spec 011 conformance manifest format for published results, retaining actual runtime coverage and issuer assurance separately.
- **FR-006**: Classify running, waiting, succeeded, failed, cancelled and incomplete executions from observed events; silence becomes missing heartbeat or suspected stall under a declared threshold, never automatic proof of failure.
- **FR-007**: Build bounded scope-filtered execution projections across attempts/children, with cycle rejection, orphan references, cancellation, late completion and partial children explicit. Late evidence produces revised projections with provenance, not rewritten events.
- **FR-008**: Keep investigation-only mode usable without native memory, embeddings, AtBot, task activation or context changes. Link optional context packages and task revisions when supplied by authenticated hosts.
- **FR-009**: Expose execution/timeline/coverage resources through the existing application service; authorize joins, counts, cursors and export as well as row content. Old flights remain inspectable and unlinked unless actual provenance establishes a job relationship.
- **FR-010**: Use allocated persisted migrations and verified retention/deletion for spool, full-fidelity evidence/artifacts and projections. Preserve existing verified-flight semantics while migrating new captures to the standalone evidence profile. Chain-of-thought that was never exposed by a model is not inventable evidence; all actual boundary content is retained by default under FR-024–FR-031.

## Key entities

- **JobExecution**: Authenticated job ID, owning scope, optional parent, associated run/turn references, observed start/end and coverage-aware status.
- **ExecutionAttempt**: Attempt ID, execution ID, explicit retry-of reference, host attempt number and observed lifecycle.
- **StepLink**: Scoped source/target event or step IDs, dependency/child/input relationship, declaring producer and evidence reference.
- **EvidenceEvent**: Producer instance/epoch/sequence, event ID/type, execution/attempt/turn/tool references, event and ingest times, exact evidence-envelope reference, supporting integrity digest and assurance.
- **EvidenceEnvelope**: Versioned immutable boundary record containing ordered content parts, actor/scope, execution identity, timing, provenance, completeness and artifact references.
- **ContentPart**: Positioned text, link/fetched resource, file, image, audio or video content with its exact bytes or transactionally bound artifact, MIME type, source and timing.
- **Artifact**: Original immutable bytes owned by the AtMem evidence store, with integrity metadata, lifecycle state and audited access/export/deletion history.
- **ReplayManifest**: Deterministic inert reconstruction of captured inputs, dependencies, tool contracts and missing prerequisites; it never authorizes execution.
- **CoverageManifest**: Adapter/host/version/configuration identity, supported/observed/enforced boundary sets, gaps, last producer sequence and assessment time.
- **CaptureCheckpoint**: Durable spool position, acknowledged producer sequence, retained range, replay state and loss/backpressure reason.

## Success criteria

- **SC-001**: A virtual-clock 40-minute fixture with two children, recovered retry, cancellation and an orphan event reconstructs all supplied relationships and labels every planted gap.
- **SC-002**: Crash/restart, concurrent replay and out-of-order tests lose zero acknowledged events, create zero duplicate logical events and expose conflicting duplicates and disk exhaustion.
- **SC-003**: On 100,000 synthetic events, first-page (100 events) execution lookup p95 <= 200 ms on a documented local host; record write overhead and storage size separately.
- **SC-004**: Real supported host conformance plus an MCP-only fixture proves coverage differences; investigation-only operation causes zero canonical imports, context injections or inferred task bindings.

## Failure and edge cases

Missing identity, inaccessible parent/reference, duplicate or conflicting delivery, timeout after external dispatch, stale generation, late evidence, deleted source, unavailable provider/model, process restart, cancellation, scope changes, artifact corruption, quota exhaustion and retention races must have explicit bounded outcomes. Authorization covers joins, explanations, totals and exports. A source reference or signature does not establish semantic truth. Where a boundary is unsupported, report it rather than emulate a stronger guarantee; storage pressure never silently changes the capture profile.

## Dependencies and ownership

For M0, 007 T110 delivers the non-task ExecutionIdentity subset of T088; use existing control-store migrations and baseline adapters/services/invariants. T089/T092 task-link storage and propagation are required only for task-enabled expansion. Context capture accepts optional 019 references; investigation-only capture is independent of 019, 022 and 025.

The dependency list distinguishes existing baseline modules from new contract milestones. Feature-specific assertions feed Spec 018; Spec 018's existing registry is a baseline prerequisite, not a cycle requiring future consumer code before its contracts exist.

## Compatibility, privacy and migration

Keep Python 3.10–3.13, optional provider/model/framework imports, local operation, explicit activation and egress, unchanged host-owned state and distinct canonical memory/task/evidence authorities. Closed wire schemas get new versions when needed; additive fields require negotiation. Allocate migrations through existing registries, retain legacy projections, test supported published floors, and never fabricate historical links or content from hashes. Full-fidelity boundary content and multimodal artifacts are retained by default; credentials use protected references/reversible protection and all evidence access remains scoped and audited.

## Out of scope

Owning host scheduling/checkpoints, guaranteeing capture of unreported events, treating heartbeat absence as proof of task failure, or automated restart.

## Invariant Attestation

Touches INV-004, INV-005, INV-006, INV-008, INV-010, INV-011 through `spec020.scope`, `spec020.evidence`, `spec020.compatibility` and `spec020.failure`. These are planned assertion identifiers, not claims of executing tests. They become proven only when boundary tests and installed-artifact evidence exist.

## M0 release profile

[The M0 release slice](../m0-investigation-preview.md) defines independent OpenClaw investigation-only delivery and exact prerequisite tasks. It overrides full-feature sequencing for that profile only: shared non-task identity and the evidence-specific Spec 022 destinations can ship before task links, providers, other hosts or the broader application shell. Completing the slice does not complete broader requirements. Usability claims follow [the declared protocol](../usability-protocol.md).

## Product-wide requirements — agent neutrality and clear evidence

**Required, not yet implemented:** [Product requirements](../product-requirements.md) PR-001–PR-002 and PR-005–PR-007. This amendment applies to this feature's public and UI boundaries; host-specific integrations cannot redefine core identity or authority.

- **FR-011**: Preserve authenticated framework-qualified agent identities across concurrent and explicitly linked parent/child work without inheriting access. Publish event time, receive time, clock/source provenance, elapsed duration where calculable and last actual coverage verification. Unknown/skewed clocks and late events remain explicit; display refresh cannot change event or verification time.
- **SC-005**: Concurrent agents with colliding display names retain distinct scope and evidence; time fixtures cover late arrival, absent timestamps, clock skew, timezone/daylight-saving changes and refresh without re-verification, with zero invented ordering or timestamp claims.

This work extends existing authority and preserves legacy scopes. Private/shared memory and multi-framework claims require their own evidence; M0 delivers only its applicable capture/feedback subset. See the central ownership and release matrix.


## Tool error diagnostics amendment — 2026-09-09

A reported `web_fetch` failure retained only `tool_error` and the digest of JSON
`null`, discarding the host's separate error field. This amendment applies to
the existing Black Box recorder; it does not mark the wider execution roadmap
implemented. Existing signed events must remain unchanged.

- **FR-012**: Failed tool completions MUST preserve an available host error as a
  redacted, single-line diagnostic of at most 512 characters (`error_reason`).
  Strip URLs, recognizable credentials, email addresses, paths, quoted values,
  control characters and subsequent stack/output lines before retention. This is
  best-effort diagnostic redaction, not a guarantee against arbitrary sensitive
  prose; full tool outputs and stacks remain excluded. Store a separate
  `error_sha256` when a distinct error field exists. Apply this to typed hooks
  and correlated terminal tool events, without weakening correlation or deduplication.
- **FR-013**: Reports and the dashboard MUST surface the captured reason. If it
  is unavailable, including for legacy events, state “No error reason was
  captured.” Do not infer a cause from the tool name, outcome, or digest. Typed
  completions MUST distinguish absent results with `result_present`; the digest
  of `null` alone does not establish why a call failed.
- **SC-006**: Regression checks cover a typed error without a result, terminal
  event error text, absent diagnostics, redaction/truncation, preserved successful
  outcomes, conflicting observations, persisted report propagation, and dashboard
  reason/fallback rendering. Historical event hashes remain unchanged.

- **FR-014**: Missing-completion and tool-error displays MUST explain the
  evidence boundary and give an operator next step in both the diagnosis list and
  expanded timeline event. For missing completion, direct users to correlate host
  logs by run/call ID and establish whether execution occurred before retrying.
  Recurring gaps should point to `atmem control verify`, bridge upgrade after an
  AtMem upgrade, and host restart. Never imply an upgrade reconstructs historical
  evidence or a missing completion proves tool failure.

- **FR-015**: Run-list projections expose observed lifecycle/response coverage and
  bounded tool-issue counts independently of the evidence verdict. Classify only
  the known OpenClaw skill-review run/session convention as background display
  metadata. A scoped revision endpoint returns the latest event sequence/hash and
  acknowledgement count for UI refresh, without claiming chain verification.

### Progress-card reporting equivalence — 2026-09-09

- **FR-016**: Preserve each raw result digest while adding the optional
  `openclaw-progress-card-v1` comparison profile at capture. Accept only the exact
  shipped progress-card `{content, details}` and native `input_text[]` formats:
  bounded text, matching summary/JSON/details, valid revision and step counts,
  and no additional fields. Compare only two successful completion observations
  with distinct recognized shapes, matching nonempty request digests, canonical
  `progress_card` identity and equal comparison digests within the existing
  scoped flight/call grouping. Other tools and unknown/contradictory shapes,
  payloads or outcomes remain conflicts. No default result-text retention.
- **FR-017**: Historical hash-only conflicts MUST NOT be silently declared
  equivalent or rewritten. When all completion observations report success,
  present an amber result-record discrepancy and explain that reporting formats
  may differ; do not claim a tool failure or instruct a retry merely to clear it.
- **SC-007**: Reproduce the observed pair of raw incident hashes from independent
  host/transcript evidence; validate capture through real bridge hooks and RPC
  persistence, plus negative cases for changed results, extra fields, wrong tool,
  inconsistent details, contradictory outcome, third observation and absent
  comparison metadata. Synthetic regression and local incident inspection do not
  establish fresh live-host conformance.

### Selective automatic context and precise diagnostics — 2026-09-09

- **FR-018**: The direct OpenClaw bridge MUST require calibrated direct support
  for the original query before automatic recall injection by default. Relative
  retrieval rank alone is not proof of relevance. Persona injection is opt-in;
  explicitly enabled persona IDs are excluded from recall to prevent duplication.
  Existing explicit search and optional legacy rank-based API behavior remain
  available. Record component counts and selection profile alongside context
  digests; no-result decisions must not claim memory was delivered.
- **FR-019**: Recognize the inspected OpenClaw API security wrapper and retain
  only its bounded `Web fetch failed (HTTP status)` diagnostic. Unknown wrapper
  content is not an error reason. Never retain page text merely to extract a
  diagnostic. Historical security-notice-only reasons remain unavailable rather
  than becoming an invented HTTP status.
- **FR-020**: Evidence timestamps remain ISO 8601 UTC with at least millisecond
  precision. Preserve existing microseconds and signed timestamp bytes. Sequence
  remains authoritative when timestamps coincide. UI timestamps show browser-local
  date/time, seconds, three fractional digits and timezone; expose the original
  UTC value in event details. Missing time must not become the Unix epoch.
- **SC-008**: A weak-match shopping query that previously selected procedural
  list advice injects none under the direct-support profile; a supported personal
  query still recalls memory; opt-in persona/recall have no duplicate IDs. Verify
  bridge-to-MCP behavior, selection audit and legacy explicit recall.
- **SC-009**: Wrapped HTTP 403 fixtures expose the status without page text;
  unknown wrappers have no fabricated diagnostic. UTC precision, timezone/DST
  conversion and mobile timestamp layout pass deterministic checks. Historical
  signed evidence is unchanged.

### Release-candidate correctness hardening — 2026-09-12

- **FR-021**: Producer-sequenced delivery MUST include an event ID and an ISO
  8601 UTC event time with at least millisecond precision. Replay identity MUST
  exclude server-generated ingest time. Invalid timestamps and incomplete
  producer or parent/retry identity groups fail before evidence persistence.
  Legacy unsequenced observations may continue to use ingest time as their
  recorded time.
- **FR-022**: Delivery receipts MUST distinguish accepted/replayed evidence from
  a durably recorded conflict classification. A producer MAY remove either
  terminal decision from its spool, but a conflicting body MUST NOT be called
  accepted evidence. The conflict ledger retains its identity and both hashes.
- **FR-023**: The public recording schema MUST declare every durable delivery,
  timing and execution-identity field consumed by ingestion. Execution paging
  MUST select either the modern identity or the legacy compatibility route once,
  without changing route at a page boundary. Dashboard delivery counts MUST use
  bounded aggregate queries.
- **SC-010**: Boundary tests cover timestamp omission and malformation,
  idempotent replay, identity dependency rejection, conflict receipt semantics,
  MCP schema parity, receive-time/skew display, modern-versus-legacy pagination,
  indexed gap counts and aggregate delivery counts.

## Standalone full-fidelity multimodal evidence amendment — 2026-09-13

This amendment governs every conflict with FR-010 and FR-012–FR-019. It
supersedes only their content-minimizing, redaction-only, no-result-retention,
and “consult host logs” fallback behavior; their correlation, integrity,
comparison, timing, status and uncertainty rules remain valid. Historical
events are not rewritten.

- **FR-024**: Define one versioned canonical `EvidenceEnvelope` whose ordered
  parts cover user input, active memory state and exact records selected,
  delivered context, governance decision inputs/rules/outputs, system and model
  input/output, tool request/completion and outcome evidence. Each boundary MUST
  preserve text, link, fetched resource, file, image, audio and video parts with
  original bytes, MIME type, byte length, timestamp, source and position.
- **FR-025**: Full-fidelity capture MUST be the default. Every supported adapter
  publishes actual boundary coverage and persists each acknowledged envelope
  before the disposable producer state may be lost. Explicit capture-off or
  metadata-only choices are audited and mark affected runs `not_reconstructable`;
  they cannot satisfy the Agent Black Box capability.
- **FR-026**: Persist envelope metadata and original artifact bytes in a
  transactionally linked Spec 028 encrypted AtMem evidence store with crash recovery, backup,
  restore, export and verified deletion. Content-addressing and hashes MAY
  deduplicate and verify bytes but MUST NOT replace them. External URLs, host
  paths, provider IDs and agent-log offsets are provenance, never the sole copy.
- **FR-027**: Capture the exact tool request name, call identity, argument object,
  URL/path/command/target, completion result, error, duration and retry/parent
  relationship. Capture the exact memory/context bytes and exact decision state
  that caused or influenced the model call. Generic counts, parameter-key lists,
  redacted summaries and digests are supporting indexes only.
- **FR-028**: Given only AtMem plus a supported evidence-store copy, reconstruct
  a deterministic human-readable and machine-readable run story without the
  original agent, model, logs, workspace, memory database, provider or network.
  The story order is user input → memory/context → decisions → model exchange →
  tools and multimodal artifacts → result/error → known outcome. Missing capture
  is named at the exact boundary and blocks a completeness claim.
- **FR-029**: Produce a deterministic replay manifest containing the original
  ordered inputs, tool contracts, arguments, artifacts and dependency identities.
  Reconstruction and simulation MUST NOT execute external effects. A new real
  execution is a separate, freshly authorized run linked to—not substituted for—
  the historical evidence.
- **FR-030**: Preserve credentials or platform secrets unrelated to the user's
  instruction using protected references or reversible field protection while
  retaining the complete surrounding call. Authorized reveal, artifact access,
  export, replay-manifest creation, capture-mode change and deletion each append
  an evidence-access event.
- **FR-031**: Full-fidelity storage MUST be bounded by explicit owner-visible
  local quotas and retention policy suitable for consumer hardware. AtMem MUST
  reserve capacity before acknowledging capture, apply backpressure or fail a
  controlled pre-dispatch boundary when required evidence cannot become durable,
  and surface the exact affected boundary. It MUST NOT silently discard bytes,
  downgrade to metadata, or prune evidence without an authorized audited policy.

- **SC-011 — Dead-agent disaster gate**: A fixture performs a multimodal run,
  closes and removes the agent process, deletes its logs, workspace, caches,
  original memory/provider stores and model stub, copies only the AtMem evidence
  store into a fresh process, and reconstructs every expected prompt, memory,
  context, decision, model message, call argument/target, result/error, timestamp
  and outcome statement exactly. The test MUST fail if any answer requires an
  opaque ID lookup against the destroyed systems.
  Before key release, direct inspection of the copied store MUST reveal none of
  the planted content or semantic metadata; reconstruction occurs only through
  an authorized AtMem operation under Spec 028.
- **SC-012 — Multimodal round trip**: Golden fixtures compare byte-for-byte text,
  fetched HTML, file, image, audio and video parts before capture, after
  crash/restart, after backup/restore and after export/import. Captions,
  transcripts, thumbnails and hashes are tested only as additional indexes.
- **SC-013 — No generic-evidence acceptance**: UI/API/CLI/MCP tests fail any
  captured run that presents only a count, hash, call ID, “a tool failed”, tool
  name without arguments/target, or error without the original request/result.
  The readable view and exact evidence must agree.
- **SC-014 — Capture modes and replay**: Default installation proves
  full-fidelity capture. Explicit metadata-only/off fixtures are visibly
  non-reconstructable and audited. Replay manifests are deterministic and cause
  zero external effects; separately authorized re-execution creates a new linked
  run and never rewrites history.
- **SC-015 — Capacity and backpressure**: With a deliberately small configured
  quota, concurrent one-megabyte multimodal envelopes produce zero acknowledgments
  before envelope and artifact durability, zero silent full-to-metadata
  downgrades, and an explicit capacity failure before the next controlled model
  or tool dispatch. Crash recovery preserves every acknowledged byte and reports
  every unacknowledged boundary without inventing evidence.
