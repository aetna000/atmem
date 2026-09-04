# Feature Specification: Governed Task State

**Feature directory**: `specs/007-governed-task-state`  
**Created**: 2026-09-04  
**Status**: Draft  
**Input**: Add a governed, continually maintained execution state that gives
agents a structured checklist of goals, phases, actionable data units, current
status, constraints, dependencies, and verified progress without weakening
AtMem's authority, provenance, privacy, host neutrality, or safe fallback.

## Overview

AtMem currently governs durable memory: it captures authenticated sources,
admits typed memory proposals, authorizes retrieval, constructs byte-stable
context, records exposure, and preserves provenance. Long-running agents also
need a different kind of memory: a current execution state that answers what
the task is, which work is ready, completed, blocked, or skipped, what
constraints still apply, and whether the latest action made progress.

Governed Task State adds that capability as a separate AtMem authority plane.
It does not turn temporary workflow progress into durable personal memory and
does not replace LangGraph checkpoints, Pydantic AI dependencies, OpenClaw
sessions, or another host's workflow state. AtBot may interpret observations
and propose state deltas. AtMem alone validates scope, transition legality,
evidence, concurrency, lifecycle, and final context delivery before committing
a revision or influencing an agent.

The product name for this feature is **Governed Task State**. Its contracts,
documentation, and UI must use independently designed terminology and must not
copy third-party prompts, datasets, diagrams, model artefacts, or branded
research component names.

## User Scenarios and Acceptance

### User Story 1 — Maintain a structured checklist and retire stale tasks (P1)

As an agent operator, I can start an explicitly enabled governed task whose
current state tracks its goal, phase, constraints, dependencies, actionable
items, and progress so the agent does not have to reconstruct remaining work
from conversation history.

**Why this priority**: A durable, structured current state is the minimum
valuable capability and the foundation for every transition, guard, and UI.

**Independent test**: Start a local task with three items, advance one item,
block another, and verify that a fresh process reads the same current revision
with one completed, one blocked, and one remaining item. Start a second task
under an injectable clock and verify that its immutable profile expiry rule
produces exactly one terminal `expired` transition and no later context.

**Acceptance scenarios**:

1. Given an authorized subject, agent, workspace, and task profile, when a task
   starts, then AtMem creates revision 1 with a stable task ID, goal, phase,
   constraints, items, scope, and evidence binding.
2. Given several task items, when accepted transitions occur, then each item
   retains a stable identity and one current status from `pending`, `ready`,
   `running`, `blocked`, `completed`, `skipped`, or `failed`.
3. Given an unchanged observation, when a workflow step is recorded, then
   AtMem records an explicit `no_change` result without creating a semantically
   different state revision.
4. Given a task whose immutable profile expiry threshold is reached, when the
   task is read, prepared, updated, or evaluated by maintenance, then AtMem
   records exactly one evidence-linked `expired` terminal transition and never
   returns that task as active context.

---

### User Story 2 — Admit only valid, evidence-linked transitions (P1)

As a memory custodian, I can allow AtBot or a host adapter to propose task-state
changes while AtMem remains the sole authority that accepts, rejects, and
commits them.

**Why this priority**: Unchecked model-written status would turn hallucination
into execution authority and contradict AtMem's core product guarantee.

**Independent test**: Submit valid, stale, cross-scope, unsupported,
out-of-order, and duplicate deltas against one task and verify that only the
valid delta advances the head revision exactly once.

**Acceptance scenarios**:

1. Given eligible current state and an authenticated observation or tool
   outcome, when AtBot proposes a typed delta, then AtMem validates the exact
   base revision, task scope, transition rules, evidence references, and
   idempotency key before committing it atomically.
2. Given a proposal that invents an item, changes a locked schema, widens
   scope, cites unknown evidence, or uses a stale revision, when submitted,
   then AtMem rejects it without changing current state.
3. Given a completion proposal based only on a host-reported tool result, when
   accepted by policy, then the item records that limited assurance and AtMem
   does not claim an independently verified real-world outcome.
4. Given concurrent proposals for the same base revision, when both arrive,
   then at most one advances state and the other receives a deterministic
   conflict result.

---

### User Story 3 — Deliver current state and guard task execution (P1)

As an agent using AtMem in active mode, I receive a bounded, byte-stable view
of the current authorized task state before model execution, including clear
signals for remaining work, lack of progress, and whether completion is
currently allowed.

**Why this priority**: Structured state creates value only when it reliably
informs the next action without becoming an instruction-injection channel.

**Independent test**: Run a multi-item task through a supported deterministic
adapter, repeat an already completed action, attempt premature completion, and
verify exact state delivery, a no-progress warning, and a denied completion
decision until all required items satisfy the task profile.

**Acceptance scenarios**:

1. Given active mode and an open task, when the adapter reaches the model
   boundary, then AtMem revalidates scope and revision and delivers the exact
   current task-state envelope once as governed data.
2. Given shadow mode or a task for another scope, when a model call occurs,
   then task state is not injected and no exposure confirmation is created.
3. Given repeated equivalent actions without an accepted progress transition,
   when the configured threshold is reached, then AtMem emits an explainable
   no-progress guard signal bound to the repeated actions and current revision.
4. Given required items that are not completed or validly skipped, when the
   agent proposes task completion, then AtMem returns a completion-not-allowed
   decision listing the blocking item IDs without executing a host action.
5. Given unchanged state and policy, when context is prepared repeatedly, then
   the task-state bytes and digest are identical and cache entries remain bound
   to scope, task ID, revision, profile, and policy generation.
6. Given authorized task state that exceeds the configured byte budget, when
   context is prepared, then AtMem removes only profile-declared optional whole
   fields in deterministic order and otherwise withholds the complete package
   with `task_context_budget_exceeded`; it never truncates UTF-8, JSON, a field,
   an item, a constraint, or evidence binding.
7. Given task content containing imperative text, role-like delimiters, or
   instruction-shaped strings, when context is prepared, then the content is
   canonically escaped and provenance-labelled as untrusted governed data and
   is never promoted into a system, developer, tool, or other instruction
   channel.
8. Given no task ID (including when multiple tasks are open), an unknown task
   ID, or a terminal task ID, when a task-aware model call is prepared, then
   AtMem never guesses or selects a task implicitly; it withholds task state
   with a stable non-disclosing reason and records preparation without exposure.

---

### User Story 4 — Inspect and correct task progress (P2)

As an operator, I can understand and control active task state using clear CLI
and dashboard views without reading hashes or editing SQLite.

**Why this priority**: Model-proposed state requires human visibility and a
safe correction path, but the authority contracts can operate before the full
product view is complete.

**Independent test**: Inspect a task, review its timeline, correct one blocked
item with a reason, pause and resume it, then complete or cancel it and verify that each
operation appears as a distinct authorized revision or lifecycle event.

**Acceptance scenarios**:

1. Given a task with mixed item statuses, when viewed, then CLI and dashboard
   show the human-readable goal, current phase, counts, blockers, constraints,
   last progress, and next eligible items before technical identifiers.
2. Given an authorized operator correction, when it is submitted with a
   reason, then AtMem creates a new evidence-linked revision and preserves the
   prior revision.
3. Given a paused or terminal task, when an agent requests state, then the
   lifecycle and permitted actions are explicit; a completed, cancelled, or
   expired task cannot be silently resumed or mutated.
4. Given a rejected proposal, when inspected, then the operator sees the
   proposed change, reason codes, source, actor, model or rule identity, and
   affected item without secret or raw chain-of-thought exposure.
5. Given task state is disabled, in shadow mode, or unavailable for the current
   adapter, when the operator opens the dashboard or runs a task command, then
   the product states the effective mode and capability boundary, shows at most
   one safe next action, and does not render empty active-task controls or imply
   that task context is influencing an agent.
6. Given an operator selects a task and moves between Activity, Decisions, and
   Evidence, when each view opens, then the same selected task and compact
   goal/lifecycle/phase summary remain visible, direct links preserve that
   selection, and a clear return path leads to the task list. Profile settings
   remain in Settings and do not duplicate task detail.
7. Given an operator attempts cancellation, required-item skipping, provenance
   correction, policy override, task deletion, or profile registration, when
   using CLI or dashboard, then the product previews the exact scope, task,
   expected revision, effect, and reason before confirmation. A stale-revision
   conflict displays what changed and requires an explicit refreshed request;
   the product never silently retries a mutation.
8. Given a human or automation invokes a task CLI command, when it succeeds,
   performs `no_change`, is rejected, conflicts, or is invalid, then human and
   JSON modes report the same outcome and reason code, follow documented
   stdout/stderr and exit-code rules, and human mode prints one actionable next
   command when further action is possible.
9. Given empty, loading, degraded, permission-denied, integrity-failed, narrow
   screen, keyboard-only, reduced-motion, or assistive-technology use, when a
   task surface is rendered, then status and permitted actions remain
   understandable without color, hover, animation, hashes, or pointer input.

---

### User Story 5 — Work across hosts and degraded intelligence (P2)

As an integrator, I can use the same governed task-state contracts from
OpenClaw, Pydantic AI, LangGraph, or a conforming generic adapter, and the task
remains safe when AtBot or optional semantic services are unavailable.

**Why this priority**: Host neutrality and local fallback are existing AtMem
guarantees that the new execution-state plane must preserve.

**Independent test**: Replay the same typed task sequence through each
supported adapter and with AtBot disabled; verify equivalent committed state,
scope isolation, delivery disposition, and evidence semantics.

**Acceptance scenarios**:

1. Given equivalent authenticated events from supported hosts, when processed,
   then they use the same versioned task contracts and transition policy.
2. Given AtBot is unavailable, when the host supplies a valid typed delta or no
   state change is inferable, then AtMem validates that delta deterministically
   or records `no_change`; it never fabricates progress.
3. Given an adapter that cannot prove exact model-boundary delivery, when task
   state is requested, then its documented capability is limited and AtMem
   does not claim exposure.
4. Given multiple agents and tasks in one workspace, when state is queried or
   proposed, then every subject, workspace, agent, and task boundary is
   enforced before content reaches AtBot, and task-aware delivery requires the
   exact task ID rather than choosing among open tasks.
5. Given an older or task-unaware adapter, when capabilities are negotiated,
   then the authoritative runtime capability response reports task-state
   delivery, guard detection, and guard enforcement as unavailable rather than
   relying on documentation claims.

## Prerequisite Boundary

Governed Task State depends only on existing AtMem primitives: `AuthorityScope`,
canonical JSON and digest helpers, SQLite transactions and additive migration,
control preparation and exposure evidence, host-neutral adapter lifecycle
identity, and the authorized AtBot companion boundary. Implementation MUST
verify these concrete primitives before feature work begins.

Specs 005 (Semantic Setup and Health) and 006 (Memory Extraction and Updating)
are not implementation prerequisites for this feature. Task-state-specific
profiles, proposals, transition decisions, provenance, and fallback are
defined here. Their generalized semantic-health or extraction contracts may
be adopted only through an explicit compatibility change; their absence must
not block or silently alter this feature.

## Governance Matrix

All permissions are evaluated against the exact subject, workspace, agent, and
task scope before content or mutations are exposed. A role describes a trusted
capability, not merely an actor-supplied string.

| Actor or component | Read eligible state | Propose delta | Commit state | Correct/override | Register profile | Change lifecycle | Deliver context | Delete state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AtMem authority | Yes | Rules only | Yes | Applies authorized requests | Validates and stores | Validates and stores | Constructs and authorizes | Applies authorized deletion |
| Scoped AtMem policy evaluator | No | No | No | No | No | Expiry only, per immutable profile rule | No | No |
| AtBot intelligence | Authorized input only | Yes | No | No | No | No | No | No |
| Host agent/framework | Own authorized task only | Yes | No | No | No | Requests only | Injects exact AtMem package | No |
| Authenticated operator | Authorized scope | Yes | No | Requests with reason and expected revision | Requests with administrative permission | Requests with permission | No | Requests with permission |
| Registered independent verifier | Minimum bound claim only | Attestation only | No | No | No | No | No | No |
| Auditor/observer | Authorized redacted view | No | No | No | No | No | No | No |
| Delegated context provider | No task access by default | No | No | No | No | No | No | No |

AtMem is the only row permitted to commit canonical state. Administrative
profile registration, correction, skipping required work, cancellation,
deletion, and any policy override require an authenticated operator permission
distinct from ordinary agent access. This feature defines and enforces those
capabilities for the local product; production tenant identity and remote API
keys remain in the production service specification.

Automatic expiration is an AtMem policy operation, not an agent or operator
cancellation. Only the scoped policy evaluator may exercise `task.expire`, and
it must cite the profile rule and trusted evaluation time. Operators control
expiry policy through separately authorized immutable profile registration;
ordinary task access cannot force or postpone expiration.

## Provenance Model

Provenance is retained at four linked levels:

1. **Task provenance**: goal source, creating actor, scope, profile and policy
   versions, creation time, and initial evidence.
2. **Field and item provenance**: every structured value, item identity,
   constraint, dependency, blocker, skip reason, and status records the source
   observation or tool/verifier evidence, actor, extraction method,
   interpreter/model/prompt identity when applicable, assurance class, first
   observed time, and revision that introduced or superseded it.
3. **Transition provenance**: expected and resulting revisions, exact bounded
   operations, proposer, decision maker, reason codes, evidence references,
   idempotency identity, assurance ceiling, and timestamp.
4. **Delivery provenance**: authorized revision, serializer/profile/policy
   versions, exact context digest, preparation, inject/withhold decision,
   adapter, model boundary, exposure confirmation, and resulting run/turn.

Corrections never erase lineage. The current value points to the revision it
superseded, while deletion removes governed content and retains only the
minimum receipt evidence allowed by policy. Provenance does not include raw
chain-of-thought, secrets, or unnecessary prompt/tool payloads. Human-readable
inspection must explain where a value or status came from before presenting
technical hashes.

## Observability Requirements

Observability has three product levels:

- **Overview**: active, paused, blocked, completed, cancelled, expired, stale,
  and no-progress task counts plus integrity and AtBot/fallback health.
- **Task detail**: goal, phase, progress, ready/blocked/remaining items,
  constraints, completion eligibility, last progress, current guards, and the
  latest accepted/rejected/conflict/`no_change` decisions.
- **Evidence**: correlated proposal, decision, prior/resulting revision,
  field/status lineage, action/tool evidence, context preparation/exposure,
  lifecycle event, and honest outcome assurance.

At minimum, CLI JSON and dashboard health surfaces expose scope-filtered
counters for transition outcomes and reason codes, lifecycle totals, guard
types, stale-revision conflicts, fallback use, and context prepared versus
exposed. They expose latency distributions for validation/commit and context
preparation, current integrity status, last successful progress time, and tasks
that exceed profile no-progress or age thresholds. Metrics and diagnostics
must not expose task content across scope, secrets, raw chain-of-thought, or
unnecessary prompts and tool results.

An **observed workflow step** is one unique, authenticated, task-bound event
capable of changing execution state: an accepted host observation, an
action/tool request, an action/tool terminal result, an operator action, or a
registered verifier result. Token chunks, model streaming fragments,
diagnostic logs, and duplicate delivery of the same idempotency identity are
not additional workflow steps. Each observed workflow step resolves exactly
once to `accepted`, `rejected`, `conflict`, or `no_change`.

## Functional Requirements

- **FR-001**: AtMem MUST maintain Governed Task State as a separate authority
  domain from durable long-term memory and from host-owned conversation,
  checkpoint, planner, or workflow state.
- **FR-002**: A task MUST be bound to a stable task ID, `AuthorityScope`, task
  profile, lifecycle, goal, creation source, current revision, and policy
  generation. Lifecycle MUST be exactly one of `open`, `paused`, `completed`,
  `cancelled`, or `expired`; the last three are terminal.
- **FR-003**: A task profile MUST define an ordered or graph-shaped set of
  allowed phases and transitions. The base product MUST include a general
  profile supporting `plan`, `collect`, `validate`, `execute`, `verify`, and
  `complete` while allowing separately registered versioned profiles rather
  than hard-coding a two-phase GUI workflow.
- **FR-004**: Current state MUST support structured constraints, dependencies,
  sources to inspect, completed sources, and stable actionable items with
  bounded structured content and exactly one status from `pending`, `ready`,
  `running`, `blocked`, `completed`, `skipped`, or `failed`.
- **FR-005**: Task item schemas MAY be extended during profile-permitted
  collection and MUST reject structural changes after they are locked.
- **FR-006**: Every observed workflow step, as defined in this specification,
  MUST produce one typed outcome: `accepted`, `rejected`, `conflict`, or
  `no_change`. A `no_change` outcome MUST NOT rewrite an equivalent task
  snapshot.
- **FR-007**: AtBot and other intelligence components MAY propose typed state
  deltas but MUST NOT create, mutate, authorize, complete, cancel, expire,
  inject, or delete
  governed task state.
- **FR-008**: AtMem MUST authorize scope and eligible current state before
  candidate task content reaches AtBot and MUST revalidate the returned delta
  against the current head revision before commit.
- **FR-009**: Each proposal MUST identify its task, expected base revision,
  idempotency key, actor, interpreter or rule identity, affected fields and
  items, source observations, and evidence references.
- **FR-010**: State commits MUST be atomic, append an immutable revision, use
  optimistic concurrency, detect idempotent replay, and permit at most one
  accepted successor for a given head revision.
- **FR-011**: AtMem MUST enforce profile-defined phase, item-status, dependency,
  schema-lock, lifecycle, and completion transitions with stable human-readable
  reason codes.
- **FR-012**: A transition to `completed`, `skipped`, or task completion MUST
  retain the supporting evidence and assurance class and MUST distinguish host
  observation from independently verified outcome.
- **FR-013**: Task completion MUST be denied while profile-required items,
  constraints, dependencies, or verification gates remain unsatisfied.
- **FR-014**: AtMem MUST detect configurable repeated equivalent actions with
  no accepted progress and return an explainable guard signal. It MUST NOT
  claim to prevent or execute a host action unless the adapter enforces and
  reports that boundary.
- **FR-015**: Before a supported active-mode model call explicitly bound to an
  exact task ID, AtMem MUST construct a bounded, deterministic UTF-8 task-state
  envelope from the currently authorized revision and deliver it exactly once
  as governed data, separate from standing system instructions and long-term
  recalled memory. AtMem MUST NOT infer an active task from scope or choose
  among open tasks. A missing task ID MUST withhold task state with
  `task_context_selection_required`; an unknown, terminal, cross-scope, or
  otherwise ineligible task ID MUST withhold it with the non-disclosing reason
  `task_context_not_eligible`, and neither outcome may create exposure evidence.
- **FR-016**: Task context MUST include only the minimum useful current state,
  use stable ordering and serialization, and bind its digest and cache identity
  to scope, task ID, revision, profile version, policy generation, and
  serializer version.
- **FR-017**: Preparation, injection or withholding, exposure confirmation,
  transition proposals, decisions, revisions, corrections, lifecycle changes,
  guard signals, and terminal outcomes MUST be represented in tamper-evident
  evidence with honest proof boundaries.
- **FR-018**: Governed Task State MUST be disabled by default for existing and
  new installations until explicitly enabled for a supported scope or task;
  shadow mode MAY record and evaluate proposals but MUST NOT inject task state
  or block host execution.
- **FR-019**: AtBot, embedding, model-provider, or network failure MUST leave a
  deterministic typed-delta validation and `no_change` path. Failure MUST NOT
  widen scope, invent progress, unlock schemas, or bypass completion gates.
- **FR-020**: CLI and dashboard MUST support task start, list, show, timeline,
  pause, resume, correction, verification, completion, cancellation, and
  expiration inspection with plain-language state and next actions. Task
  `show` and `timeline` MUST render the bound expiry rule, effective expiry
  clock, evaluated time, transition reason, and supporting evidence;
  machine-readable CLI output MUST use the same authority contracts.
- **FR-021**: Operator corrections MUST require authenticated scope, expected
  revision, reason, and source; they MUST append history rather than overwrite
  prior revisions.
- **FR-022**: Completed, cancelled, or expired tasks MUST not be returned as
  active context and MUST NOT be mutated or reopened. Continuing terminal work
  requires an explicit new task linked to the terminal task's provenance.
- **FR-023**: OpenClaw, Pydantic AI, LangGraph, and generic integrations MUST
  preserve their host's messages, checkpoints, tools, model selection, and
  execution authority while mapping lifecycle hooks into the same task-state
  contracts.
- **FR-024**: Persistent subject, workspace, agent, task, session, run, turn,
  proposal, action, and tool-call identifiers MUST be validated according to
  their security or correlation role and MUST NOT be treated as interchangeable
  search hints.
- **FR-025**: Forgetting a subject or task MUST remove or tombstone current
  state, revisions, derived cache/index entries, and registered task artefacts
  according to policy and provide verifiable deletion evidence.
- **FR-026**: SQLite MUST remain the default canonical store; schema migration
  MUST preserve existing AtMem installations and be tested from all supported
  persisted-data upgrade versions.
- **FR-027**: Base operation MUST remain local-first and dependency-light. Any
  new model or framework dependency MUST remain optional, explicit, and
  compatible with Python 3.10–3.13 and Apache-2.0 enterprise requirements.
- **FR-028**: The implementation MUST use independently authored contracts,
  prompts, examples, documentation, and benchmark fixtures and MUST not bundle
  third-party research code, prompts, figures, datasets, or model weights
  without a separately reviewed compatible licence.
- **FR-029**: AtMem MUST enforce the Governance Matrix for every read,
  proposal, commit, correction, profile registration, lifecycle operation,
  context preparation, exposure, and deletion; actor labels alone MUST NOT
  grant capability.
- **FR-030**: Every task-level, item-level, field-level, status-level,
  transition-level, and delivery-level value or decision MUST retain the
  provenance attributes defined in the Provenance Model, including
  supersession linkage where applicable.
- **FR-031**: AtMem MUST provide a scope-authorized provenance query that starts
  from a human-readable task value or status and returns its source, actor,
  method, assurance, time, introducing/superseded revisions, transition
  reasons, evidence, and delivery usage without requiring users to interpret
  hashes.
- **FR-032**: AtMem MUST expose the scope-filtered health, counters, latency,
  progress-age, guard, fallback, prepared-versus-exposed, and integrity
  observations defined in Observability Requirements through CLI JSON and the
  dashboard using the same underlying authority data.
- **FR-033**: Task observability MUST minimize content and MUST NOT leak scoped
  task values, secrets, raw chain-of-thought, prompts, or tool payloads through
  metrics, logs, diagnostics, or cross-scope aggregates.
- **FR-034**: Custom task profile registration MUST be an explicit
  administrative operation with authenticated permission, closed-schema
  validation, immutable version and digest, conflict detection, dry-run
  validation, CLI/API inspection, and tamper-evident evidence. Registration
  MUST NOT enable a profile or alter existing tasks.
- **FR-035**: Skipping required work, cancelling a task, correcting provenance,
  or requesting a policy override MUST require the specific Governance Matrix
  permission, expected revision, human-readable reason, source binding, and
  complete audit evidence.
- **FR-036**: A profile MAY declare an absolute maximum task age and/or maximum
  no-progress age. At task start, AtMem MUST bind the applicable immutable rule
  and trusted UTC time source. Absolute age starts at task creation;
  `last_progress_at` is initialized to creation time and advances only for an
  accepted semantic-progress transition. Absolute age continues while paused,
  preventing indefinite parking; no-progress age excludes paused intervals so
  an intentional pause cannot itself cause no-progress expiry. Terminal tasks
  are not evaluated again. AtMem MUST durably retain pause accounting so the
  effective no-progress clock is identical after restart and can be verified
  against immutable lifecycle transitions. AtMem MUST evaluate expiry before task read,
  context preparation, proposal admission, and lifecycle mutation, and during
  an idempotent maintenance scan. When `now >=` the applicable threshold, the
  scoped AtMem policy evaluator MUST atomically transition the current head to
  `expired`, record the rule, evaluated time, prior revision, and evidence, and
  withhold task context. Expiry races MUST use the same optimistic-concurrency
  and replay guarantees as every other transition.
- **FR-037**: Task-context budget handling MUST operate on complete canonical
  fields and items using profile-declared, stable optional-field priority.
  Mandatory goal, active constraints, blockers, eligible next work, completion
  eligibility, scope, revision, and integrity bindings MUST never be truncated.
  If mandatory content cannot fit, AtMem MUST withhold task state with stable
  reason `task_context_budget_exceeded` and record preparation without exposure.
- **FR-038**: User-, host-, tool-, model-, and provider-originated task content
  MUST remain untrusted data. AtMem MUST schema-validate, canonically escape,
  length-bound, provenance-label, and place it only inside the governed-data
  envelope; it MUST NOT interpolate that content into envelope structure or an
  instruction channel. Tests MUST prove structural and delimiter containment,
  while product claims MUST NOT imply that framing guarantees model obedience.
- **FR-039**: A single runtime capability response MUST be authoritative for
  governed task-state availability and its delivery, guard-detection, and
  guard-enforcement boundaries. Public schemas, adapter responses, tests, and
  documentation MUST mirror that response and MUST NOT act as independent
  capability authorities.
- **FR-040**: Every `atmem task` operation MUST have documented required
  arguments, exact-scope resolution, runnable help examples, deterministic
  ordering and pagination for collections, human and `--json` output parity,
  and stable process behavior: exit `0` for successful reads, accepted actions,
  and `no_change`; exit `1` for rejected, conflict, unavailable, or integrity
  outcomes represented by a typed reason code; and exit `2` for CLI usage or
  input-schema errors. JSON mode MUST emit exactly one public-contract document
  on stdout and diagnostics only on stderr. Human mode MUST lead with the
  outcome and next action rather than identifiers. Non-interactive privileged
  mutations MUST require `--yes` in addition to every authority, expected
  revision, reason, and source requirement; omission MUST fail closed without
  prompting. CLI output MUST never disclose whether an unauthorized task ID
  exists.
- **FR-041**: Dashboard task surfaces MUST be capability-gated and preserve the
  current four-workspace information architecture. Disabled, shadow,
  unavailable, legacy, empty, loading, degraded, permission-denied, conflict,
  integrity-failed, and terminal states MUST each have a tested plain-language
  presentation with no false active controls. A selected task MUST persist
  across direct links among Activity, Decisions, and Evidence with a consistent
  compact summary and return path; Settings owns profile configuration and
  destructive task deletion. Mutations MUST preview exact effect and authority
  scope, use accessible confirmation, and never auto-retry after conflict.
  Controls, tabs, dialogs, timelines, live status, and errors MUST support
  keyboard operation, visible focus, semantic labels, assistive-technology
  announcements, reduced motion, narrow screens, and meaning independent of
  color or hover.

## Key Entities

- **Task**: Stable governed identity joining scope, profile, goal, lifecycle,
  current revision, policy generation, and creation evidence.
- **Task profile**: Versioned allowed phases, item transitions, schema rules,
  completion gates, evidence requirements, and guard thresholds.
- **Task state revision**: Immutable canonical snapshot with phase, constraints,
  sources, items, parent revision, digest, actor, timestamp, and evidence.
- **Task item**: Stable actionable data unit with structured content,
  dependencies, status, blocker or skip reason, assurance, evidence, and
  field/status-level provenance with supersession links.
- **Task-state proposal**: Untrusted typed delta nominated by AtBot, a host, a
  deterministic rule, or an operator against an expected base revision.
- **Transition decision**: AtMem's `accepted`, `rejected`, `conflict`, or `no_change`
  result with reason codes and resulting revision when applicable.
- **Task context package**: Minimum byte-stable authorized state delivered at a
  model boundary with preparation, digest, revision, and exposure binding.
- **Guard signal**: Explainable warning or denial such as no-progress,
  dependency-unsatisfied, out-of-scope, or completion-not-allowed.

## Failure and Edge Cases

- Two workers propose different successors to the same base revision.
- A delayed tool completion arrives after the task advanced or became terminal.
- An action succeeds at the host but independent real-world verification is
  unavailable.
- AtBot returns a full replacement state instead of the allowed bounded delta.
- A proposal removes a constraint, expands scope, changes stable item identity,
  or unlocks a schema.
- The same action is legitimately repeated for different task items.
- A task has no actionable items, cyclic dependencies, an impossible required
  constraint, or a source that can no longer be reached.
- A task pauses or expires while context is prepared but before exposure.
- An operator correction conflicts with an in-flight model proposal.
- Task context exceeds its byte budget or contains untrusted instruction-like
  text inside item content.
- A subject deletion occurs while task revisions or task-context caches exist.
- An older adapter emits ordinary memory events but no task-state events.

## Out of Scope

- Training or distributing a task-state-specific model using SFT, GRPO, or
  another reinforcement-learning method.
- Reproducing a third-party mobile GUI benchmark, dataset, prompt, model, or
  published performance result.
- Making AtMem an autonomous planner, tool executor, or replacement for the
  host agent framework.
- Letting AtBot or an external provider own canonical task state.
- Treating task progress as permanent personal memory without a separate
  admitted-memory proposal.
- General workflow orchestration, scheduling, queues, distributed workers, or
  production multi-tenant HTTP service infrastructure.
- Guaranteeing flawless execution or independently proving external outcomes
  solely from model text or host-reported tool completion.
- Automatically enabling task-state influence during installation or upgrade.

## Success Criteria

- **SC-001**: In deterministic multi-item scenarios, 100% of accepted valid
  transitions produce the expected next revision and 100% of stale,
  cross-scope, unknown-evidence, illegal, and schema-widening transitions leave
  the head unchanged.
- **SC-002**: Across at least 1,000 concurrent or replayed proposal attempts,
  each base revision has at most one accepted successor and repeated
  idempotency keys create no duplicate revisions.
- **SC-003**: Supported active adapters deliver identical task-state bytes and
  digests for identical scope, revision, profile, policy, and serializer input;
  shadow, completed, cancelled, expired, and cross-scope tasks deliver zero
  task-state bytes. Missing, unknown, terminal, cross-scope, and ambiguous task
  selection also delivers zero task-state bytes and never falls back to another
  open task.
- **SC-004**: A deterministic benchmark covering completed, remaining,
  dependency-blocked, skipped, failed, repeated-action, premature-finish,
  expired, context-overflow, and instruction-shaped cases produces the expected
  guard, completion, lifecycle, and context-disposition result for every case.
- **SC-005**: Every accepted task transition, operator correction, prepared
  context, exposure, guard, and lifecycle change can be traced to its actor,
  source, prior revision, evidence, decision reasons, and resulting digest.
- **SC-006**: With AtBot and optional semantic services unavailable, valid typed
  host/operator transitions, `no_change` recording, current-state delivery, and
  completion validation continue locally without scope or authority changes.
- **SC-007**: Local transition validation and commit overhead, excluding model,
  host-tool, and independent-verifier execution, has p95 below 25 ms across at
  least 1,000 measured single-writer operations without concurrent write
  contention on the supported SQLite profile. Concurrent/replayed correctness
  remains measured separately by SC-002 and has no 25 ms claim.
- **SC-008**: Upgrade tests from every supported persisted-data release create,
  advance, inspect, complete or cancel, and delete a governed task while all pre-existing
  memory, graph, vector, evidence, OpenClaw restore, and framework-adapter tests
  remain green.
- **SC-009**: A first-time operator can use CLI help or dashboard guidance to
  enable a scope, start a task, inspect progress, correct an item, and complete
  or cancel the task without directly editing a database or reading internal
  documentation.
- **SC-010**: Dependency and licence checks confirm that the base package adds
  no mandatory model/framework SDK and ships no unapproved third-party
  research artefacts.
- **SC-011**: A conformance matrix proves every governance action is accepted
  only for the permitted actor capability and exact scope, while all denied
  combinations leave state unchanged and emit a reasoned decision.
- **SC-012**: For every value/status/transition type in deterministic fixtures,
  a provenance query returns complete human-readable origin, actor, method,
  assurance, revision, supersession, evidence, and delivery history with zero
  cross-scope results.
- **SC-013**: Deterministic health fixtures produce exact lifecycle,
  transition, guard, fallback, stale-task, prepared/exposed, latency, and
  integrity observations in both CLI JSON and dashboard APIs without raw task
  content appearing in metric or diagnostic snapshots.
- **SC-014**: Deterministic clock tests cover absolute-age and no-progress-age
  boundaries, exclusion of paused intervals from no-progress age, inclusion of
  paused intervals in absolute age, lazy evaluation, maintenance evaluation,
  restart, and concurrent expiry; every due task reaches exactly one `expired`
  terminal head and is never delivered afterward.
- **SC-015**: Every context-budget fixture produces identical bytes and outcome
  across repeated runs; mandatory overflow always withholds with
  `task_context_budget_exceeded`, and instruction-shaped fixtures produce zero
  structural or instruction-channel breakout.
- **SC-016**: Runtime capability fixtures for current and legacy adapters match
  the public capabilities schema and documentation exactly, with unsupported
  task-state boundaries always reported as unavailable.
- **SC-017**: A deterministic CLI journey starting only from `atmem task
  --help` enables a scope, starts and lists a task, inspects it, resolves a
  conflict, corrects an item, and completes or cancels the task using runnable
  displayed commands. Every command produces the specified exit code, one JSON
  document in `--json` mode, no diagnostics on stdout, no undisclosed required
  argument, and one useful next command in human mode where applicable.
- **SC-018**: Dashboard fixtures for every FR-041 state preserve the selected
  task and direct return path across workspaces, expose no mutation unavailable
  to the current capability, require fresh confirmation after a conflict, and
  pass automated keyboard, focus, semantic-label, reduced-motion, narrow-screen,
  no-color, and content-overflow checks without regressing existing memory-only
  dashboard behavior when Governed Task State is disabled.

## Assumptions

- Existing AtMem authority scope, canonical serialization, SQLite transaction,
  evidence/exposure, adapter lifecycle, and AtBot companion primitives are the
  complete prerequisites; T000 verifies their concrete compatibility before
  implementation begins.
- Initial delivery targets local SQLite and the already supported OpenClaw,
  Pydantic AI, LangGraph, and generic lifecycle boundaries.
- Hosts remain responsible for selecting and executing actions. AtMem returns
  state, transition decisions, guards, and evidence only.
- A host-reported successful tool result is useful evidence but is not treated
  as independent proof unless a registered verifier supplies stronger evidence.
- Task state is bounded and current-task oriented; durable facts discovered
  during a task require the ordinary memory proposal and admission path.
