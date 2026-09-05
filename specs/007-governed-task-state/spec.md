# Feature Specification: Governed Task State

**Feature directory**: `specs/007-governed-task-state`  
**Created**: 2026-09-04  
**Status**: Implemented (core) · Amendment A (Host-Driven Task Binding and Proposal) proposed
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

Amendment A extends this matrix with session-binding and host-boundary
proposal capabilities; see that amendment for the added columns.

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
  among open tasks; resolving an operator-registered session-to-task binding
  (FR-042, FR-043) is a lookup of a recorded authorization, not inference or
  selection. A missing task ID MUST withhold task state with
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
- **Session-task binding** and **Host task proposal**: defined in Amendment A.

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

---

# Amendment A — Host-Driven Task Binding and Proposal

**Created**: 2026-09-05
**Status**: Proposed
**Amends**: FR-015, Governance Matrix, Key Entities, Failure and Edge Cases
**Adds**: User Story 6, FR-042–FR-054, SC-019–SC-031
**Revision 6** (2026-09-05): T058 established that every host-supplied identity
field — `sessionId`, `sessionKey`, `senderIsOwner` — is declared *optional* on
the contexts carrying it. FR-050 and FR-052 now state the resulting fail-closed
obligation explicitly: absent identity withholds and never resolves on partial
fields; an absent owner signal is a non-owner.

**Revision 5** (2026-09-05): resolves fourth-review findings I1, U1, C1. Host
proposal availability joins the adapter-keyed capability data; FR-051 requires
complete session identity in every host request contract and states why
addressing claims are permitted where authority claims are not.

**Revision 4** (2026-09-05): resolves third-review findings A1–A5. FR-054 binds
every host submission to its own session, closing a same-scope cross-task gap
that scope and role ceilings did not cover; FR-048 makes host-varying capability
data adapter-keyed.

**Revision 3** (2026-09-05): resolves second-review findings C1 (critical), I1,
C2, I2, C3, U1, R1, I3, T1. FR-053 makes exposure evidence truthful when a task
turns terminal mid-call; FR-052 now requires a positive host reset signal and
demotes the lifetime to supplemental; FR-049 path (b) must name a registered
model tool. Phase 12 is renumbered into execution order.

**Revision 2** (2026-09-05): resolves first-review findings I1, U1, C1, S1, C2,
U2, A1, T1, R1. FR-046 separates disabled from shadow; FR-049 fixes where deltas are
produced; FR-050 adds the in-host operator surface; FR-051 adds versioned host
contracts with derived actor role; FR-052 handles session recycling; FR-042
spells out the binding key.

## Motivation

The core feature is implemented and its authority contracts hold. Two gaps
prevent any of it from being reachable from OpenClaw, the primary supported
host.

**Gap 1 — the delivery branch never executes.** `integrations/openclaw/index.ts`
prepares task context only when `ctx.taskId` is present, and
`integrations/openclaw/src/types.ts` documents that field as *"Exact governed
task selected by the host. Never inferred by AtMem."* The host does not supply
it: OpenClaw's `PluginHookMessageContext` carries `channelId`, `accountId`,
`conversationId`, `sessionKey`, `runId`, `messageId`, `senderId`, reply and
trace correlation fields, and `callDepth` — and no task identity. OpenClaw's
own `taskId` belongs to detached task runs and terminal sessions and is not
plumbed to plugin hooks. The branch is therefore exercised only by
`integrations/openclaw/test/hooks.mjs`, which constructs the context by hand.
Observed consequence: `context prepared/exposed/withheld` reads `0/0/0` and
`governed_task_enforcing_adapters` is empty on a live install.

**Gap 2 — no host write path.** The Governance Matrix already grants the host
agent row *"Propose delta: Yes"* and *"Change lifecycle: Requests only"*, and
FR-007 already contemplates proposals from a host adapter. No such surface was
built. The MCP server exposes exactly two task tools —
`control_prepare_task_context` and `control_task_exposure_shown` — both
read-and-deliver. Write paths exist for the CLI (`atmem task correct`,
`complete`, `cancel`, …) and for the dashboard
(`ControlPlaneManager.change_task_lifecycle`, which commits pause, resume,
complete, and cancel under `ActorRole.OPERATOR` with its own stale-revision
conflict result). The adapter boundary has neither.

Gap 2 is therefore an unimplemented row of the existing matrix, not a widening
of authority. This amendment does not grant the host any capability the core
specification withheld; it builds the surface the matrix already permits and
constrains it to that row.

## Design Position

AtMem must still never choose a task. Amendment A closes Gap 1 with an
**operator-registered binding**, not a heuristic: a session key maps to a task
because an authenticated operator said so, and AtMem performs a lookup of that
recorded fact. Resolving a registered binding is not inference, is not
discovery, and is not selection among open tasks. Where no binding exists,
behavior is unchanged — task state is withheld.

## User Scenarios and Acceptance

### User Story 6 — Drive a governed task from the host (P1)

As an operator running an agent inside OpenClaw, I can bind a conversation to
an exact governed task once, and from then on the agent receives that task's
current state and can report progress against it, without my leaving the host
to run CLI commands and without the agent gaining authority to commit state.

**Why this priority**: Without it the feature is unreachable from the primary
supported host. Delivery cannot fire and the agent cannot report progress, so
no host-side value of Governed Task State is realizable at all.

**Independent test**: Register a binding from one session key to one open task,
run a turn through the OpenClaw bridge with no `ctx.taskId`, and verify the
exact task-state envelope is delivered once and exposure is confirmed. Submit a
host-proposed item-status delta with a valid expected revision and verify it
advances the head exactly once. Submit the same delta again, a delta against a
stale revision, a delta that skips a required item, and a delta for a task
bound to a different session, and verify each is refused with its stable reason
code and leaves the head unchanged. Revoke the binding and verify the next turn
withholds task state.

**Acceptance scenarios**:

1. Given an authenticated operator and an eligible open task, when a binding is
   registered for an exact scope and session key, then AtMem records it with
   evidence, and at most one active binding exists for that scope and session
   key.
2. Given a registered binding and a turn that supplies no host task identity,
   when task context is prepared, then AtMem resolves the binding, revalidates
   scope, eligibility, and revision, and delivers the exact current envelope
   once under the existing delivery rules.
3. Given a turn that supplies an explicit host task identity, when a binding
   also exists and names the same task, then the explicit identity is used and
   the outcome is identical; when they name different tasks, then AtMem
   withholds task state with `task_binding_conflict` and creates no exposure.
4. Given no binding and no host task identity, when task context is prepared,
   then AtMem withholds with the existing `task_context_selection_required` and
   discloses nothing about whether any task exists.
5. Given a binding whose task became terminal, cross-scope, or unknown, when
   task context is prepared, then AtMem withholds with the existing
   non-disclosing `task_context_not_eligible` and the binding is marked
   unresolvable rather than silently retargeted.
6. Given an authenticated host agent, when it proposes a typed bounded delta
   naming its task, expected base revision, idempotency key, and evidence, then
   AtMem validates it through the same policy path as every other proposal and
   returns `accepted`, `rejected`, `conflict`, or `no_change`.
7. Given a host-proposed delta that attempts an operator-only action —
   correcting provenance, skipping a required item, cancelling, deleting,
   overriding policy, registering a profile, or binding a session — when
   submitted, then AtMem refuses it on capability grounds before evaluating its
   content and leaves the head unchanged.
8. Given a host agent requesting task completion, when required items,
   constraints, dependencies, or gates remain unsatisfied, then AtMem returns
   the existing completion-not-allowed decision with blocking item IDs and
   commits nothing.
9. Given shadow mode, when a host proposes a delta, then AtMem evaluates and
   records the decision but commits no revision and delivers no context. Given a
   disabled scope, the same submission is refused immediately before identity
   resolution or content evaluation.
10. Given a conversation owner inside the host, when they issue the in-host bind
    command naming an eligible task, then AtMem registers the binding for their
    current conversation with full evidence, without the operator seeing or
    supplying a session key; a non-owner issuing the same command is refused
    without learning whether a binding exists.
11. Given a bound conversation that is reset or whose session key is recycled,
    when the next turn prepares context, then AtMem withholds with
    `task_binding_stale_session` and delivers zero bytes until an operator
    explicitly re-confirms; the earlier task is never inherited.
12. Given a host observation of one tool outcome, when AtBot is available, then
    AtMem authorizes the observation, obtains a candidate delta through the
    companion path, revalidates it against the current head, and commits or
    refuses it; when AtBot is unavailable, the same observation records a
    deterministic `no_change` and never fabricates progress.
13. Given a host submission carrying an actor-role, capability, or authority
    field, when received, then AtMem rejects it as malformed rather than
    honoring or silently ignoring the field.
14. Given a bound task that expires after its context was prepared and reached
    the model boundary, when exposure is confirmed, then AtMem records the
    exposure truthfully and records the expiry as a separate later event linked
    to that delivery; the next call re-resolves identity and withholds.
15. Given a host that cannot supply a session generation or a reliable session
    start, when binding is attempted, then the capability response reports
    session binding unavailable and no binding is created under a lifetime
    alone.
16. Given two open tasks in one authorized scope, each bound to a different
    session, when a host submission from the first session names the second
    session's task, then AtMem refuses it before content evaluation with a
    non-disclosing reason and leaves both heads unchanged — scope and role
    checks alone do not separate them.

## Adjustments to the Core Specification

**FR-015 is amended.** The sentence *"AtMem MUST NOT infer an active task from
scope or choose among open tasks"* stands unchanged in force. It is clarified
to read that AtMem MUST NOT infer or select a task, and that resolving an
operator-registered session-to-task binding is a lookup of a recorded
authorization rather than inference or selection. The withholding reasons and
their non-disclosure properties are unchanged.

**The Governance Matrix is amended** by the following capability, which no
existing column expresses:

| Actor or component | Bind session to task | Propose delta from host boundary |
| --- | --- | --- |
| AtMem authority | Validates and stores | Validates, decides, commits |
| Scoped AtMem policy evaluator | No | No |
| AtBot intelligence | No | No (unchanged: proposes through the companion route) |
| Host agent/framework | No | Yes, bounded, within its own authorized task |
| Authenticated operator | Requests with permission | Yes |
| Registered independent verifier | No | Attestation only |
| Auditor/observer | No | No |
| Delegated context provider | No | No |

Binding and unbinding are privileged operator operations subject to the same
preview, expected-scope, reason, source, evidence, and `--yes` requirements as
every other privileged mutation. A host agent may consume a binding and may
never create, retarget, or revoke one.

**Key Entities gains**:

- **Session-task binding**: An operator-registered, evidence-backed mapping from
  an exact scope and host session key to one task ID, with registration actor,
  reason, time, and revocation state. At most one is active per scope and
  session key.
- **Host task proposal**: A typed bounded delta submitted at the adapter
  boundary under the host-agent capability ceiling, carrying task ID, expected
  base revision, idempotency key, affected items, and evidence references.

**Failure and Edge Cases gains**. Each case states its required outcome; none
may be left to implementation judgement:

- **Several sessions bound to one task**: permitted. Bindings are many-to-one;
  uniqueness is per binding key, never per task. Each bound session resolves to
  the same task and each turn is independently scope-revalidated.
- **Retargeting an already-bound session**: refused as an update. Changing a
  session's target MUST be an explicit revoke followed by an explicit register,
  each carrying its own authority, reason, source, and evidence. No operation
  may silently repoint an active binding.
- **The bound task expires between context preparation and exposure**: governed
  by FR-053. Evidence records what happened, not what policy would have
  preferred. If the bytes reached the model boundary, exposure is confirmed
  truthfully and the expiry is recorded as a separate later event; if they did
  not, preparation is recorded without exposure. Either way the binding becomes
  unresolvable and every subsequent call withholds. A binding never extends a
  terminal task's reachability, but it also never rewrites the history of a call
  that already happened.
- **A recycled or reset session key in the same scope**: MUST NOT inherit the
  earlier binding. Resolution MUST withhold with `task_binding_stale_session`
  and require explicit re-confirmation (FR-052). Exact scope alone does not
  distinguish conversations and MUST NOT be relied on for this case.
- **A host proposes against a bound task whose scope no longer authorizes that
  agent**: refused on scope grounds before content evaluation, with the head
  unchanged and no disclosure of the task's existence.
- **A host proposes against a task in its own scope but bound to another
  session**: refused under FR-054 before content evaluation. This is a distinct
  case from the one above and is not caught by scope or capability checks.
- **The host supplies a task identity that disagrees with a live binding**:
  withheld under `task_binding_conflict` (FR-043); neither source wins.
- **A submission arrives while the scope is disabled or in shadow mode**:
  governed by FR-046 — immediate refusal when disabled, evaluated without
  commit when shadow.

## Functional Requirements

- **FR-042**: AtMem MUST support an operator-registered session-to-task binding
  whose unique key is exactly
  `(subject_id, agent_id, workspace_id, host_type, session_key, session_epoch)`
  — the three `AuthorityScope` fields, the host namespace, the host session key,
  and the session generation defined in FR-052. `task_id` is the binding's
  target and MUST NOT be part of the uniqueness key. At most one binding MUST be
  active per key; bindings are many-to-one, so several keys MAY target one task.
  Registration and revocation MUST be privileged operator operations requiring
  authenticated capability, reason, source, and tamper-evident evidence, and
  MUST append history rather than overwrite prior bindings.
- **FR-043**: Task identity for delivery MUST resolve in a fixed order: an
  explicit host-supplied task ID, then an active registered binding, then
  withholding. AtMem MUST NOT infer, discover, or select a task at any step. An
  explicit identity that disagrees with an active binding MUST withhold task
  state with stable reason `task_binding_conflict` and create no exposure
  evidence. Absence of both MUST withhold with the existing
  `task_context_selection_required`; a binding resolving to an unknown,
  terminal, or cross-scope task MUST withhold with the existing non-disclosing
  `task_context_not_eligible`.
- **FR-044**: AtMem MUST expose a host-boundary proposal operation that accepts
  a typed bounded delta with task ID, expected base revision, idempotency key,
  affected items, actor and adapter identity, and evidence references, and MUST
  evaluate it through the identical policy, concurrency, replay, evidence, and
  assurance path used for every other proposal, returning `accepted`,
  `rejected`, `conflict`, or `no_change`.
- **FR-045**: Host-boundary proposals MUST be evaluated under the host-agent
  capability ceiling. Operator-only actions — correction, required-item
  skipping, cancellation, deletion, policy override, profile registration, and
  session binding — MUST be refused on capability grounds before delta content
  is evaluated, with a stable reason code and no state change. A host MAY
  request a lifecycle change; the request MUST be decided by existing lifecycle
  and completion gates and MUST NOT bypass them.
- **FR-046**: Disabled and shadow scopes MUST behave differently and MUST NOT
  be conflated. Where governed task state is disabled for the scope, a
  host-boundary observation, proposal, or lifecycle request MUST be refused
  immediately with the existing disabled reason, before task identity is
  resolved or delta content is evaluated, recording only the minimal evidence
  that a refused attempt occurred and disclosing nothing about whether any task
  exists. In shadow mode, the same submission MUST be fully evaluated and
  recorded as a decision with reason codes, MUST NOT commit a revision, and
  MUST NOT deliver context or influence execution; shadow is the rehearsal path
  for this boundary and must produce the same decision it would produce when
  active.
- **FR-047**: The OpenClaw bridge MUST resolve task identity through FR-043,
  carry host proposals and lifecycle requests through FR-044–FR-046, preserve
  existing memory-only behavior when no identity resolves, and continue to
  claim no capability to block OpenClaw execution. Bridge behavior MUST remain
  backward compatible for installations with no bindings.
- **FR-048**: A single runtime capability response MUST remain authoritative for
  the new boundaries, advertising session-binding availability, host-proposal
  availability, and agent-tool availability alongside the existing delivery,
  guard-detection, and guard-enforcement flags. Availability that varies by host
  MUST be expressed as adapter-keyed data, not a single global boolean: session
  binding depends on whether a given adapter supplies a reset signal, host
  proposal depends on whether a given adapter can submit authenticated
  session-bound requests at all, and the agent-facing delta tool depends on
  whether a given adapter registers it. All three vary by host, so one flag
  cannot truthfully describe two adapters at once. These MUST follow
  the existing adapter-keyed pattern already used for guard enforcement. Where a
  global flag is retained it MUST mean only that the capability exists in the
  runtime, and adapter responses MUST derive their own availability from the
  adapter-keyed data rather than from that flag. Schemas, adapter responses, tests, and documentation
  MUST mirror that response and MUST NOT act as independent authorities.
- **FR-049**: AtMem MUST define exactly where a typed delta is produced from a
  raw host observation; no component may be left to infer it. A host adapter
  MUST NOT synthesize deltas from tool output. Two entry points exist and no
  third is permitted:
  (a) an **observation** submission carrying one bounded, authenticated,
  task-bound workflow step, which AtMem authorizes and routes through the
  existing AtBot companion path to obtain a candidate delta that AtMem then
  revalidates against the current head before commit; and
  (b) an **explicit typed delta** submitted by the agent through a tool the
  host registers with the model, already in delta form, carrying no
  interpretation step. A control-plane operation is not automatically visible
  to a model: path (b) MUST name and register an actual host model tool, define
  the result the model receives for each decision outcome, and be tested at the
  tool boundary, or it MUST NOT be claimed as available.
  Where AtBot is unavailable, path (a) MUST record a deterministic `no_change`
  rather than fabricating progress, per FR-019. Observation payloads MUST be
  minimized to the fields the profile declares relevant, MUST remain untrusted
  data under FR-038, and MUST NOT carry raw prompts, full tool results, secrets,
  or chain-of-thought. Idempotency keys MUST be derived deterministically from
  the observed step's stable host identifiers — never from payload content,
  wall-clock time, or a random value — so a retried hook, a duplicated tool
  result, and a replayed turn collapse to one decision.
- **FR-050**: An operator MUST be able to bind, unbind, and inspect the binding
  for the conversation they are in, from inside the host, without obtaining or
  handling an opaque session key. The host surface MUST be authorized as the
  conversation owner by the host's own owner signal, MUST carry the same
  authority, reason, source, evidence, and confirmation requirements as the CLI
  and dashboard paths, and MUST NOT disclose the session key, the existence of
  other sessions' bindings, or any task outside the caller's authorized scope.
  A caller whose owner signal is absent, unset, or anything other than an
  explicit affirmative MUST be treated as a non-owner: the signal is optional on
  every host context that carries it, so absence is never permission. A
  non-owner caller MUST be refused without disclosing whether a binding
  exists. This surface grants no capability beyond the operator row of the
  Governance Matrix. It MUST supply the host's session identity and current
  generation on registration, and every later context lookup MUST present the
  same generation, so binding and resolution cannot disagree about which
  conversation they refer to.
- **FR-051**: Host-boundary submissions MUST use versioned public contracts
  distinct from the internal proposal type: a host task proposal request, a host
  observation request, and a host lifecycle request, each with a closed schema,
  stable reason codes, and explicit adapter and host identity. Every one of the
  three MUST carry the session identity FR-054 resolves — `host_type`,
  `session_key`, and `session_epoch` — as required fields, or MUST obtain them
  from an authenticated transport envelope that supplies all three; a schema
  that admits a submission without complete session identity MUST be treated as
  malformed. Session identity is an **addressing** claim that AtMem resolves and
  checks, not an authority claim, and is therefore permitted where an
  actor-role, capability, or authority field is not: the host states which
  conversation it is, and AtMem decides what that conversation may do. Actor role MUST
  be derived from the authenticated transport and registered adapter identity
  and MUST NEVER be read from a caller-supplied field; a submission that carries
  an actor-role, capability, or authority field MUST be rejected as malformed
  rather than honored or silently ignored.
- **FR-052**: A binding MUST NOT survive a conversation reset, and reset
  detection MUST be positive rather than inferred from elapsed time. Session
  binding requires a host reset signal: an opaque `session_epoch` that the host
  changes when a conversation is reset, replaced, or newly started. AtMem MUST
  bind that generation at registration and include it in the binding key.
  Resolution MUST withhold with stable reason `task_binding_stale_session` when
  the presented generation differs from the bound generation or when the host
  reports a session start later than the binding's registration. Because hosts
  declare these values as optional, a turn that presents no generation or no
  session key MUST withhold rather than resolve on the remaining fields, and a
  binding MUST NOT be registered from a call that cannot supply both; absence is
  never treated as a match. Recovery MUST
  require explicit operator re-confirmation and MUST NOT be automatic. A
  profile-declared binding lifetime is **supplemental expiry protection only**
  and MUST NOT be offered as a substitute for a reset signal: a lifetime cannot
  detect a reset that occurs within it, so a host that cannot supply a
  generation or a reliable session start MUST have session binding reported
  unavailable in the capability response, and MUST NOT be bound under a
  lifetime alone.
- **FR-053**: Exposure evidence MUST record what actually happened at the model
  boundary. Preparation authorizes exactly one model call. Where the adapter can
  prove the prepared bytes reached that boundary, AtMem MUST confirm exposure
  truthfully even when the task became terminal, ineligible, or unbound between
  preparation and confirmation; the subsequent terminal or ineligible outcome
  MUST be recorded as its own later event linked to that delivery. Where the
  bytes demonstrably did not reach the boundary, or the adapter cannot prove
  delivery, AtMem MUST record preparation without exposure and MUST NOT claim
  exposure. AtMem MUST NOT suppress, discard, or rewrite evidence of a delivery
  that already occurred in order to make history consistent with current policy.
  Every call after the authorizing one MUST re-resolve identity and withhold.

- **FR-054**: Every host-boundary observation, proposal, and lifecycle request
  MUST be bound to the session that submits it. AtMem MUST resolve
  `(host_type, session_key, session_epoch)` through FR-043 and MUST require the
  submitted `task_id` to equal the resolved task. A mismatch MUST be refused
  before delta content is evaluated, with a stable non-disclosing reason that
  reveals nothing about whether the named task exists, and MUST leave the head
  unchanged. Scope and capability checks are insufficient on their own: one
  authorized scope may hold several concurrent tasks, so a submission naming a
  task bound to a different session would otherwise pass both. Where FR-043
  resolves nothing, the submission MUST be refused rather than falling back to
  the submitted identifier.
## Success Criteria

- **SC-019**: In deterministic fixtures, every combination of {explicit
  identity, active binding, both agreeing, both disagreeing, neither} produces
  the specified disposition and reason code; disagreement and absence deliver
  zero task-state bytes, and no case selects a task AtMem was not told to use.
- **SC-020**: Across at least 1,000 concurrent or replayed host-boundary
  proposals, each base revision has at most one accepted successor and repeated
  idempotency keys create no duplicate revision, matching SC-002 exactly.
- **SC-021**: A conformance matrix proves every operator-only action is refused
  at the host boundary on capability grounds with the head unchanged, and that
  the host capability ceiling cannot be widened by actor label, adapter
  identity, binding ownership, or evidence content.
- **SC-022**: An end-to-end OpenClaw test binds a session, delivers exact task
  context on a turn carrying no host task identity, confirms exposure exactly
  once, advances the task by host proposal, is denied premature completion,
  and withholds after revocation — with `prepared`, `exposed`, and `withheld`
  counters matching the expected sequence.
- **SC-023**: Runtime capability fixtures report session-binding, host-proposal,
  and agent-tool availability truthfully per adapter, including a mixed fixture
  in which one adapter supplies a reset signal and another does not, and each
  adapter response derives its own availability from the adapter-keyed data.
  Guard enforcement remains reported as unavailable until an adapter proves it.
- **SC-024**: Observation fixtures produce the specified decision with AtBot
  available and, with AtBot and the network disabled, a deterministic
  `no_change` in every case — never invented progress. Derived idempotency keys
  collapse retried hooks, duplicated tool results, and replayed turns to exactly
  one decision, and no observation payload contains a raw prompt, full tool
  result, secret, or chain-of-thought.
- **SC-025**: For every reset path a supported host can produce — changed
  session epoch, host-reported session start after registration, and elapsed
  binding lifetime — a recycled session key within the same scope delivers zero
  task-state bytes under `task_binding_stale_session`, and no fixture inherits
  an earlier task. Hosts able to supply neither a generation nor a session start
  report session binding unavailable rather than resolving.
- **SC-026**: The in-host binding surface registers, revokes, and reports a
  binding for the caller's own conversation without exposing a session key;
  every non-owner call is refused with no disclosure of binding existence, and
  no call reaches a capability outside the operator row of the Governance
  Matrix.
- **SC-027**: Host-boundary contract fixtures validate against their published
  versioned schemas; every submission carrying a caller-supplied actor-role,
  capability, or authority field is rejected as malformed, and actor role is
  proven to derive only from authenticated transport and registered adapter
  identity. Every submission missing, emptying, or malforming any of
  `host_type`, `session_key`, or `session_epoch` is likewise rejected as
  malformed rather than resolved with a partial identity.
- **SC-028**: Delivery-race fixtures prove exposure evidence is truthful in both
  directions: where prepared bytes reached the boundary before the task became
  terminal, exposure is confirmed and the terminal outcome appears as a separate
  later linked event; where they did not, preparation is recorded with no
  exposure claim. No fixture produces evidence that a delivery did not occur
  when it did, and every subsequent call withholds.
- **SC-029**: Every supported host either supplies a reset signal that rotates
  `session_epoch` across its reset, session-start, and subsequent-prompt paths,
  or reports session binding unavailable. No fixture binds a session under a
  lifetime alone, and a reset occurring inside a declared lifetime still
  withholds.
- **SC-030**: The agent-facing typed-delta tool is registered with the host,
  visible to the model, and returns a defined result for `accepted`, `rejected`,
  `conflict`, and `no_change`; tool-boundary tests cover each outcome.

- **SC-031**: For every host-boundary operation, a submission naming a task
  bound to a different session in the same authorized scope is refused before
  content evaluation with a non-disclosing reason and both heads unchanged; a
  submission whose session resolves to nothing is refused rather than trusted.
## Out of Scope for this Amendment

- Automatic or heuristic session-to-task binding, including binding by
  conversation title, recency, sole-open-task, or model suggestion.
- Granting the host agent any capability beyond its existing Governance Matrix
  row.
- Guard enforcement at the OpenClaw execution boundary. Detection remains
  detection; the bridge continues to make no blocking claim.
- Changing OpenClaw itself. This amendment is implementable entirely within
  AtMem and its bridge. If OpenClaw later adds task identity to its plugin hook
  context, FR-043's first resolution step consumes it with no further change.
