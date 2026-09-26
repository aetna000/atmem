# 037 — Hermes integration and DolphinBench qualification

**Date:** 2026-09-26  
**Status:** Core binding/provider implementation in progress; no installed compatibility certification or benchmark result yet.  
**Release target:** `2.3.8b2` Hermes preview; prerelease. Stable 2.3.8 maintenance commitments remain unchanged.  
**Owner:** AtMem; Hermes remains the agent runtime, AtFlows remains optional observation.

## Outcome

A Hermes user can connect AtMem, explicitly activate governed memory, remember
across sessions, inspect what was returned, and restore their previous provider.
They do not need Mem0 or a benchmark checkout. DolphinBench then tests the same
installed integration against matched configurations, without implementing any
memory, extraction, ranking, governance or recovery behavior of its own.

This is memory-provider support, not an automatic claim of OpenClaw-equivalent
capture, whole-agent context governance or Hermes workflow continuation.

## User scenarios

1. **Connect safely:** with an existing Hermes profile/provider, install the
   integration and inspect readiness without changing responses or writing
   memories. Explicit activation preserves a recoverable configuration backup.
2. **Remember and inspect:** after activation, provide an authorized preference;
   in a new session in the same scope retrieve it through AtMem. Inspect its
   source and selection decision in the dashboard. Another profile cannot read it.
3. **Correct and revoke:** supersede or revoke that preference; subsequent recall
   cannot deliver the old record, including from prefetched results. Previously
   disclosed host conversation content is not claimed to have been retracted.
4. **Recover configuration:** interrupt setup/restore, restart, and see the exact
   incomplete state and retry action. Restore the previous provider without
   deleting native memory or unrelated settings.
5. **Evaluate fairly:** use the installed integration on pinned public benchmark
   data; freeze memory after ingestion and compare accuracy, costs and latency.
   A failed task remains in the report, not removed from the denominator.

## Requirements

- **FR-001 — Installation and compatibility.** Ship a standalone Hermes memory
  provider named `atmem`, discovered through supported upstream interfaces. Do
  not fork Hermes, inject dependencies into its managed environment, require a
  Mem0 account or import Hermes from AtMem's base installation. Declare exact
  tested host/Python/OS versions and license/dependency compatibility.
- **FR-002 — Setup and restore.** Start in non-influencing readiness mode: no
  memory admission, context injection or provider replacement before explicit
  activation. Preview touched files, back up previous settings, validate before
  switching, preserve native stores, detect conflicting providers and make
  interrupted activation/restore recoverable. Repeated setup is idempotent.
- **FR-003 — Identity.** Bind profile, workspace, authenticated subject, session,
  run and turn to AtMem authority. Display names, prompts, model tool arguments
  and caller-supplied headers cannot establish authorization. Missing or changed
  required identity withholds memory. Concurrent profiles and delegated/cron
  runs cannot inherit another session's authority; child writes are disabled
  until explicitly supported and authorized.
- **FR-004 — Governed lifecycle.** All capture, admission, recall, corrections
  and deletion use product-owned AtMem contracts. Capture is not automatic
  promotion to trusted knowledge. Retry-safe durable writes and bounded queues
  preserve source/evidence linkage; queue failure is visible, never a success
  receipt. Drain acknowledged work before checkpoint completion.
- **FR-005 — Delivery boundary.** Authorize before retrieval content leaves
  AtMem and revalidate candidate IDs at delivery. Declare the precise host
  boundary and race limits. The initial profile is `authorized-at-recall-v1`:
  each fresh recall is authorized before returning to Hermes, as with the
  OpenClaw memory-insertion boundary. Per-model-call revalidation of previously
  disclosed context is separate future work, not an integration or benchmark gate
  (user-approved clarification, 2026-09-26). Do not cache plaintext in adapter static prompts,
  queues or spill files; cached nominations require new authorization. Test
  supersession, expiry, quarantine, deletion and scope revocation. If host hooks
  cannot enforce the claimed delivery boundary, gate that profile as unsupported
  rather than bypassing authority. Native memory remains outside this boundary
  unless a separately verified takeover explicitly controls it.
- **FR-006 — Failure and local operation.** Canonical local memory works without
  hosted intelligence. Unavailable AtMem, invalid credentials, incompatible
  versions and timeouts withhold AtMem context, surface a reason/remedy and
  never silently switch to an ungoverned memory backend. Bound RPC, queue and
  shutdown deadlines and expose pending/failed writes.
- **FR-007 — Evidence.** Retain supported captured content through existing
  encrypted evidence services with access controls, provenance, ordering and
  disclosure audit. Publish a boundary matrix separating prepared, delivered,
  observed model input and tool outcomes. Missing hooks are explicit and never
  advertised as full capture. Do not treat a filtered pre-compression transcript
  as a complete model/tool record. No new plaintext spool or credential logging.
- **FR-008 — User surfaces.** CLI and dashboard share readiness, active provider,
  host/adapter versions, profile, actual endpoint, scope, last successful delivery,
  pending writes, capture coverage and actionable errors. Activation/restore
  require existing admin authority. Include copyable setup guidance without
  secret values, consistent AtMem styling, local display time and UTC evidence.
  AtFlows is optional and receives only authorized correlation/telemetry.
- **FR-009 — Installed acceptance.** Test fresh install, upgrade, disable,
  restore, concurrent sessions, retry/restart of writes and incompatible host
  versions using built artifacts without importing benchmark code. Test macOS
  and Linux; qualify Windows in its actual supported Hermes environment, labeling
  WSL separately from native Windows. Preserve OpenClaw/framework regressions.
- **FR-010 — Inert benchmark adapter.** Implement only upstream runner wiring,
  installed agent invocation, sandboxing, evidence collection and cost accounting.
  Memory features and durable snapshot/read-only enforcement belong in AtMem.
  Pin dataset, licenses, Hermes, AtMem, benchmark, model and grader settings.
  Preserve each dated input and upstream tools, results, app resets and grader.
- **FR-011 — Isolation and freeze.** Ingest full ordered history into one empty
  store per persona via normal product hooks. Wait for durable work; verify a
  real content/generation checkpoint across processes. Block all evaluation
  memory mutations in product authorization, including automatic capture and
  background writes. Evidence/usage go to a separate authorized append-only
  sink. Each test has fresh conversation/runtime and isolated apps. Agent tools
  cannot read facts, test answers, grader, run artifacts or real app connectors.
- **FR-012 — Costs and records.** Record actual per-response usage, complete
  interactions, memory processing, retries, timing, errors and freeze receipts.
  Missing usage is unknown/error, never zero. Keep ingestion and evaluation
  totals separate; submission totals exclude grading/infrastructure, while the
  operator ledger and budget include them. Prevent double counting. Resume only
  identical configurations; reconcile uncertain in-flight work before replay.
- **FR-013 — Evaluation discipline.** Run no-cost contract checks first, then an
  explicitly budget-approved public-data pilot, then full 600-task qualification.
  Freeze configuration before full evaluation. Pilot is not leaderboard evidence.
  Compare matched Hermes/model/settings with native memory and, when credentials
  and budget permit, Mem0. Label published upstream numbers historical, not
  locally rerun controls. Publish all failures, paired differences, uncertainty,
  p50/p95 latency, throughput, resource use and costs. Repeated held-out evidence
  is required for broad superiority claims; the public suite is not private held-out
  evidence after tuning. No target rank is a release gate.
- **FR-014 — Publication and maintenance.** Validate the complete upstream ZIP;
  public submission needs explicit approval. Describe initial listing as
  self-submitted/unverified, not official endorsement. Preserve raw authorized
  evidence and sanitized public reports with limitations and artifact hashes.
  Update integration/setup/reference/troubleshooting/release documentation and
  AtMem.ai docs through owner-reviewed main-only publication. Do not release,
  spend money or deploy by merely approving this planning document.

- **FR-015 — First-class setup parity.** Provide `atmem hermes install`,
  `status`, `verify`, `activate`, `upgrade` and `restore` through one shared
  setup service used by CLI and dashboard. Installation guides discovery of the
  real Hermes Home/profile, current provider, runtime compatibility and scope;
  preview precedes explicit changes. `atmem init` discovers Hermes without
  activating it, and `atmem status` includes its actual endpoint, versions and
  specific repair commands. Never require manual dependency injection or secret
  pasting into generated config. Commands listed here are targets, not shipped commands.
- **FR-016 — Reversible provider migration.** Guided switching explains the
  previous and proposed providers and native-memory coexistence. Preserve prior
  settings and native stores; take a protected backup, verify prerequisites,
  explicitly activate, then verify a real authorized recall. Interrupted changes,
  missing runtimes, occupied ports, stale endpoints and user-edited configuration
  have actionable recovery. Provider migration does not import historical memories;
  show that fact before switching and never claim old memories were transferred.
- **FR-017 — AtFlows integration parity.** Coordinate with AtFlows Spec 006:
  offer optional guided connection, real-event verification, stable profile/session/
  run/turn identifiers and supported model/tool/usage signals. AtFlows remains
  independently usable. Preserve other exporters and model-provider settings.
  Show grouped runs, timeline, latency, errors and usage/cost where actually
  observed; missing usage/cost is unknown, not zero. AtFlows failure cannot
  grant memory access or stop otherwise valid local memory operations. Define
  captured boundaries explicitly; observation does not imply Hermes continuity.

## Acceptance gates

### Native provider-list milestone — 2026-09-26

The user requested that the installed Hermes dashboard discover AtMem through its
native plugin interface. This is an additive, non-influencing installation step,
not permission to skip the existing activation, durability or evidence gates.

- **FR-018 — Discoverable before connection.** Installing the packaged AtMem
  directory plugin must make `atmem` visible through Hermes's actual provider
  discovery and dashboard metadata, including when no connection is configured.
  Missing/invalid credentials must produce an unavailable provider with a clear
  setup reason, not an import failure, a falsely ready provider or leaked secrets.
  Do not patch Hermes core, hardcode its dropdown, install AtMem into Hermes's
  Python environment or replace native memory merely to make an entry appear.
- **FR-019 — Safe installation boundary.** Preview and explicit install must
  target the selected existing Hermes Home, preserve its config/provider/native
  stores, reject unsafe paths and unmanaged existing plugin directories, install
  atomically, and record product-owned file hashes. Repeating an identical install
  is a no-op. Never overwrite user edits. Discovery installation needs no AtMem
  administrator credential and grants no memory access. A connection remains a
  separate administrative operation under FR-003/015/016; the live service must
  support the scoped protocol before activation is offered.
- **SC-008:** A built artifact installs into a clean test Home and is listed by
  the pinned Hermes's real discovery and dashboard helpers. Unconfigured AtMem
  is unavailable: guarded dashboard activation routes reject it and the memory-setup CLI
  delegates to a no-write AtMem setup hook. Hermes's generic plugin picker,
  settings/raw-config APIs and raw config edits can still select it; the host warns and falls back to native
  memory at startup. This host behavior is not AtMem activation or governance.
  A configured temporary test binding exercises normal product capture,
  review/admission and new-session recall independently
  of any benchmark. Local default provider remains unchanged after installation.

User-facing outcome for this milestone: **AtMem is listed; connection/activation
status is shown truthfully.** Full operational integration remains gated by the
existing SC-001–007; this milestone does not redefine those gates as complete.

Discovery diagnostics use a static manifest description and setup/status hook;
the pinned dashboard does not render `unavailable_reason()`. No credential form
or generic setup schema is added. Missing configuration requires no network.
Configured discovery retains a loopback health probe with a one-second socket
budget (not a strict total deadline), explicitly deviating from the host's
local-only availability recommendation to avoid calling a disabled binding ready.
Full activation remains blocked until the host fallback/activation boundaries,
credential copying by profile backup/export, and durable capture are qualified.

Preview is read-only, including no locks, Home creation or configuration writes.
Apply may create the missing `plugins/` parent, plugin directory, a sibling lock and hidden staging
directory; it preserves `.atmem`, `.env`, config and native stores. A receipt
authenticates owned payload hashes, not third-party authorship. Unsafe ownership,
symlinks and ambiguous existing targets are rejected. Installation uses exclusive
no-replace publication; interrupted hidden staging is not discovered and must
never cause deletion of an unmarked directory. Native Windows installation is
unqualified and explicitly refused in this slice.

The installer ignores only regular generated `__pycache__` content when checking
payload ownership; extra source files are conflicts. Staging names start with
double underscores so both Hermes discovery systems ignore interrupted stages.
Plugin metadata and status label this preview local CLI-only; failed initialization
must leave all reads/writes disabled. Dashboard restart is required after payload
changes. Record the pinned host and the risk that Hermes may attempt catalog
reinstallation of a missing selected provider; do not claim control of that host
behavior or delete an active provider in this slice.

- **SC-001:** FR-001/002/006/009 pass from clean installed artifacts; a new user
  can follow one documented setup sequence without editing Python or running a
  benchmark. Default activation changes no existing host behavior.
- **SC-002:** FR-003/004/005/011 negative tests produce zero unauthorized memory
  deliveries or evaluation memory mutations, including concurrent/race cases.
- **SC-003:** FR-007/008 tests link authorized returned bytes to their decisions
  and show truthful capture gaps; encrypted-store-only reconstruction succeeds
  for each declared supported boundary after fixture host logs are removed.
- **SC-004:** FR-010/012/013 dry checks and pilot retain complete per-call evidence;
  budget exhaustion stops new paid calls with in-flight reservation accounted for.
- **SC-005:** FR-013/014 full qualification retains three full ingestion histories,
  exactly 600 results including failures, valid packaging and a reproducible report.
  Unfinished runs remain explicitly partial. Higher ranking is an objective, not
  an asserted outcome or condition for preserving results.

- **SC-006:** Installed fresh and upgrade journeys complete through the documented
  CLI or dashboard without manual file editing: discover, preview, install,
  activate, remember, new-session recall, inspect, upgrade and restore. Repeat
  setup is idempotent; previous provider and unrelated settings survive restore.
  Compare each capability against shipped OpenClaw behavior using `parity.md`.
- **SC-007:** A real installed Hermes session appears in both dashboards with
  matching supported identifiers; a second profile cannot be misattributed.
  Health checks alone never report activity. Exercise AtFlows outage, reconnection,
  alternate ports and secret-redaction cases with no unauthorized disclosure.

## Non-goals and dependencies

### Authorized local service update — 2026-09-26

The user requested updating the installed AtMem after native plugin discovery.
Deploy the already-tested development artifact locally, preserving existing
memory, companion packages and OpenClaw configuration. Retain rollback material,
restart only the AtMem dashboard daemon and verify both normal dashboard access
and the scoped Hermes RPC authentication boundary. This is not publication and
does not bypass the pending connection/activation gates or provision credentials.
Report unchanged release metadata alongside the development artifact hash.

No Hermes fork, Mem0 wrapper, replacement agent loop, hidden recovery controller,
native-memory import, automatic account creation or automatic benchmark upload.
No whole-agent secrecy guarantee after legitimate context disclosure. No global
exactly-once tool execution or new continuity claim. Existing Specs 007/011/019/
020/028/030 retain identity, conformance, context, evidence, encryption and Home
ownership. Benchmarking 002 retains continuity ownership. Preserve scheduled
2.3.8 MCP discovery and AtFlows redaction; publish the targeted Hermes beta only after gates.
