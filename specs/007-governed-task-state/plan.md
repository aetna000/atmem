# Implementation Plan: Governed Task State

**Branch**: `future/007-governed-task-state` | **Date**: 2026-09-04 | **Spec**: `specs/007-governed-task-state/spec.md`

## Summary

Add a separate AtMem-owned execution-state plane for active tasks. A task has a
versioned profile, stable scope, lifecycle, immutable state revisions,
structured items, constraints, dependencies, and evidence. AtBot, adapters,
deterministic rules, and operators submit bounded deltas against an expected
revision. AtMem validates and atomically commits or rejects each delta, then
delivers a minimal byte-stable current-state package at supported model
boundaries. Existing long-term memory, framework checkpoints, host execution,
shadow mode, and safe local fallback remain intact.

## Technical Context

- **Language/version**: Python 3.10–3.13; TypeScript only for the existing
  OpenClaw bridge changes needed to emit task lifecycle hooks.
- **Primary dependencies**: Python standard library, existing AtMem SQLite and
  canonical JSON helpers, existing AtBot provider abstraction, existing
  OpenClaw/Pydantic AI/LangGraph/generic adapters. No new mandatory SDK.
- **Storage**: SQLite remains canonical. Append-only task revisions and
  transition decisions live beside, but not inside, canonical long-term memory
  records. Any cache or projection is derived and generation-bound.
- **Testing**: pytest contract/unit/integration/property-style concurrency and
  persisted-upgrade tests; existing npm typecheck/test/smoke for OpenClaw.
- **Target**: local-first library, CLI, loopback dashboard, and host adapters on
  macOS and Linux.
- **Performance**: local validation plus SQLite commit p95 below 25 ms across
  1,000 single-writer operations without concurrent write contention,
  excluding model/tool/verifier execution. Contended writes are a separate
  correctness test without that latency claim.
- **Security**: fail-closed four-axis task scope, optimistic concurrency,
  evidence validation, no direct AtBot mutation, explicit activation, minimal
  context, exact exposure proof, and verifiable deletion.
- **Scale for this feature**: multiple concurrent tasks per persistent agent;
  production multi-tenant service scaling remains a separate future feature.
- **Concrete prerequisites**: existing `AuthorityScope`, canonical JSON/digest
  helpers, SQLite transaction/migration support, control preparation/exposure
  evidence, host-neutral adapter lifecycle identity, and the authorized AtBot
  companion boundary. T000 pins these symbols and behaviours before feature
  work. No unpublished roadmap specification is a dependency; Spec 007 owns
  its task-specific proposal, transition, provenance, and fallback contracts.

## Constitution Check

- **Authority Before Intelligence — pass**: task content is scope-authorized
  before AtBot sees it. AtBot returns deltas only; AtMem revalidates the current
  head and commits. No intelligence component owns task state.
- **Provenance and Exact Evidence — pass**: every proposal, decision, revision,
  context package, exposure, guard, correction, and lifecycle event binds actor,
  source, assurance, task/revision, and digest. Host-observed success remains
  distinct from independent outcome proof.
- **Safe Defaults and Reversibility — pass**: the feature is disabled by
  default; shadow mode cannot influence models or block host actions. Revisions
  are append-only, corrections preserve history, and existing host restore
  behavior remains unchanged.
- **Scope, Privacy, and Verifiable Deletion — pass**: subject, workspace, agent,
  and task scope is exact; active context is minimal; terminal/deleted state is
  excluded; deletion covers revisions and derived representations.
- **Contract-First Host Neutrality — pass**: task contracts are independent of
  OpenClaw, Pydantic AI, and LangGraph. Adapters map their hooks without
  replacing native messages, checkpoints, tools, models, or execution.
- **Executable Claims — pass**: every user-visible guard and delivery claim has
  contract and integration coverage; benchmarks distinguish detection from
  actual host enforcement.
- **Local-First and Replaceable Intelligence — pass**: validation, typed host
  deltas, `no_change`, state delivery, and completion gates work without AtBot.
  Remote model use remains optional and attributable.
- **Engineering constraints — pass**: SQLite upgrades, Python 3.10–3.13,
  dependency-light base install, CLI/dashboard parity, and Apache-2.0 licence
  checks are explicit release gates.

No constitution exception is required.

## Architecture

```text
Authenticated host observation / tool result / operator correction
  → TaskStateProposal(expected revision, bounded delta, evidence refs)
  → AtMem scope + lifecycle + evidence validation
  → profile transition policy + dependency/completion checks
  → atomic decision
      ├── accepted → immutable revision + new head
      ├── no_change → step outcome only
      ├── conflict → no mutation
      └── rejected → no mutation + reasons
  → task evidence event

Before read, preparation, proposal, or lifecycle mutation
  → evaluate immutable profile expiry rule with trusted UTC time
  → if due, atomically commit one `expired` terminal head
  → record policy rule + evaluated time + prior revision
  → withhold task context

Before supported model boundary in active mode
  → require an explicitly supplied task ID
  → resolve that exact eligible open task and current head
  → never select another open task as fallback
  → authorize scope and lifecycle
  → construct minimal stable task-state bytes
  → combine as a separate governed-data section beside recalled memory
  → exact exposure confirmation and flight evidence
```

AtMem does not choose or execute the next host action. Guard signals and
completion decisions are authoritative AtMem outputs; a host is credited with
enforcement only when its adapter reports and proves that boundary.

## Design Decisions

### 1. Separate task-state domain

Create `atmem/task_state/` rather than adding workflow fields to long-term
`MemoryRecord`. This prevents temporary progress from appearing in semantic
recall, entity graph traversal, memory lifecycle operations, or permanent user
profiles. Durable facts discovered during a task continue through the normal
source-capture and memory-admission path.

Public dependency-free contracts live in `atmem/contracts/task_state.py` and
JSON schemas under `atmem/schemas/v1/`. The first formats are additive:

```text
atmem-task-profile-v1
atmem-task-start-request-v1
atmem-task-state-v1
atmem-task-state-proposal-v1
atmem-task-transition-decision-v1
atmem-task-context-package-v1
atmem-task-guard-v1
```

Before building those contracts, a prerequisite test pins the existing
authority-scope, canonical serialization, SQLite transaction/migration,
preparation/exposure, adapter identity, and AtBot-boundary APIs. A missing
shared primitive fails T000 explicitly; task-specific types are implemented
inside Spec 007 without waiting for unpublished roadmap work. T004 then adds
the dependency-free trusted UTC clock used by every task-state timestamp before
the walking skeleton or service orchestration is implemented.

### 1a. Early walking skeleton

Immediately after the minimum profile, repository, and transition policy are
available, implement one local end-to-end slice: start a `general-v1` task,
read revision 1, apply `set_item_status`, apply `set_phase`, record
`no_change`, restart the process, and read the same head. It uses no AtBot,
semantic service, guard, dashboard, or host adapter. This validates transaction,
revision, scope, digest, and provenance assumptions before richer state depends
on them.

### 2. Canonical state and persistence

Add SQLite tables through the existing idempotent schema initializer:

- `governed_task_profiles`: versioned profile definition and digest;
- `governed_tasks`: stable scope/lifecycle identity, current head pointer,
  nullable `paused_at_utc`, and integer `no_progress_paused_ms` accumulated
  since the latest accepted semantic-progress transition;
- `governed_task_revisions`: immutable canonical snapshot, parent revision,
  transition decision, actor/source/evidence, digest, and timestamp;
- `governed_task_provenance`: field-, item-status-, constraint-, dependency-,
  blocker-, and lifecycle-level lineage with introducing/superseded revisions;
- `governed_task_proposals`: idempotency, expected revision, closed delta,
  decision, reason codes, and optional resulting revision;
- `governed_task_steps`: one `accepted`/`rejected`/`conflict`/`no_change`
  outcome per observed step, including action fingerprint and progress marker.

Task context packages and exposures use existing control evidence and flight
stores rather than creating a second receipt authority. Derived dashboard
counts or caches may be rebuilt from task heads and revisions.

One SQLite transaction checks scope, lifecycle, expected head, idempotency,
profile rules, evidence references, and then inserts the decision/revision and
advances the head. A unique constraint prevents more than one accepted
successor from the same task revision.

### 3. State and delta shape

A canonical snapshot contains only bounded structured values:

```text
task_id, profile_id/version
lifecycle: open | paused | completed | cancelled | expired
revision
goal
phase
constraints[]
remaining_sources[] / completed_sources[]
schema {fields[], locked}
items[] {
  item_id, content, status, required, dependencies[],
  blocker_or_skip_reason, assurance, evidence_refs[]
}
last_progress {step_id, revision, occurred_at}
```

Items and fields use stable deterministic ordering. Free-form content,
constraints, item counts, dependencies, and evidence lists have explicit size
limits. Proposals are closed operation lists such as `add_item`, `set_field`,
`set_item_status`, `set_phase`, `add_constraint`, `lock_schema`, and
`set_lifecycle`; full replacement snapshots are rejected.

### 4. Profiles and transition policy

Ship one built-in `general-v1` profile with phases:

```text
plan → collect → validate → execute → verify → complete
```

Profiles declare allowed phase edges, item-status edges, schema-lock behavior,
required assurance, completion predicates, no-progress thresholds, and optional
absolute-age and no-progress-age expiry thresholds. They are
versioned and digest-bound to each task. Registration validates a closed schema
and is an administrative action; tasks never mutate their profile. The
administrative service and `atmem task profile register|list|show|verify`
commands support dry-run validation, immutable version conflict detection, and
tamper-evident registration without enabling the profile for any scope.

The policy engine derives `ready` only when dependencies and constraints permit
it, rejects completed-to-running regressions unless an operator correction rule
allows them, and denies task completion until every required item is completed
or validly skipped and verification gates pass.

Expiry uses a dependency-free `TrustedUtcClock` interface whose `now()` returns
an aware UTC `datetime`. Production uses `SystemUtcClock`; tests inject a
deterministic clock. The same clock supplies task creation, revision, progress,
pause/resume, decision, evidence, and expiry evaluation timestamps so mixed
time sources cannot change boundary behavior. Expiry is evaluated lazily before
every read, context preparation, proposal admission, and lifecycle mutation, plus an
idempotent maintenance scan for timely visibility. The policy evaluator alone
holds `task.expire`; it commits one optimistic-concurrency-protected terminal
transition with the profile rule and evaluation time. An operator ends work
manually with cancellation rather than manufacturing expiration.

Absolute age is measured from immutable `created_at`. No-progress age is
measured from `last_progress_at`, initialized to `created_at` and advanced only
by an accepted semantic-progress transition. Absolute age includes paused
wall-clock time so pause cannot park work indefinitely. No-progress elapsed
time excludes every recorded paused interval, making pause safe for deliberate
operator suspension without falsely claiming progress. Completed, cancelled,
and expired tasks are never evaluated again.

Pause accounting is an O(1) materialized value on `governed_tasks`, not a
revision-chain scan on each expiry check. `paused_at_utc` is set atomically on
pause. Resume adds the completed interval to integer
`no_progress_paused_ms` and clears `paused_at_utc`; accepted semantic progress
resets that accumulator when it advances `last_progress_at`. While currently
paused, the open interval is also subtracted at evaluation time. Every update
shares the lifecycle transition transaction, survives restart, and is
rebuildable and integrity-checkable from immutable pause/resume revisions.

### 5. Evidence and assurance

Evidence references must resolve inside the same authorized task/run boundary.
Accepted transitions record one assurance class:

```text
model_proposed
rule_derived
host_observed
operator_verified
independently_verified
```

The class describes the strongest supporting evidence, not semantic truth.
Tool completion may support `host_observed`; only a registered verifier can
produce `independently_verified`. No raw chain-of-thought is accepted or stored.

Task events extend the Black Box vocabulary with versioned payloads such as
`task.started`, `task.transition_proposed`, `task.transition_decided`,
`task.no_change`, `task.guard`, `task.context_disposition`, and
`task.lifecycle_changed`. Existing chain verification remains authoritative.

### 6. Governance implementation

Represent Governance Matrix permissions as closed capabilities evaluated by
AtMem policy, not as trusted caller labels:

```text
task.read
task.propose
task.correct
task.skip_required
task.complete
task.cancel
task.delete
task.profile.register
task.policy.override
task.expire
```

Host agents receive only read/propose capabilities for their exact task scope.
Independent verifiers submit bounded attestations but cannot mutate state.
Operator actions resolve through authenticated local administrative authority;
future remote identities must map to the same capabilities rather than adding
a parallel permission system. Every denied action records a content-minimizing
decision and leaves canonical state unchanged.

### 7. Provenance implementation

Store lineage at the smallest mutable semantic unit. Each field, status,
constraint, dependency, blocker, and lifecycle value points to its source and
evidence, actor, extraction or interpretation method, interpreter identity,
assurance, introducing revision, and optional superseded lineage record. The
revision snapshot contains lineage references instead of duplicating evidence
bodies.

Add a scope-authorized provenance resolver that pivots from task, item, field,
status, transition, or context exposure and returns a human-readable origin and
change chain. Technical IDs and hashes remain available as verification detail.
Deletion removes governed content from lineage rows while retaining only the
minimum receipt digest and count permitted by deletion policy.

### 8. Observability implementation

Create `atmem/task_state/observability.py` as a read-only projection over
canonical task heads, step outcomes, evidence, context preparation/exposure,
and AtBot health. It emits no raw task content in counters or diagnostics.

The projection supplies:

- lifecycle, blocked, stale, and no-progress task counts;
- transition outcomes and reason-code counts;
- guard types, stale-revision conflicts, and fallback use;
- prepared versus exposed task-context counts;
- validation/commit and context-preparation latency distributions;
- last successful progress time and profile age/step threshold breaches;
- task-state/audit-chain integrity and adapter capability health.

CLI JSON and dashboard endpoints call the same projection with exact scope
filtering. Human views follow overview → task detail → evidence. Test fixtures
prove metric parity and absence of task values, secrets, prompts, tool payloads,
and cross-scope aggregates.

### 9. AtBot intelligence boundary

Add task-state proposal types and prompts to the in-repository AtBot package.
AtBot receives only the authorized current snapshot plus bounded authenticated
observation/tool evidence and returns a closed delta, confidence, affected item
IDs, and reasons. It cannot nominate a different task/scope, change profile,
claim stronger assurance, introduce unknown evidence, or commit state.

If AtBot is unavailable, AtMem still accepts explicitly typed host/operator
deltas, applies deterministic status/dependency/completion rules, constructs
current context, and records `no_change` when no safe transition is available.

### 10. Context preparation and caching

Extend existing `control_prepare` output with a separate `task_state` section;
do not concatenate task state into a standing system instruction. The adapter
uses a fixed preamble identifying it as governed execution data and preserves
the exact bytes through the model boundary.

Task context preparation is explicit, never ambient. A task-aware boundary
must supply `task_id` together with the subject, workspace, and agent scope.
Missing identity returns `task_context_selection_required`; an unknown,
terminal, cross-scope, or otherwise ineligible identity returns the same
non-disclosing eligibility disposition `task_context_not_eligible`. Neither
case searches for or falls back to another open task, and neither records an
exposure.

The serializer includes current phase, eligible next items, blockers,
constraints, completion eligibility, and recent no-progress guard. Completed
item content is omitted unless needed to prevent repetition. Cache keys include
authority scope, task ID, revision, profile digest, policy generation,
serializer version, and byte budget. Any transition, lifecycle change, policy
change, profile change, correction, or deletion invalidates affected entries.

Budget reduction removes only complete profile-declared optional fields in a
fixed order and never cuts UTF-8, JSON, items, constraints, or bindings. Goal,
active constraints, blockers, eligible next work, completion eligibility,
scope, revision, and integrity data are mandatory. If those bytes cannot fit,
preparation returns a typed `task_context_budget_exceeded` withholding decision
and records no exposure.

All task content is untrusted governed data regardless of origin. Strings are
schema-validated, bounded, canonically escaped, and provenance-labelled inside
the data envelope. Content can never create envelope members or enter system,
developer, tool, or other instruction positions. Tests prove delimiter and
structural containment; documentation does not claim this guarantees how a
model interprets otherwise valid imperative text.

### 11. Action equivalence and no-progress guards

Adapters canonicalize an action fingerprint from host, tool/action name,
bounded argument digest, target item ID when known, and task revision. Repeating
the same operation for a different item is not equivalent. The profile counts
equivalent completed attempts since the last accepted progress transition and
emits a guard at its configured threshold.

A workflow step is created only for a unique authenticated task-bound host
observation, action/tool request, action/tool terminal result, operator action,
or registered verifier result. Streaming fragments, diagnostic logs, and
idempotent duplicate hook delivery do not create steps. Each unique step is
resolved once to `accepted`, `rejected`, `conflict`, or `no_change`.

AtMem records whether a capable adapter withheld a completion action or merely
displayed a warning. Generic/MCP integrations that cannot prove enforcement
receive detection-only status.

### 12. Adapter integration

Extend `AtMemAdapterIdentity` with `task_id` that remains optional only for
legacy, task-unaware operation and is required for every task-aware method;
absence disables task-state delivery rather than triggering task discovery.
Session/run/turn IDs remain correlation identifiers. Extend
`AtMemTurnLifecycle` with methods for
authenticated observation, task context preparation, action proposal, tool
outcome, completion check, and `no_change`. Pydantic AI and LangGraph wrappers map
their existing model/tool hooks to those methods without changing framework
state.

The OpenClaw adapter adds matching hook payloads and exact task-context
delivery. Its npm package is released only when its bridge contract changes.
Older adapters continue ordinary memory behavior and report task-state
capability unavailable rather than failing installation.

`atmem/contracts/versions.py::capabilities()` is the runtime authority for
negotiation. It advertises `governed_task_state`, `task_state_delivery`,
`task_state_guard_detection`, and `task_state_guard_enforcement`. The public capabilities schema,
adapter response tests, and `docs/capabilities.json` mirror that result; the
documentation file is not itself executable authority.

### 13. CLI and dashboard

Add a top-level task command family using the same manager methods as the UI:

```text
atmem task enable --subject ... --agent ... --workspace ...
atmem task start --subject ... --agent ... --workspace ... --profile general-v1 --goal ...
atmem task list --subject ... --agent ... --workspace ... [--lifecycle ...] [--limit ...] [--cursor ...]
atmem task show TASK_ID
atmem task timeline TASK_ID
atmem task verify TASK_ID
atmem task correct TASK_ID --expected-revision N ... --reason ...
atmem task pause|resume|complete|cancel TASK_ID
atmem task forget TASK_ID --expected-revision N --reason ...
atmem task profile register PROFILE.json --dry-run
atmem task profile list|show|verify ...
atmem task disable ...
```

`show` presents the immutable expiry rule and effective clock state. `timeline`
presents each expiry evaluation that changed lifecycle, including evaluated
time, threshold, reason, prior revision, and evidence. Expiration remains a
policy action rather than a manual `expire` command.

Human output leads with goal, lifecycle, phase, progress counts, blockers, next
eligible work, completion eligibility, and corrective actions. JSON output
uses public contracts. Every subcommand has a runnable example and resolves an
exact visible scope. Collection commands use stable ordering plus cursor/limit
pagination. Human output ends with one `Next:` command when another action is
available. JSON mode writes exactly one contract document to stdout and sends
diagnostics to stderr. Exit `0` means a successful read, accepted action, or
`no_change`; exit `1` means a typed rejected, conflict, unavailable, or
integrity outcome; argparse and input-schema failures exit `2`. Unauthorized
lookups use a non-disclosing result.

Cancellation, required-item skip, provenance correction, policy override,
task deletion, and profile registration present an exact preview containing
scope, task/profile, expected revision, effect, reason, and source. Interactive
CLI requires confirmation; non-interactive use requires `--yes` and never
weakens the other authority inputs. Dashboard confirmation uses the same
preview contract. Neither surface auto-retries a stale mutation: it reloads the
new head, explains changed fields, and requires a fresh explicit submission.

The dashboard follows `docs/dashboard-design-language.md`
and adds no fifth top-level workspace: active tasks and progress live in
**Activity**; blocked items, completion denial, corrections, and profile/lifecycle
actions live in **Decisions** or **Settings** according to whether action is
pending or configurational; timeline, provenance, and transition proof live in
**Evidence**. Each section has one owner, uses progressive disclosure when not
glanceable, reuses the existing icon vocabulary, and maps health to the existing
check/alert states. Technical IDs and digests remain expandable evidence.

Task UI is capability-gated. Disabled installations retain the existing
memory-only dashboard with no empty task panels. Shadow mode is visibly labelled
and never implies agent influence. Unavailable and legacy adapters show one
boundary explanation and at most one safe next action. Selecting a task creates
one persistent task context shared by direct links among Activity, Decisions,
and Evidence: a compact goal/lifecycle/phase header remains stable, while each
workspace owns only its job-specific content and provides a clear return to the
task list. Settings owns profile configuration and a separated task deletion
danger zone.

Every task surface defines empty, loading, degraded, permission-denied,
stale-conflict, integrity-failed, terminal, and content-overflow states. Tabs,
links, dialogs, timelines, confirmations, live updates, and errors use semantic
HTML, labelled controls, visible focus, focus restoration, polite live-region
announcements, keyboard-complete operation, non-color status text, reduced
motion, and layouts tested at narrow widths. The global verdict band remains
the only whole-dashboard health verdict; task summaries cannot introduce a
competing global status.

### 14. Compatibility, migration, and deletion

Schema creation is additive. Existing installs have no task rows and remain
disabled. Upgrade tests start from every public persisted-data version named by
the release workflow and exercise task creation through deletion. Downgrading
to a release unaware of task tables leaves long-term memory readable; rollback
documentation warns that older releases ignore, but do not interpret, task
state.

Subject/task deletion tombstones the task head and removes or verifies absence
of revision content, proposals, step records, caches, and registered derived
artefacts according to retention policy. Minimal deletion receipts may retain
digests and counts under the existing proof boundary.

### 15. Independent implementation and licensing

All contracts, prompts, examples, fixture tasks, diagrams, and benchmarks are
authored for AtMem. Tests use synthetic generic workflows such as processing
approved support tickets or inventory records. Third-party research prompts,
datasets, figures, model weights, and branded algorithm/component names are not
bundled. Dependency licence checks remain part of CI.

## Project Structure

```text
atmem/
  core/
    time.py
  contracts/
    task_state.py
    versions.py
  schemas/v1/
    task-profile.json
    task-start-request.json
    task-state.json
    task-state-proposal.json
    task-transition-decision.json
    task-context-package.json
    capabilities.json
  task_state/
    __init__.py
    models.py
    profiles.py
    policy.py
    service.py
    context.py
    guards.py
    governance.py
    provenance.py
    observability.py
  store/sqlite.py
  maintenance.py
  memory.py
  control/
    manager.py
    evidence.py
    blackbox.py
    assets/app.html
    assets/app.js
    assets/app.css
  adapters/
    base.py
    pydantic_ai.py
    langgraph.py
  cli.py
packages/atbot/src/atbot/
  domain.py
  task_state.py
  prompts.py
integrations/openclaw/
  index.ts
  src/rpc-client.ts
  src/types.ts
  test/hooks.mjs
  test/smoke.mjs
atmem/benchmark/
  data/task-state-v1.json
  runner.py
tests/
  test_task_state_prerequisites.py
  test_task_state_clock.py
  test_task_state_contracts.py
  test_task_state_store.py
  test_task_state_policy.py
  test_task_state_service.py
  test_task_state_walking_skeleton.py
  test_task_state_expiry.py
  test_task_state_context.py
  test_task_state_guards.py
  test_task_state_governance.py
  test_task_state_provenance.py
  test_task_state_observability.py
  test_task_state_atbot.py
  test_task_state_adapters.py
  test_task_state_cli.py
  test_task_state_dashboard.py
  test_task_state_deletion.py
  test_task_state_upgrade.py
  test_task_state_performance.py
docs/
  governed-task-state.md
specs/007-governed-task-state/
  spec.md
  plan.md
  tasks.md
```

No host-specific task contract belongs in AtMem core; the OpenClaw files only
map its hooks and exact-delivery boundary to the host-neutral contracts.

## Test Strategy

1. **Contracts**: closed shapes, bounds, canonical bytes, stable IDs, unknown
   fields, profile digest, delta operations, reason codes, and schema fixtures.
2. **Authority**: exact task scope, lifecycle, authorized-before-AtBot,
   revalidation, unknown evidence, assurance, and no direct intelligence write.
3. **Transitions**: every phase/item edge, dependencies, schema lock,
   completion gates, corrections, `no_change`, and invalid full replacement.
4. **Transactions**: optimistic concurrency, 1,000 replay/concurrent attempts,
   idempotency, one successor per head, interruption, and recovery.
5. **Context**: minimal/stable ordering, budgets, instruction-like data,
   whole-field optional reduction, mandatory-overflow withholding, delimiter
   containment, generation-bound caching, invalidation, one exposure, shadow
   withholding, and stale preparation.
6. **Guards**: repeated-equivalent action, different item/action distinction,
   reset on progress, premature completion, out-of-scope, and detection versus
   host enforcement evidence.
7. **AtBot/fallback**: valid and malicious deltas, unknown IDs/evidence,
   unavailable/malformed/timeout model, deterministic host delta, `no_change`,
   and egress attribution.
8. **Adapters**: OpenClaw, Pydantic AI, LangGraph, and generic lifecycle parity;
   model/tool/error/terminal paths; legacy adapter capability reporting.
9. **Governance**: every Governance Matrix actor/action combination, capability
   derivation, exact scope, administrative overrides, denied-action evidence,
   and unchanged state on denial.
10. **Provenance**: complete task/field/status/transition/delivery lineage,
    supersession, human-readable query, assurance ceilings, deletion
    minimization, and cross-scope denial.
11. **Observability**: deterministic lifecycle/transition/guard/fallback/
    prepared-exposed/latency/integrity fixtures, CLI/dashboard parity, content
    minimization, and scope isolation.
12. **Product**: runnable CLI help journeys, exact scope, stable collection
    pagination, stdout/stderr and exit-code contracts, JSON parity, privileged
    previews/confirmations, stale-conflict recovery, dashboard capability
    gating, selected-task navigation, CSRF, human-readable state, technical
    evidence disclosure, and no database editing.
13. **Deletion and upgrades**: task/subject forget across canonical and derived
    state; migrations from supported releases; downgrade-safe long-term memory;
    backup/restore and OpenClaw restore regressions.
14. **Performance**: 1,000 single-writer local transitions without concurrent
    write contention, cold/warm context preparation, guard evaluation,
    database query plans, and p95 threshold; contended writes remain a separate
    correctness test with no 25 ms target.
15. **Release regression**: full Python matrix, AtBot matrix, framework latest,
    OpenClaw npm checks, clean wheels, optional dependencies, licences, and
    published-artifact upgrade drills.
16. **Expiry**: injectable-clock absolute/no-progress thresholds, exact boundary,
    lazy and maintenance evaluation, restart, race/idempotency, evidence, and
    zero post-expiry delivery.
17. **Capabilities**: runtime/schema/documentation equality and current/legacy
    adapter negotiation for delivery, guard detection, and guard enforcement.
18. **Task UX**: disabled/shadow/unavailable/legacy/empty/loading/degraded/
    denied/conflict/integrity/terminal fixtures; memory-only dashboard
    regression; keyboard/focus/semantic-label/live-region/reduced-motion/
    narrow-screen/no-color/content-overflow checks; and runnable first-use CLI
    navigation from help alone.

## Rollout and Rollback

- Ship behind an explicit per-scope task-state enablement. Installation and
  upgrade create no task and inject no task state.
- Begin supported hosts in shadow evaluation, where proposals and expected
  guards are visible but cannot influence model context or execution.
- Active enablement requires adapter capability checks for exact task-context
  delivery; detection-only adapters remain clearly labelled.
- Rollback disables task-state influence while preserving append-only history
  for inspection and export. Existing long-term memory behavior continues.
- If AtBot fails, remain active only for deterministic validation/current-state
  delivery; never infer progress.
- Release notes distinguish task-state detection, context delivery, and host
  enforcement capabilities for every advertised adapter.

---

# Amendment A Plan — Host-Driven Task Binding and Proposal

**Date**: 2026-09-05 | **Spec**: Amendment A in `spec.md` | **Adds**: Design
Decisions 16–21, structure and test-strategy deltas.

**Revision 5** (2026-09-05): resolves fourth-review findings I1, U1, C1.
Decisions 17 and 19 are extended in place.

**Revision 4** (2026-09-05): resolves third-review findings A1–A5. Decisions 17,
19, and 20 are extended in place.

**Revision 3** (2026-09-05): resolves second-review findings C1 (critical), I1,
C2, I2, C3, U1, R1, I3, T1. Decisions 16, 17, 19, and 20 are corrected in place;
Decision 21 is new. Phase 12 is renumbered into execution order.

**Revision 2** (2026-09-05): resolves first-review findings I1, U1, C1, S1, C2,
U2, A1, T1, R1. Decisions 16 and 17 are corrected in place; Decisions 18–20 are
new.

## Summary

Close the two gaps that make Governed Task State unreachable from OpenClaw:
task identity never resolves at the hook boundary, and the adapter boundary has
no write path. Add an operator-registered session-to-task binding that AtMem
looks up (never infers), and a host-boundary proposal operation constrained to
the host-agent row of the existing Governance Matrix. Both reuse the committed
policy, concurrency, evidence, and provenance path; neither adds a new authority.

## Technical Context Delta

- **Storage**: one new table in Spec 007's reserved bootstrap block. `0070`–
  `0077` are consumed; `0078` takes the binding table and `0079` is the only
  identifier left in the reserved range. Any further Spec 007 schema work must
  either fit `0079` or request identifiers through the Spec 010 registry —
  budget this before implementation, not during.
- **Dependencies**: unchanged. No new mandatory SDK, Python or TypeScript.
- **Surfaces**: three new MCP tools (`control_observe_task_step`,
  `control_propose_task_delta`, `control_request_task_lifecycle`), one new
  agent-facing model tool registered by the bridge, one new CLI subcommand
  family, and one owner-gated in-host command group. No new network listener and
  no change to the loopback-only dashboard posture.
- **Security**: bindings are privileged operator state. A host agent consuming a
  binding gains no capability it did not already hold for a task named
  explicitly, so the binding is an addressing mechanism, not an authorization.

### 16. Session-to-task binding

Persist bindings in `governed_task_session_bindings` (migration `0078`). The
unique key is exactly
`(subject_id, agent_id, workspace_id, host_type, session_key, session_epoch)`.
`AuthorityScope` supplies three fields, not four; `host_type` namespaces the
session key so an OpenClaw key and a LangGraph key cannot collide; and
`session_epoch` is the FR-052 generation. `task_id` is the target and is
deliberately outside the key, which is what makes bindings many-to-one and makes
retargeting impossible to express as an update. A partial uniqueness constraint
admits at most one active row per key while retaining revoked rows for history.
Columns carry task ID, registering actor, reason, source, registration and
revocation times, and evidence ID. Registration validates that the target task
is currently eligible; a task that later becomes terminal does not rewrite the
binding, it makes it unresolvable at read time.

Resolution lives in `atmem/task_state/binding.py` and is called only from the
existing `ControlPlaneManager.prepare_task_context` path, so every eligibility,
expiry, budget, escaping, and exposure rule already proven for explicit
identity applies unchanged. The resolver returns exactly one of: a task ID, or
a withholding reason. It never returns a candidate list, so there is no code
path in which selection could be introduced later without deleting this
contract.

Resolution order is fixed and total — explicit identity, then active binding,
then withhold — with disagreement between the first two withholding under
`task_binding_conflict` rather than preferring either. Preferring the explicit
identity would silently mask a misconfigured binding; preferring the binding
would let stale operator state override a host that knows better. Withholding
is the only outcome that surfaces the contradiction to an operator.

Session keys are correlation identifiers and are not secrets; per FR-024 they
must not become authorization. The binding is authorized by the scope it was
registered under, and resolution revalidates that scope on every turn.

Scope revalidation alone does **not** solve key recycling: a new conversation in
the same subject/agent/workspace can present a reused key and would otherwise
inherit a stale binding. FR-052 closes this with a bound session generation.

Reset detection must be positive, not inferred from elapsed time. A lifetime
cannot detect a reset that happens inside it — the reset that matters most is
the one that happens a minute after binding — so a TTL is supplemental expiry
protection and never a substitute. Session binding therefore *requires* an
opaque host `session_epoch` that rotates on reset, which is part of the
uniqueness key, so a new incarnation simply does not match any active row. A
host that cannot supply a generation or a reliable session start reports session
binding unavailable in the capability response and is not bound at all.

OpenClaw can supply this: its plugin surface exposes `session_start`,
`before_reset`, and `session_end`, and `ctx.sessionId` distinguishes
incarnations. The bridge maps that identity into `session_epoch` at registration
and presents it on every later lookup, so binding and resolution cannot disagree
about which conversation they mean.

Both stale paths withhold under `task_binding_stale_session` and require
explicit re-confirmation; neither recovers automatically.

### 17. Host-boundary proposal

Add `control_propose_task_delta` and `control_request_task_lifecycle` to
`atmem/control/server.py`, and the manager methods behind them to
`atmem/control/manager.py`. Both route into the existing `TaskStateService`
with `ActorRole.AGENT`, alongside — not around — the operator paths used by
`atmem task correct` and `change_task_lifecycle`.

Session identity and actor role are different kinds of claim and are handled
differently. `host_type`, `session_key`, and `session_epoch` are **addressing**:
the host states which conversation it is, all three are required on every
host-boundary request, and AtMem resolves them through FR-043 and checks the
result. A partial identity is malformed, not a licence to resolve loosely.
Actor role is **authority** and is derived, never received. It comes from the
authenticated transport and the registered adapter identity; a submission carrying an actor-role,
capability, or authority field is rejected as malformed rather than honored or
quietly dropped, because silently ignoring it leaves a caller believing it was
accepted. The capability ceiling is likewise derived in
`atmem/task_state/governance.py` from the Governance Matrix, not asserted at the
tool boundary. Operator-only actions are
refused before delta content is evaluated, so a malformed privileged proposal
and a well-formed one produce the same capability refusal and leak nothing
about the task. This mirrors the existing derivation approach and keeps a
single enforcement site.

Idempotency keys are supplied by the adapter and scoped to the task, so a
retried hook, a duplicated tool result, and a replayed turn collapse to one
decision under the SC-002 guarantees already implemented.

Scope is not enough to decide *which* task a host may write to. One authorized
scope routinely holds several concurrent tasks — the spec assumes exactly that —
so a submission naming a sibling task passes every scope and capability check
while belonging to a different conversation. FR-054 closes this by resolving
`(host_type, session_key, session_epoch)` through FR-043 on every submission and
requiring the submitted `task_id` to equal the resolved one. The submitted
identifier is then a redundant assertion to be checked, never the authority;
where resolution yields nothing the submission is refused rather than trusted.

This puts read and write on the same resolution path, which is the property
worth having: a host can only write to the task it is currently allowed to read.
The mismatch refusal is non-disclosing for the same reason every other lookup
is — otherwise naming tasks at random becomes an existence oracle.

Shadow and disabled are different code paths and must not share one. A disabled
scope refuses at the boundary before identity resolution or content evaluation,
matching what `atmem task` already does today and keeping the non-disclosure
property intact. Shadow evaluates fully and records the decision it would have
made, committing nothing — that is what makes shadow a rehearsal for this path
rather than a silent no-op. Collapsing the two would either leak task existence
from a disabled scope or make shadow untestable.

The bridge changes stay inside `integrations/openclaw/`: resolve identity via
the manager rather than reading `ctx.taskId` alone, and submit **observations**
— not deltas — from the existing `after_tool_call` and `agent_end` hooks where
tool outcomes are already observed for Black Box evidence. See Decision 18 for
why the bridge never produces a delta itself. No OpenClaw change is required; if
OpenClaw later adds task identity to `PluginHookMessageContext`, it lands as
the first resolution step with no further work.

### 18. Where a delta comes from

The bridge observes raw tool outcomes; the policy engine consumes typed deltas.
Nothing in Revision 1 said who converts one into the other, which would have
left each adapter to invent it — the exact failure FR-007 exists to prevent.

Two entry points, and deliberately no third:

**(a) Observation → AtBot → revalidate → commit.** The adapter submits one
bounded authenticated workflow step. AtMem authorizes it, routes it through the
companion path already built by T035–T036, and revalidates the returned delta
against the current head before commit. This reuses the whole existing
intelligence boundary rather than growing a second one, and it keeps AtBot in
its matrix row: proposes, never commits. With AtBot unavailable the observation
records a deterministic `no_change` — FR-019 already requires exactly this, so
the fallback is not new behavior.

**(b) Explicit typed delta from the agent.** A tool through which the model
states progress directly, already in delta form. No interpretation step, so no
interpreter to trust.

A manager method and an MCP operation are invisible to the model. Path (b) is
only real if the bridge registers it through `api.registerTool`, the same
mechanism that already publishes `memory_search` and `memory_get`. That means
naming the tool, defining what the model reads back for each of `accepted`,
`rejected`, `conflict`, and `no_change` — a rejection the model cannot interpret
is a rejection it will retry blindly — and testing it at the tool boundary.
Unregistered, path (b) does not exist and must not be advertised.

The adapter itself never synthesizes a delta. A deterministic tool-result
mapping table was the third option and is rejected: it would put execution
semantics in the bridge, where it could not be governed by a profile, could not
be versioned with the policy, and would drift per host.

Idempotency keys derive from the observed step's stable host identifiers —
`runId`, tool-call id, step index — never from payload content, wall-clock, or
randomness. Content-derived keys would collapse two legitimately identical
actions on different items; random keys would defeat replay collapse entirely.
Payloads are minimized to profile-declared fields before leaving the host.

### 19. In-host operator binding

US6 promises the operator never leaves OpenClaw, and Revision 1 shipped only
CLI and web endpoints — which also required an opaque `sessionKey` the operator
has no way to obtain. Add an owner-gated in-host surface for bind, unbind, and
status, scoped to the caller's own conversation so the session key is resolved
internally and never displayed.

The owner gate is `ctx.senderIsOwner`, which the bridge already receives and
already uses to refuse non-owner turns. Reusing it keeps one owner definition
rather than inventing a second. A non-owner call is refused without disclosing
whether a binding exists, matching the non-disclosure rule everywhere else.

This surface is a convenience over the operator row, not an addition to it: the
same authority, reason, source, evidence, and confirmation requirements apply,
and it can express nothing `atmem task bind` cannot.

Because OpenClaw can supply a reset signal and another adapter may not, session
binding availability is per adapter, not global. The capabilities response
already carries `governed_task_enforcing_adapters` as an adapter-keyed list, so
this follows an established pattern rather than inventing one: add
`governed_task_session_binding_adapters`,
`governed_task_host_proposal_adapters`, and
`governed_task_agent_delta_tool_adapters`, keep any global flag meaning only
"the runtime implements this", and have each adapter response derive its own
availability from the keyed data. All three vary by host — an adapter with no
authenticated session-bound request path cannot host-propose at all — so a
single boolean would have to lie about one of the two adapters in each case.

### 20. Proving the premise without a global install

Revision 1's premise gate proposed asserting from Python that an installed
OpenClaw never populates `ctx.taskId`. That is not provable: a TypeScript
declaration is not a runtime guarantee, and reading a globally installed
OpenClaw makes CI depend on whichever version the machine happens to have.

Move the check to the npm suite against the pinned OpenClaw dependency, with
versioned hook fixtures recording the context shape per tested version. The
bridge's `peerDependencies` range is open-ended (`openclaw >=2026.7.1-2`), so
"each supported version" is not testable as written. Define instead a finite
matrix of exactly three: the declared minimum, the version in the lockfile, and
the latest compatible version CI resolves. All three must be installed and
tested in CI — a fixture that is never run against its version is documentation,
not a check — and the resolved version of the moving "latest compatible" entry
must be recorded in the run so a regression can be attributed. Anything outside
those three is unverified and must be described that way. If a
future version does populate task identity, the fixture diff is the signal to
re-scope the amendment — FR-043's first resolution step already consumes native
identity — rather than a permanent assertion that must never change. The Python
side keeps only what it can actually prove: that no task write tool is
registered, and which migration identifiers remain free.

### 21. Truthful exposure when a task turns terminal mid-call

Revision 2 said a task expiring between preparation and exposure meant exposure
"MUST NOT be confirmed" and the package was "discarded." That is wrong, and in
OpenClaw it is provably wrong: task exposure is confirmed in the `agent_end`
hook (`integrations/openclaw/index.ts`), which runs *after* the turn. By the
time confirmation happens the bytes have already reached the model. Refusing to
record the exposure would assert that a delivery did not occur when it did —
manufacturing convenient history rather than recording evidence, which is the
one thing the evidence plane exists to prevent.

FR-053 inverts the rule: preparation authorizes exactly one model call, and the
evidence records what happened on that call. If the adapter can prove the bytes
reached the boundary, exposure is confirmed truthfully and the expiry is
recorded as its own later event linked to that delivery. If they demonstrably
did not, or the adapter cannot prove delivery, preparation is recorded with no
exposure claim — which is the existing rule for detection-only adapters and is
unchanged.

The safety property people actually want is not "no exposure record." It is
"the task stops influencing future calls," and that is delivered by
re-resolving identity on every subsequent call and withholding. Nothing is
gained by lying about the call that already happened, and the audit trail is
strictly worse for it.

## Project Structure Delta

```text
atmem/
  contracts/task_state.py          # binding + host-boundary contracts
  schemas/v1/
    task-session-binding.json      # new
    task-profile.json              # + binding lifetime, reset-signal requirement
    host-task-proposal-request.json    # new (FR-051)
    host-task-observation-request.json # new (FR-051)
    host-task-lifecycle-request.json   # new (FR-051)
    capabilities.json              # + binding/host-proposal flags
  task_state/
    binding.py                     # new: registration, revocation, resolution
    profiles.py                    # + binding lifetime defaults for general-v1
    governance.py                  # + host-agent ceiling derivation
  store/sqlite.py                  # + migration 0078
  control/
    manager.py                     # + bind/unbind/list, propose, lifecycle request
    server.py                      # + 3 MCP tools
    web.py                         # + binding endpoints
  cli.py                           # + atmem task bind | unbind | bindings
packages/atbot/src/atbot/
  task_state.py                    # reused unchanged by the observation path
integrations/openclaw/
  index.ts                         # resolve identity; submit observations
  src/commands.ts                  # new: owner-gated bind | unbind | status
  src/task-tools.ts                # new: registered agent-facing delta tool
  test/fixtures/hook-context/      # new: min | lockfile | latest-compatible
  src/rpc-client.ts
  src/types.ts
tests/
  test_task_state_binding.py       # new
  test_task_state_host_proposal.py # new
  test_task_state_observation.py   # new (FR-049)
```

## Test Strategy Delta

- **Resolution matrix**: exhaustive fixture over {explicit, binding, both-agree,
  both-disagree, neither} × {open, paused, terminal, cross-scope, unknown},
  asserting disposition, reason code, and byte count — zero bytes for every
  non-delivering cell (SC-019).
- **Concurrency**: reuse the SC-002 harness against the host-boundary path;
  1,000 attempts, one accepted successor per head, no duplicate for a repeated
  idempotency key (SC-020).
- **Capability**: extend `tests/fixtures/task_state/governance-v1.json` with the
  host-agent row so operator-only actions are proven refused at the host
  boundary with the head unchanged (SC-021).
- **End-to-end**: an OpenClaw hooks test that binds, delivers with no
  `ctx.taskId`, confirms exposure once, advances by proposal, is denied
  premature completion, and withholds after revocation, asserting the
  prepared/exposed/withheld counter sequence (SC-022).
- **Regression**: with no bindings registered, every existing memory-only and
  task-unaware test must remain green and the bridge must behave identically to
  today (FR-047).
- **Observation**: every fixture runs twice — AtBot available and AtBot plus
  network disabled — asserting the specified decision in the first and a
  deterministic `no_change` in the second, with derived idempotency keys
  collapsing retries and payloads free of prompts, full tool results, secrets,
  and chain-of-thought (SC-024).
- **Session recycling**: one case per reset path a supported host can produce —
  changed epoch, host-reported session start after registration, elapsed
  lifetime — each asserting zero bytes under `task_binding_stale_session` and no
  inherited task (SC-025).
- **In-host surface**: owner and non-owner calls to bind, unbind, and status,
  asserting no session key is ever returned and non-owner refusal discloses
  nothing (SC-026).
- **Contract**: published-schema validation for all three host-boundary request
  types, plus rejection-as-malformed for any submission carrying a
  caller-supplied actor-role, capability, or authority field (SC-027).
- **Disabled versus shadow**: the same submission against a disabled scope and a
  shadow scope, asserting immediate refusal with minimal evidence in the first
  and full evaluation without commit in the second (FR-046).
- **Delivery race**: a task turning terminal after preparation, tested both
  ways — bytes reached the boundary (exposure confirmed, expiry recorded as a
  separate linked event) and bytes did not (preparation only, no exposure
  claim), with every subsequent call withholding (SC-028).
- **Reset rotation**: `session_epoch` rotation asserted across `before_reset`,
  `session_start`, and the next `before_prompt_build`, plus a reset occurring
  inside a declared lifetime still withholding (SC-029).
- **Agent tool boundary**: the registered typed-delta tool invoked by the model
  for each of `accepted`, `rejected`, `conflict`, and `no_change`, asserting the
  result the model reads back is defined and interpretable (SC-030).
- **Profile compatibility**: existing persisted profiles without a binding
  lifetime load unchanged, `general-v1` gains its default, and the published
  `task-profile.json` accepts both shapes (FR-052; SC-008).
- **Wrong-session submission**: for each of observation, proposal, and lifecycle
  request, two open tasks in one scope bound to two sessions, with each session
  naming the other's task — refused before content evaluation, non-disclosing,
  both heads unchanged; plus a submission whose session resolves to nothing
  (FR-054; SC-031).
- **Mixed-adapter capability**: one adapter supplying a reset signal and one not,
  asserting each adapter response derives its own availability from the
  adapter-keyed data rather than a global flag (FR-048; SC-023).

## Rollout and Rollback Delta

- Bindings ship revoked-by-default: upgrading creates none, so behavior is
  byte-identical to the current release until an operator binds a session.
- Host proposals are gated by the same per-scope enablement as the rest of the
  feature and are evaluated without commit in shadow mode.
- Rollback is revocation: revoking every binding returns delivery to the
  current withholding behavior while retaining binding history for inspection.
- Release notes for the amendment ship as `docs/releases/v<VERSION>.md`, the
  artefact `AGENTS.md` requires before tagging — the repository has no
  `CHANGELOG.md` and one must not be invented for this. The note must carry the
  user-visible change, exact install and upgrade commands, migration and opt-in
  behavior, compatibility, and honest limitations, with a matching section in
  `docs/current-status.md`, aligned across the three versioned artefacts
  released together — the `atmem` distribution, the `atbot`
  distribution, and the OpenClaw bridge `package.json`. The entry must state
  that guard enforcement is still unavailable: this amendment makes the feature
  reachable, not blocking. T084 owns that preparation and no release proceeds
  without it.
