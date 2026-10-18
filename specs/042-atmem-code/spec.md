# AtMem Code: automatic project memory for coding agents

**Status:** Phases 0–8 implementation and qualification, 2026-10-14. See [implementation-status.md](implementation-status.md) for completed work and open acceptance blockers; the five-host product is not fully qualified.
**Target:** AtMem 2.3.9 release track; final release number and date follow qualification.
**Baseline:** Published AtMem 2.3.8. Work is isolated from `laya_changes`.

**2026-10-17 expansion:** FR-017–FR-028 and SC-008–SC-013 below formalize the
pending knowledge/experience/Memory Explorer workstream. Historical phase 0–8
qualification does not cover it. Its runtime implementation is not completed.

## Overview

AtMem Code is an installation flavour of the existing AtMem product, not a separate memory authority, service or repository. It carries useful project knowledge between coding sessions and agents without requiring the model to remember to call an MCP tool. It connects agent lifecycle events to one local memory service, supplies a bounded context pack at the next relevant boundary, and offers explicit search, correction, and deletion in both CLI and dashboard. A project memory can be exported as a portable, versioned bundle and restored for an authorized copy of the project.

The named adapter targets are Muse Code, Claude Code, Grok's coding CLI, GitHub Copilot CLI, and Codex. These are separate host surfaces behind one host-neutral contract, not five memory databases. GitHub Copilot in VS Code and its cloud coding agent are separate surfaces requiring their own capability checks; a Copilot CLI result does not establish support for them. An adapter is described as automatic only after its actual capture and context-delivery behavior is verified for a pinned host version and operating system. Other MCP clients may use explicit tools without receiving the automatic claim.

Code structure is a separate, derived retrieval surface. An optional code graph can answer symbol, call, import, and impact questions under a token budget. Project memories describe decisions, conventions, failures, and outcomes; graph nodes describe the current repository. Source code and current Git state outrank stale memory assertions.

## User scenarios

1. A developer installs AtMem Code in one repository, explicitly enables two available coding-agent adapters during setup, and completes a task in one agent. A relevant, source-linked project lesson is available to the other agent in its next task without a manual save or recall call. There is no shadow-run period. The same shared-project contract applies to Muse Code, Claude Code, Grok CLI, GitHub Copilot CLI, and Codex when their adapters pass the host gates.
2. The developer starts a new task. The adapter submits a small, source-linked context pack at its verified host injection boundary, records the bytes it submitted and the host's acknowledgement if available, and allows explicit search during the session. The receipt does not claim those bytes reached the model unless that boundary is independently observable.
3. A task changes code that invalidates a stored architecture note. AtMem marks the note stale or routes it to review; subsequent context does not present the old claim as current.
4. The developer searches and clears memories for one project, one profile, or one agent in the dashboard. A preview identifies the exact affected records and derived indexes; a receipt verifies the requested deletion.
5. A request with an authorized `docs` tag is routed to a configured RAG provider; one tagged `external-memory` goes to Mem0; an untagged request uses the local default. The response identifies the source provider and delivered bytes. Unauthorized tags cannot change scope or cause network egress.
6. The developer turns off optional review queues for routine coding. Core controls and the default evidence capture remain in force. If the developer separately opts into reduced capture, the affected runs are visibly marked `not_reconstructable`.
7. A developer exports one project's memory bundle, moves it to another machine or clone, verifies and imports it, then explicitly attaches the copied project to the restored identity. Canonical memories, lifecycle and source links survive; host hooks and credentials are configured anew.
8. A developer selects a configured RAG or external-memory route in CLI or dashboard and sees which provider handled a query, what context was returned, and whether it was submitted to the coding agent. They can switch the route back to AtMem without changing the agent adapter.

## Functional requirements

- **FR-001 — Installation flavour.** Provide a Code choice in AtMem onboarding and an equivalent `atmem code` guided setup for a repository and selected coding agents, with per-host status, doctor, preview, enable, disable, and uninstall/restore operations. This installs/configures the same AtMem package and memory service; Code is a selectable profile with optional adapter/parser dependencies, not a fork or second canonical database. Installing the package alone leaves Code disabled and non-influencing. The user explicitly enables selected adapters during setup; once enabled, capture and injection operate immediately without a shadow period. `disable` only stops automatic capture and context injection, leaving hooks, saved memory and restore material in place; `enable` resumes; only explicit `uninstall` restores prior host configuration. Setup must not silently activate an adapter. Base `pip install atmem` remains useful without a code parser, hosted provider, or model download. Installation must document local storage location, permissions, dependency size, and any host restart.
- **FR-002 — Host capability.** Maintain a versioned capability matrix for Muse Code, Claude Code, Grok CLI, GitHub Copilot CLI, and Codex, with GitHub Copilot editor/cloud surfaces assessed separately. Each adapter declares supported lifecycle events, capture coverage, context injection point, acknowledgement capability and known gaps. Setup verifies hook execution and the supported injection boundary before claiming automatic operation. A submitted pack, a host acknowledgement and observed model input are distinct receipt states; an adapter may claim only the strongest state it can verify. Unsupported or untrusted hooks produce an explicit degraded status. A host with only MCP tools is labelled manual, not automatic.
- **FR-003 — Automatic capture.** Supported hooks submit authenticated user turns and bounded task outcomes, including changed-file identities and test/build outcomes, to a common intake contract. Capture is idempotent across retries, compaction, restarts, and multiple host agents. Raw repository files, terminal output, and complete transcripts are not automatically made canonical memories. Once an adapter is enabled, ordinary turns feed the formation path without an agent-initiated `remember` call; explicit remember remains available.
- **FR-004 — Formation.** AtMem derives project memory candidates with source, actor, project, profile, agent, session, time, Git revision and validity metadata. It rejects unsupported or transient claims; distinguishes project knowledge, personal preference, architecture decision, workflow, failure and fix; and supports update, supersession and explicit forgetting. A model may propose but cannot directly write canonical memory.
- **FR-005 — Secret boundary.** Every automatic intake and semantic field is screened before any write to an unprotected episode, canonical memory, vector, graph, queue, audit payload, export, or provider request. The 2.3.8 `remember()` raw-episode-before-screening and `interpreted_fact` bypasses must be fixed. Recognized credentials are excluded from searchable and outbound memory surfaces; where full-fidelity evidence requires their original bytes, those bytes are retained only as reversibly protected fields in the encrypted evidence envelope with privileged access and access audit. A refusal code or hash alone must not be presented as full-fidelity evidence. Common token formats, URLs, headers, key blocks and unknown high-entropy values are covered by tests; unknown secrets remain a measured residual risk.
- **FR-006 — Automatic recall.** On each supported task boundary after explicit enablement, the adapter requests a bounded context pack using current task, project identity and permissions. It submits only authorized, current evidence at the verified host boundary and returns a receipt identifying exact submitted bytes, host acknowledgement when available, and whether model input was independently observed. Explicit search remains available during a session. Missing context, timeout or unhealthy service cannot silently imply successful injection.
- **FR-007 — Shared scope.** Stable repository identity is independent of clone path, worktree and coding host, while user-private and agent-private memories remain separate. Memories written through one supported agent are eligible for another supported agent only when both are bound to the same authorized project/profile scope. This release supports one authorized local service and explicit portable export/import; live cross-user or cross-machine sync is out of scope. A common repository name alone never grants access. Scope changes and Git remote changes must not merge unrelated projects silently.
- **FR-008 — Governance controls.** The default Code experience may hide optional approval queues, manual review and investigation UI, and the user may switch those workflow controls off or on through CLI or dashboard. This switch never disables canonical authorization, scope isolation, secret protection, provenance, lifecycle enforcement, encryption, deletion verification or required evidence/access audit. Full-fidelity evidence capture remains the default supported profile; an explicit reduced-capture choice is recorded and labels affected runs `not_reconstructable`. Any host whose capture coverage is below full-fidelity is labelled accordingly, not advertised as a complete Agent Black Box. A mode that bypasses the core controls is out of scope under the current constitution.
- **FR-009 — Dashboard.** One AtMem dashboard lists, searches, filters, inspects, edits or supersedes, and deletes project memories by project, profile, agent, type, validity, source and time. Bulk clear provides preview, bounded selection, authorization, progress and a verifiable completion receipt. It distinguishes canonical memory, code-graph index and external-provider data.
- **FR-010 — Tagged context routing.** A versioned request carries declared task tags and scope. A user-configured provider contract identifies a local RAG service or registered memory provider such as Mem0, its endpoint, credentials reference, permitted scope, egress policy, request/response schema, timeout and fallback. An external route uses a visibly named `delegated-context` authority mode and the existing signed, scoped delegated-context contract. AtMem authorizes and screens the outbound query before sending it to that provider instead of searching its own memories for the route. Route selection is deterministic and inspectable; a tag cannot grant authority or egress. AtMem validates provider identity, signature, binding, expiry, size and result contract, attributes provenance, labels external content as delegated and records the actual submission assurance level; it does not claim independent truth verification of external documents. Provider unavailability follows a configured safe native fallback or withholds context. External-provider data is not silently promoted into canonical AtMem memory.
- **FR-011 — Code graph.** The optional graph indexes eligible repository files into symbols and relationships with file/commit lineage. It respects ignore rules, excludes secrets and generated files, updates or invalidates on file and branch changes, and answers bounded structural queries. A stale index is visible and cannot be presented as current. The graph does not become a second canonical memory authority.
- **FR-012 — Compatibility.** Existing 2.3.8 installations and deterministic memory APIs remain compatible; code mode is opt-in. The product must support the declared Python range and test installer, hooks, dashboard and local service on macOS, Windows and Linux before claiming each host combination.
- **FR-013 — Evaluation.** Use [VibeMemBench](https://arxiv.org/abs/2609.23570) as the primary memory-specific real-coding-task benchmark, preserving its repository histories, target task definitions and executable grading. Compare the same pinned agent/model and task under memory off, native host memory, AtMem Code memory only, graph only, and combined modes; add a configured competing memory system and a strong repository-map/graph control where technically comparable. Measure whether AtMem constructs and retrieves useful experience from prior history, not merely whether an oracle experience helps when directly injected. Because VibeMemBench selects targets where prior experience helped a reference solver, run a separate preregistered, unfiltered real-issue control to measure ordinary-work benefit and harm; do not pool the two results. Report executable task resolution, missed required context, stale/wrong-context injection, total input/output tokens, context bytes, p50/p95 latency, cost, capture success, secret retention, indexing overhead and errors/refusals. Publish paired raw receipts, uncertainty, dataset/license and immutable version, chronological leakage controls, configuration, hardware and repetition policy. No graph token-saving or general coding-improvement percentage is a release claim until measured against ordinary file exploration and a strong repository-map baseline on a held-out set.
- **FR-014 — Release.** 2.3.9 is the AtMem Code track. `v2.3.9b1` is an existing historical Laya prerelease and must never be moved or presented as the proposed AtMem Code release. The actual 2.3.9 candidate version is chosen after gates pass, with matching package and bridge pins and the coordinated release workflow.
- **FR-015 — Portable project bundle.** Export and import one authorized project's canonical memories, lifecycle history, source metadata, scope policy and required evidence as a versioned, integrity-checked, encrypted bundle. Include a manifest for schema and embedding/index revisions. A restored bundle can rebuild derived vector and graph indexes; it must not require the old host agent or original clone path. Host hook settings, machine-bound credentials and external-provider secrets are excluded and reconfigured on import. Import previews target project identity and collisions, requires explicit authorization and never silently merges unrelated projects. Verify round-trip content, lifecycle, scope isolation and search parity in a fresh installation.
- **FR-016 — Configurability and search.** CLI and dashboard expose the same readable configuration and supported changes for host adapters, project/profile mapping, capture/review controls, provider routes, context budgets and storage health. Changes show their effective scope and require confirmation where they alter egress, sharing or deletion. Both interfaces provide authorized keyword/semantic memory search with project, profile, agent, type, source, validity and time filters, plus source inspection and correction/forget actions. Neither interface displays secrets or bypasses authorization.

## Acceptance scenarios

- In a clean repository, package installation alone makes no host change. The user explicitly enables each selected adapter during setup; its real hook probe succeeds, it captures one safe coding outcome, then submits a relevant memory at the verified injection boundary in a new session without the agent calling a memory tool. No shadow run is required. The receipt's context digest matches the submitted bytes and labels host acknowledgement and model-input observation separately. This test is repeated for every host/OS combination advertised as automatic.
- Two different supported coding agents, using the same authorized project identity, retrieve the same shared decision; a private preference and an unrelated repository's memory remain invisible. A five-agent matrix covers Muse Code, Claude Code, Grok CLI, GitHub Copilot CLI and Codex; unsupported or manual-only cells are published rather than counted as passes.
- A credential placed in a user message, interpreted fact, tool output, file path, source URL, provider response or metadata field does not appear in searchable memory, plaintext SQLite content, derived indexes, ordinary audit payloads, queue, unprivileged export or external request. If required for full-fidelity evidence, its original bytes are available only through privileged, audited decryption of a protected evidence field.
- Changing a referenced source file or switching branch invalidates or visibly qualifies a stale graph result and any memory claim dependent on it.
- Clearing an exact project/profile/agent selection removes its canonical and derived records; adjacent scopes remain unchanged. A provider-owned record is deleted only if that provider confirms it; otherwise the dashboard reports partial completion.
- A `docs` tag selects only the authorized docs route; a malformed or unauthorized tag cannot contact an external service. The receipt reports provider, fallback/withhold decision and delivered context identity.
- Installation and disabling code mode leave the 2.3.8 memory path usable; a failed hook installation restores the previous host configuration.
- A project bundle exported on one machine imports into a fresh AtMem installation for a new authorized clone; canonical memory and source-linked search results match after derived-index rebuild, while host configuration and credentials do not travel with the bundle.
- Turning optional review workflow off removes approval queues from ordinary coding use but does not bypass scope, secret, lifecycle or deletion gates; selecting reduced evidence capture records the choice and marks affected runs `not_reconstructable`.
- A provider route configured in CLI is visible and editable in the dashboard, and vice versa; a search request records whether AtMem or the registered external provider served it and what was submitted to the host.
- On a frozen VibeMemBench target, both control and AtMem-enabled runs begin from the same repository commit, prior-history boundary, agent/model version and budget. AtMem must build and retrieve its own memory from the permitted history; it cannot receive the benchmark's verified experience as an oracle injection. The executable grader and complete token/latency receipts determine the paired result. An unfiltered real-issue control is reported separately, including cases where memory harms the task.

## Success criteria

- **SC-001:** Every host and OS combination advertised as automatic passes the new-session capture and context-delivery probe; unsupported combinations are labelled manual or unavailable.
- **SC-002:** All secret-regression fixtures are absent as plaintext from every tested persistent copy and outbound request; no fixture becomes searchable canonical or derived memory. Required protected evidence can be recovered only by authorized, audited decryption. Tests include false-positive and false-negative reports.
- **SC-003:** Cross-agent project sharing and private-scope isolation pass paired integration tests.
- **SC-004:** A bulk deletion test verifies zero remaining canonical or derived hits in the selected scope and no change in an adjacent scope.
- **SC-005:** The benchmark report publishes separate VibeMemBench and unfiltered real-issue results with paired executable quality, total tokens, p50/p95 latency, cost, errors and raw receipts, plus corpus/version/license, frozen task IDs, configuration, leakage controls and uncertainty. Missing corpus or comparable baseline visibly downgrades the result; a release makes no unmeasured savings claim.
- **SC-006:** An encrypted project-bundle round trip on a fresh installation preserves canonical records, source and lifecycle links, authorized search results and scope isolation; stale derived indexes are rebuilt and no host credentials are present in the bundle.
- **SC-007:** Every setting advertised for Code can be read and changed through both CLI and dashboard, or is explicitly marked read-only with a reason; a two-agent session passes automatic capture and recall without a manual memory-tool call.

## Scope boundary

The 2.3.9 design does not require a trained Laya decision model, a hosted account, a mandatory graph parser in the base install, or automatic provider egress. Provider routing and code graph are user-optional features but are included in phases 0–8 of this development request. Live cross-user/machine sync is excluded; portable export/import is included. Phase 9 benchmark and release work is deferred by the owner's later instruction. Release notes, when release work is separately authorized, must identify the qualified subset exactly.

## Pending expansion: maintained knowledge, experience and exploration

This is a separately scoped workstream within Spec 042, not a second product or
memory authority. It supplies product capabilities needed by [Click Spec 043](../043-click-historical-replay/spec.md).
The source-incorporation architecture is in [code-knowledge-plan.md](code-knowledge-plan.md).
Documents/structured-data expansion remains in the broader parent plan; this
workstream's first acceptance surface is code. No document-format parity follows.

### User scenarios

1. A developer explores repository structure, follows a source-backed dependency
   path and sees the extraction coverage without a hosted model.
2. An enabled agent finishes an attempt. AtMem can form an attributed experience
   linked to authorized intent, actions and observed test receipts. On a later
   revision it recalls only the parts whose applicability is supported, including
   relevant failed attempts; it does not invent a successful fix.
3. A user browses one Memory Explorer to find a decision, inspect its source,
   history and applicability, see its actual delivery receipt and safely correct
   or forget it. No database query or copying technical IDs is necessary.

### Functional requirements (all pending)

- **FR-017 — Upstream-first parity.** Maintain a pinned source/dependency/license
  and capability register. Reuse/adapt upstream implementation and tests before
  replacement; record incompatibility and evidence for replacements. Differential
  tests cover the frozen supported language/framework/platform envelope. Missing
  cells remain gaps; source incorporation alone is not parity.
- **FR-018 — Extraction.** Authorized immutable source snapshots feed a bounded,
  isolated, pinned Enola or justified equivalent worker. Produce typed repository,
  module, symbol, endpoint, resource, dependency and test-reference objects where
  supported, with source anchors, hashes, assurance and extraction receipts.
  Structural queries work without an LLM/embeddings. Do not execute repository
  code, fetch dependencies or leak source through worker telemetry by default.
- **FR-019 — Knowledge maintenance.** Derived projections are scope-checked,
  encrypted, rebuildable and atomically generation-published. Edits, renames,
  deletion, resolver/config changes and dependency effects invalidate affected
  evidence; no mixed-generation traversal or deleted-data resurrection on restore.
- **FR-020 — Structural queries.** Provide bounded component exploration,
  dependencies/dependents, paths, potential impact, architecture overview and
  snapshot differences. Return evidence/coverage/unresolved states, not fabricated
  runtime guarantees; enforce authorization at intermediate edges and nodes.
- **FR-021 — Experience formation.** Add a product-owned governed proposal path
  for authorized coding attempts, distinct from existing user-assertion formation.
  An experience records task intent, attempted action, affected source anchors,
  observed outcome, applicability, provenance and uncertainty. Sources may be
  authorized agent/tool observations, but remain observations rather than authority.
  Only bound, validated execution receipts support an observed test outcome;
  assistant text or exit code alone cannot prove a general successful fix. Each
  receipt binds command, source/environment identity, execution identity and
  captured result under an approved producer contract. Keep user assertions,
  hypotheses, observed failures and verified bounded outcomes distinct. Intelligence
  may propose, never directly write or authorize. No oracle lessons or training.
- **FR-022 — Cross-revision applicability.** The product, not a benchmark bypass,
  assesses experience against current authorized source/config/environment anchors.
  Unchanged applicable experience can survive unrelated edits or commits. Changed
  dependencies and unresolved applicability cause withholding/review; branch names
  alone never authorize reuse. Worktrees remain distinct. This service must work
  for experience-only use without the richer graph; source hashes and explicit
  dependency declarations can support conservative decisions. Recheck at delivery.
- **FR-023 — Unified context.** Existing qualified adapters use one authorized
  planner to combine experience and optional structure within a shared byte/token
  budget, deduplicate evidence and preserve truthful delivery assurance. Keep native
  tools available. Model absence/failure cannot widen authority or change disabled
  behavior; this work does not require Laya or double semantic classification.
- **FR-024 — Memory Explorer.** Offer one readable search/browse/detail entry point
  with optional timeline/source-tree/bounded-relationship views, source excerpts,
  history, freshness, scope, applicability, formation decisions and exact use/
  withholding receipts. Support correction/supersession, reindex and scoped clear
  with previews. CLI/MCP/dashboard share authority. No whole-database browser dump,
  invented reasoning, secret disclosure or confusing missing evidence with no use.
- **FR-025 — Usability/accessibility.** Implement keyboard-complete, focus-preserving,
  non-colour-only exploration with equivalent list access. Run the five formative
  journeys and baseline-relative targets in the knowledge plan. This small study
  does not replace the separate replicated investigation claim protocol in
  `specs/usability-protocol.md` or establish population-level benefit.
- **FR-026 — Lifecycle/portability.** Extend encrypted project bundles, migration,
  inspection/export privileges and canonical/derived deletion to new objects,
  experience and receipts; no plaintext auxiliary storage or credentials in bundles.
- **FR-027 — Qualification.** Publish separate host/platform capability results for
  prompt automation, observed task outcomes, compaction/flush and full reconstruction.
  Existing prompt-only qualification does not imply any other tier. Exercise
  installed artifacts on claimed platforms and preserve current 2.3.8 APIs/defaults.
- **FR-028 — Pilot readiness.** Export a versioned product capability receipt for
  Spec 043. On disjoint authentic attempts, prove formation from eligible non-user
  evidence and appropriate later-revision recall/withholding before labelling B/D
  experience-capable; zero formed memories must be reported, not hand-filled.
  C/D additionally need the relevant rich extraction/query/assembly gates. Full
  parity and human usability evaluation remain separate from minimal pilot readiness.

### Success criteria (all pending)

- **SC-008:** Frozen extraction/query coverage passes differential and independent
  source-anchor tests for every claimed cell; unsupported cells are explicit.
- **SC-009:** Disjoint product tests form source-bound experience from authorized
  attempts, retain failed/unknown outcomes honestly and reject fabricated receipts.
- **SC-010:** Unchanged anchored experiences survive unrelated changes; changed,
  unauthorized, deleted or unresolved anchors are withheld across worktrees and
  intervening edits at the final delivery boundary, including experience-only mode.
- **SC-011:** All five Explorer journeys and the declared formative usability and
  accessibility targets pass; sources, receipts and corrective effects are inspectable.
- **SC-012:** Upgrade, encrypted bundle restore, role denial, deletion, worker crash
  and installed-platform tests preserve canonical authority and old disabled behavior.
- **SC-013:** Product capability receipts identify exact build/configuration and
  remaining gaps; the Click harness cannot upgrade missing capabilities or declare
  partial prompt capture to be full reconstruction.
