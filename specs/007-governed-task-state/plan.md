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
  1,000 operations, excluding model/tool/verifier execution.
- **Security**: fail-closed four-axis task scope, optimistic concurrency,
  evidence validation, no direct AtBot mutation, explicit activation, minimal
  context, exact exposure proof, and verifiable deletion.
- **Scale for this feature**: multiple concurrent tasks per persistent agent;
  production multi-tenant service scaling remains Spec 013.
- **Dependencies on roadmap**: Spec 005 supplies semantic health and Spec 006
  supplies the generalized typed extraction/lifecycle vocabulary. Spec 007 may
  define its contracts now but implementation should land after those
  prerequisites or explicitly absorb any still-missing shared primitives.

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

Before supported model boundary in active mode
  → resolve exact open task and current head
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

### 2. Canonical state and persistence

Add SQLite tables through the existing idempotent schema initializer:

- `governed_task_profiles`: versioned profile definition and digest;
- `governed_tasks`: stable scope/lifecycle identity and current head pointer;
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
required assurance, completion predicates, and no-progress thresholds. They are
versioned and digest-bound to each task. Registration validates a closed schema
and is an administrative action; tasks never mutate their profile. The
administrative service and `atmem task profile register|list|show|verify`
commands support dry-run validation, immutable version conflict detection, and
tamper-evident registration without enabling the profile for any scope.

The policy engine derives `ready` only when dependencies and constraints permit
it, rejects completed-to-running regressions unless an operator correction rule
allows them, and denies task completion until every required item is completed
or validly skipped and verification gates pass.

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

The serializer includes current phase, eligible next items, blockers,
constraints, completion eligibility, and recent no-progress guard. Completed
item content is omitted unless needed to prevent repetition. Cache keys include
authority scope, task ID, revision, profile digest, policy generation,
serializer version, and byte budget. Any transition, lifecycle change, policy
change, profile change, correction, or deletion invalidates affected entries.

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

Extend `AtMemAdapterIdentity` with optional `task_id`; session/run/turn IDs
remain correlation identifiers. Extend `AtMemTurnLifecycle` with methods for
authenticated observation, task context preparation, action proposal, tool
outcome, completion check, and `no_change`. Pydantic AI and LangGraph wrappers map
their existing model/tool hooks to those methods without changing framework
state.

The OpenClaw adapter adds matching hook payloads and exact task-context
delivery. Its npm package is released only when its bridge contract changes.
Older adapters continue ordinary memory behavior and report task-state
capability unavailable rather than failing installation.

### 13. CLI and dashboard

Add a top-level task command family using the same manager methods as the UI:

```text
atmem task enable --subject ... --agent ... --workspace ...
atmem task start --profile general-v1 --goal ...
atmem task list
atmem task show TASK_ID
atmem task timeline TASK_ID
atmem task verify TASK_ID
atmem task correct TASK_ID --expected-revision N ... --reason ...
atmem task pause|resume|complete|cancel TASK_ID
atmem task profile register PROFILE.json --dry-run
atmem task profile list|show|verify ...
atmem task disable ...
```

Human output leads with goal, lifecycle, phase, progress counts, blockers, next
eligible work, completion eligibility, and corrective actions. JSON output
uses public contracts. Dashboard adds an **Active tasks** view and task detail
timeline; technical IDs/digests remain in expandable evidence.

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
  contracts/
    task_state.py
  schemas/v1/
    task-profile.json
    task-start-request.json
    task-state.json
    task-state-proposal.json
    task-transition-decision.json
    task-context-package.json
  task_state/
    __init__.py
    models.py
    profiles.py
    policy.py
    service.py
    context.py
    guards.py
    provenance.py
    observability.py
  store/sqlite.py
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
tests/
  test_task_state_contracts.py
  test_task_state_store.py
  test_task_state_policy.py
  test_task_state_service.py
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
   generation-bound caching, invalidation, one exposure, shadow withholding,
   and stale preparation.
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
12. **Product**: CLI help/JSON parity, dashboard actions, CSRF, human-readable
   state, correction confirmation, technical evidence disclosure, and no
   database editing.
13. **Deletion and upgrades**: task/subject forget across canonical and derived
    state; migrations from supported releases; downgrade-safe long-term memory;
    backup/restore and OpenClaw restore regressions.
14. **Performance**: 1,000 local transitions, cold/warm context preparation,
    guard evaluation, database query plans, and p95 threshold.
15. **Release regression**: full Python matrix, AtBot matrix, framework latest,
    OpenClaw npm checks, clean wheels, optional dependencies, licences, and
    published-artifact upgrade drills.

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
