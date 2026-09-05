# Governed Task State

Durable memory answers *what do we know about this person?*. Governed Task
State answers a different question: *what is this agent doing right now, what
is left, and is it allowed to finish?*

They are separate authority planes on purpose. Temporary workflow progress must
not silently become permanent personal memory, and a host's own conversation,
checkpoints, planner, or session state stay the host's. AtMem adds current
execution state; it does not become the agent framework.

Governed Task State is **disabled by default**, for existing installations and
new ones. Upgrading AtMem never starts influencing an agent.

## The shape of a task

A task binds a stable id, an `AuthorityScope`, a versioned profile, a goal, a
lifecycle, a current revision, and a policy generation. Its lifecycle is exactly
one of `open`, `paused`, `completed`, `cancelled`, or `expired` — the last three
terminal.

Inside it are **items**: stable actionable units, each with exactly one status
from `pending`, `ready`, `running`, `blocked`, `completed`, `skipped`, or
`failed`, plus dependencies, blocker or skip reasons, evidence, and an assurance
class. Alongside them sit constraints and a checklist of sources to inspect.

Every state is an **immutable revision**. Nothing is edited in place; the head
moves forward and the previous snapshot stays exactly as it was.

## Who may do what

The Governance Matrix is executable code, not a table in a document, and every
capability is derived from a role rather than read from a string a caller
supplied. Calling yourself an administrator changes nothing.

| Actor | Read | Propose | Commit | Correct | Register profile | Lifecycle | Expire | Deliver | Delete |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AtMem authority | yes | yes | **yes** | yes | yes | yes | no | yes | yes |
| Scoped policy evaluator | no | no | no | no | no | no | **yes** | no | no |
| AtBot intelligence | yes | yes | no | no | no | no | no | no | no |
| Host agent | yes | yes | no | no | no | no | no | no | no |
| Operator | yes | yes | no | yes | no | yes | no | no | no |
| Administrator | yes | yes | no | yes | yes | yes | no | no | yes |
| Registered verifier | yes | yes | no | no | no | no | no | no | no |
| Auditor | yes | no | no | no | no | no | no | no | no |
| Delegated context provider | no | no | no | no | no | no | no | no | no |

Two rows carry most of the weight. **AtMem is the only role that commits**, so
a model or a host can propose a change and never write one. **The policy
evaluator holds `expire_task` and nothing else**, so ageing a task out cannot be
spelled as an agent cancellation or an operator override.

## Proposals, decisions, and the four outcomes

A proposer submits a *typed delta* against an exact base revision. There is no
"replace state" operation, deliberately: a full replacement would let a proposer
overwrite work it never saw. The available operations are bounded — set a phase,
set an item's status, add an item, set item content, set a blocker, add or
satisfy a constraint, mark a source inspected, lock the schema.

Every observed workflow step resolves to exactly one outcome:

| Outcome | Meaning |
| --- | --- |
| `accepted` | Valid and committed; the head advanced by exactly one revision. |
| `rejected` | Refused with a stable reason; the head did not move. |
| `conflict` | The base revision is stale. The proposal may be fine; the world moved. |
| `no_change` | Nothing actually differs. No new revision is written. |

`no_change` is possible because a snapshot has a *semantic digest* that excludes
timestamps and revision bookkeeping. Two snapshots that mean the same thing have
the same semantic digest, so AtMem can say "nothing changed" honestly instead of
writing a revision that only differs by a clock reading.

Reason codes are a closed vocabulary. A decision citing an unknown code is
rejected at construction, so operators and scripts can rely on the set.

## Concurrency

Every mutating proposal names its base revision. Two guarantees follow:

- **At most one accepted successor per revision.** A unique index on
  `(task_id, parent_revision)` enforces it in the database, not merely in code.
- **A stale proposal fails closed** with `stale_base_revision` and changes
  nothing, rather than being retried on the proposer's behalf.

Resubmitting the same idempotency key replays the original decision. Reusing a
key with a different delta is an error, not a silent overwrite. A thousand
replays produce one revision.

## Assurance: saying only what is actually known

Each role has a ceiling on the assurance it may claim:

| Role | Ceiling |
| --- | --- |
| AtBot intelligence | `model_interpreted` |
| Host agent | `host_reported` |
| Operator / administrator | `operator_confirmed` |
| Registered verifier | `independently_verified` |

A host reporting that its tool succeeded is useful evidence, and it is not
independent proof. A model may not claim verification it did not perform. When
an item is marked completed, AtMem records the strongest assurance actually
behind the claim, and a provenance query reports `independently_verified: false`
unless a registered verifier supplied it.

Completing an item requires either cited evidence or an actor whose assurance
class can carry the claim on its own. Unevidenced optimism about finished work
is exactly where memory does damage.

## Expiry: two clocks that behave differently

A profile may declare a maximum absolute age, a maximum no-progress age, or
both. The applicable rule and a trusted UTC clock are bound to the task **when
it starts** and never re-read, so editing a profile cannot retroactively expire
work already running.

- **Absolute age** runs from creation and keeps running while paused, so a task
  cannot be parked indefinitely.
- **No-progress age** counts only active time. Completed pauses are subtracted
  and a currently open pause is subtracted live, so deliberately pausing work is
  never itself treated as failing to progress.

Pause accounting is stored as an accumulator for speed and can be rebuilt from
the immutable lifecycle revisions for audit; the two must agree.

Expiry is evaluated before a read, a list, a proposal, and a lifecycle change,
and by an idempotent maintenance scan. However many evaluations run, a due task
reaches exactly one `expired` head, cites the rule and the evaluated time, and
is never delivered afterwards. A terminal task is never re-evaluated.

## Task context: data at a model boundary

When an adapter reaches the model boundary with an **exact task id**, AtMem
builds a bounded, deterministic UTF-8 block and delivers it once as governed
data, separate from standing instructions and from recalled long-term memory.

Three rules govern that block.

**It is data, never instructions.** Task content originates from users, tools,
and models, and any of it may look like a command. The serializer strips control
characters, defangs fence-like sequences, flattens newlines so one item cannot
forge a field, and wraps everything in a fence the content cannot emit. The
preamble labels it explicitly. Framing does not guarantee a model obeys it — no
honest product claims that — but a delimiter the content cannot forge is the
part that *can* be guaranteed, and the tests prove it.

**It is byte-stable.** Identical scope, revision, profile version, policy
generation, and serializer version produce identical bytes and digest. Cache
identity binds all five.

**It never truncates.** If the block exceeds its budget, whole optional fields
are dropped in the profile's declared order. If the mandatory core still does not
fit, the package is withheld with `task_context_budget_exceeded`. A truncated
task state is a different task state.

### Selection is explicit

AtMem never infers an active task from scope and never chooses among open tasks.

| Situation | Reason code |
| --- | --- |
| No task id supplied | `task_context_selection_required` |
| Unknown, terminal, paused, or out-of-scope task id | `task_context_not_eligible` |
| Scope disabled | `task_state_disabled` |
| Scope in shadow mode | `task_state_shadow_mode` |
| Mandatory content over budget | `task_context_budget_exceeded` |

The middle case is deliberately non-disclosing: unknown, terminal, and
belonging-to-someone-else are indistinguishable from outside, so a caller cannot
probe for the existence of another scope's work. Every withheld outcome carries
zero task-state bytes and creates no exposure evidence.

## Guards: what AtMem noticed

AtMem can see that an agent has repeated an equivalent action several times
without anything advancing, that work is waiting on unfinished dependencies, or
that completion is being attempted with required items outstanding.

What AtMem cannot do is stop it. The host owns execution. So every guard is a
*detection* with an explanation, and `enforced` stays false unless an adapter
reports that it actually blocked something — which none does today, and the
runtime capability response says so.

Action fingerprints include the target, so legitimately repeating one action
across different items is not mistaken for a stuck loop, and the repeat window
resets at the last accepted progress.

## Provenance

Four linked levels are retained: task, field and item, transition, and delivery.
Every value records its source, actor, method, interpreter where applicable,
assurance, time, the revision that introduced it, and the revision it superseded.

Corrections never erase lineage. A provenance query answers in words before it
shows a hash:

> Changed by an accepted typed delta by an authenticated operator
> (ops@example.com) at 2026-09-05T12:31:00+00:00; confirmed by an authenticated
> operator. This replaced the value from revision 3.

## Observability

Three levels — overview, task detail, and evidence — expose lifecycle counts,
transition outcomes, reason-code counters, guard totals, latency distributions,
prepared versus exposed context, freshness, overdue tasks, and revision-chain
integrity.

All of it is scope-filtered at the source and deliberately content-free. Goals,
item titles, blocker text, prompts, and tool payloads appear in no snapshot, and
tests assert that credential-shaped strings planted in a task never surface in a
metric.

## The CLI

```bash
# Nothing runs until a scope is explicitly enabled.
atmem task enable memories.db --subject user-1 --agent agent-1 --workspace ws-1

atmem task start memories.db --task-id task-1 --goal "Ship the migration" \
    --actor you@example.com --required-item review=Review the change \
    --item notify=Notify the team \
    --subject user-1 --agent agent-1 --workspace ws-1

atmem task list    memories.db --subject user-1 --agent agent-1 --workspace ws-1
atmem task show    memories.db task-1 --subject user-1 --agent agent-1 --workspace ws-1
atmem task health  memories.db --subject user-1 --agent agent-1 --workspace ws-1
atmem task verify  memories.db --subject user-1 --agent agent-1 --workspace ws-1

atmem task correct memories.db task-1 --actor you@example.com \
    --item review --status completed --reason "Reviewed offline" \
    --expected-revision 1 --yes \
    --subject user-1 --agent agent-1 --workspace ws-1

atmem task complete memories.db task-1 --actor you@example.com --yes \
    --subject user-1 --agent agent-1 --workspace ws-1
```

Process behaviour is part of the contract:

| Exit | Meaning |
| --- | --- |
| `0` | A successful read, an accepted action, or `no_change`. |
| `1` | Rejected, conflict, unavailable, or integrity outcome, with a typed reason code. |
| `2` | CLI usage or input-schema error. |

In `--json` mode exactly one public-contract document reaches stdout — including
for failures, so a script can parse stdout unconditionally — and diagnostics go
to stderr. Human mode leads with the outcome and prints one actionable `Next:`
command. Privileged mutations (`cancel`, `correct`, `forget`, profile
registration) require `--yes` when nothing is attached to the terminal; omitting
it fails closed rather than prompting into a pipe.

`atmem task profile register` stores an immutable versioned rule set. It does
not enable that profile or alter any existing task, and re-registering a version
with different rules is refused.

## The dashboard

Task surfaces are capability-gated on the runtime response and live inside the
existing four workspaces — no fifth workspace, no competing global verdict.
Disabled, shadow, empty, conflict, and terminal states each have a plain-language
presentation with no false active controls, and the card states plainly whether
any task context is reaching an agent.

Mutations preview their exact scope, task, revision, and effect before
confirmation. **A conflict is never auto-retried**: the operator is shown what
changed and must submit a fresh request.

## Hosts and adapters

`AtMemAdapterIdentity` carries an optional `task_id`, optional only for legacy,
task-unaware operation. Absent identity disables task delivery outright and
never triggers discovery. `identity.for_task("task-1")` binds one task.

Pydantic AI capabilities and LangGraph middleware append the governed task
block as a separate user-data message at each model boundary, after exact
digest validation. They leave dependencies, model selection, tools, message
history, graph state, and checkpoints untouched. Their shared turn lifecycle
also correlates tool outcomes and explicit typed task observations with the
bound task.

The OpenClaw bridge performs the same preparation and exact-exposure handshake.
OpenClaw supplies no `taskId` of its own, so in practice the bridge resolves
identity through a **conversation binding** — see below. Older hosts and unbound
conversations keep the legacy memory-only path. The bridge does not discover an
open task and does not advertise guard enforcement.

AtBot can be called through its authenticated loopback
`/api/companion/task-state/propose` route. It receives only the exact snapshot
AtMem has authorized and returns no authority decision. AtMem revalidates the
task ID, base revision, referenced items/constraints/sources/phases, operation
shape, assurance, and policy against the current head before it alone commits.

One runtime response is the capability authority:

```json
"governed_task_state": true,
"governed_task_state_delivery": true,
"governed_task_guard_detection": true,
"governed_task_guard_enforcement": false
```


Availability that varies by host is **adapter-keyed**, not a single boolean:
`governed_task_session_binding_adapters`,
`governed_task_host_proposal_adapters`, and
`governed_task_agent_delta_tool_adapters` list the adapters that actually have
each capability. One adapter may supply a reset signal and register the delta
tool while another does neither, and one flag could not describe both
truthfully. An adapter response derives its own availability from these lists
rather than from the global flags.

Schemas, `docs/capabilities.json`, adapter replies, and tests mirror that
response. None of them is an independent authority, and no unsupported boundary
is ever advertised.

`governed_task_guard_enforcement` is **derived, not asserted**. AtMem cannot
stop a host from calling a tool, so the flag reads a registry rather than a
constant: it is true only while at least one adapter has registered a real
blocking boundary through `atmem.task_state.enforcement.register_enforcer`, and
registration requires a checkable `blocked_actions()` rather than a promise.
Editing a boolean cannot turn it on. The registry is empty today, which is why
the flag is false — and why it will become true on its own the moment an
enforcing adapter exists, without anyone having to remember to update it.

## Binding a conversation to a task

A host does not tell AtMem which task a conversation is working on. OpenClaw's
plugin hook context carries a channel, a session, a run — and no task identity
at all. So without something else, task context could never be delivered: there
is nothing to name the task, and AtMem must never guess one.

The something else is a **binding**: an operator says once that this
conversation is that task, and AtMem records it. Later turns *look it up*.
Resolving a recorded authorization is not inference, discovery, or selection
among open tasks — the distinction that matters is that a human decided, not
that a lookup happened.

```bash
atmem task bind memories.db migrate \
  --subject user-1 --agent agent-1 --workspace ws-1 \
  --actor you@example.com --reason "drive the migration from this chat" \
  --host-type openclaw --session-key CONVERSATION --session-epoch GENERATION --yes
```

Inside OpenClaw the owner can use `task_binding_status` to see what the current
conversation is bound to, without handling an opaque session key.

**How identity resolves.** In one fixed, total order:

1. An explicit task id the host supplied.
2. An active binding for this exact conversation.
3. Withhold.

Nothing else. When the first two disagree, AtMem withholds under
`task_binding_conflict` rather than picking: preferring the explicit id would
silently mask a misconfigured binding, and preferring the binding would let
stale operator state override a host that knows better. Only withholding
surfaces the contradiction to someone who can fix it.

**The binding key** is
`(subject, agent, workspace, host_type, session_key, session_epoch)`. `task_id`
is the target and deliberately *outside* the key. Two consequences follow:
several conversations may drive one task, and repointing a conversation cannot
be written as an update — it is a revoke and a register, each carrying its own
authority, reason, and evidence.

**Conversation resets.** `session_epoch` is the host's session generation.
OpenClaw rotates `sessionId` when a conversation is reset, so a recycled
session key does not match any active row and resolution withholds under
`task_binding_stale_session` until an operator re-confirms. A profile may also
declare `binding_lifetime_ms` as supplemental expiry, but that is a backstop and
never a substitute: a lifetime cannot detect a reset that happens inside it, and
the reset that matters most is the one a minute after binding. A host that can
supply neither a generation nor a reliable session start is reported as unable
to bind at all rather than bound unsafely.

**Every identity field is optional upstream.** OpenClaw declares `sessionId`,
`sessionKey`, and `senderIsOwner` as optional on the contexts that carry them.
So absence is ordinary, and everything fails closed: a partial identity is
refused rather than resolved on what survived, and an absent owner signal is
treated as *not* the owner. Absence is never permission.

## Reporting progress from a host

Delivery alone would hand an agent a checklist it could not tick. Two entry
points exist, and deliberately no third.

**Observation.** The adapter submits one bounded, authenticated workflow step —
what it saw, never a delta. AtMem authorizes it, routes it through the AtBot
companion path for interpretation, and revalidates the returned delta against
the current head before commit. With AtBot unavailable the observation records a
deterministic `no_change`; it never invents progress.

**Explicit typed delta.** The model calls a tool the host registered — in
OpenClaw, `task_report_progress` — stating an item and its new status. There is
no interpretation step, so there is no interpreter to trust. A control-plane
operation the model cannot see is not this path: an unregistered tool is
invisible and is never claimed in the capability response.

The adapter itself never synthesizes a delta. A deterministic tool-result
mapping table in the bridge was the third option and is rejected: it would put
execution semantics where no profile could govern it and no version could pin
it, and it would drift per host.

**A conversation may only write to its own task.** Every host submission
resolves through its own session, and the submitted `task_id` must equal what
that session resolves to. Scope is not enough — one authorized scope routinely
holds several tasks, so a submission naming a sibling would otherwise pass every
scope and capability check. The refusal is non-disclosing: naming a task at
random reads the same whether it exists elsewhere or not, so guessing names is
not an existence oracle.

**Capability ceiling.** A host agent may propose and may request a lifecycle
change. It may not correct state, skip required work, cancel, delete, override
policy, register a profile, or bind a session. Those refusals happen on
capability grounds *before* delta content is evaluated, so a malformed
privileged request and a well-formed one produce the same answer. Cancellation
is absent from the host lifecycle contract entirely rather than checked later.

**Disabled is not shadow.** A disabled scope refuses immediately, before
identity resolution or content evaluation, disclosing nothing. A shadow scope
evaluates fully and records the decision it would have made, committing
nothing — which is what makes shadow a rehearsal rather than a silent no-op.

**Idempotency** is derived from stable host identifiers such as a run id and a
tool-call id, never from payload content, a clock, or randomness. A retried
hook, a duplicated tool result, and a replayed turn collapse to one decision.

## Fallback

Task state is local-first and dependency-light. With AtBot, semantic services,
and the network all unavailable, typed host and operator transitions still
validate, `no_change` is still recorded, current state is still delivered, and
completion gates still apply. Nothing about a failure widens scope, invents
progress, unlocks a schema, or bypasses a gate.

The offline `run_task_state_benchmark()` release gate covers the ten named
status, lifecycle, guard, overflow, and instruction-containment cases from the
spec using production serializers and policy helpers. It uses no model or
network and returns a digest-bound machine-readable report.

## Deletion and rollback

Forgetting a task removes its head, revisions and their content, provenance,
proposals, steps, and delivery records. What survives is a receipt carrying
counts and a digest of the goal, never the goal text. Deleting a subject clears
its task plane alongside its memory.

History may be deleted for verified erasure; it may never be rewritten. Revision
and provenance rows carry database triggers that abort any update.

The schema change is additive. Migrations `0070`–`0077` occupy Spec 007's
reserved block and are append-only. `tests/test_task_state_upgrade.py` drives
every supported published floor through create, advance, inspect, complete or
cancel, and delete, then proves that an interrupted upgrade recovers forward and
that no pre-existing column changed shape.

## Limitations

- AtMem returns state, decisions, guards, and evidence. It does not select or
  execute actions, and it is not a planner, scheduler, or workflow engine.
- Guard *enforcement* is unavailable. AtMem detects; only an adapter that
  reports having blocked an action could claim otherwise, and none does.
- A host-reported tool result is evidence, not independent proof. Stronger
  claims need a registered verifier.
- Instruction-shaped content in task data is contained structurally, not
  semantically. The tests prove delimiter and field containment; no test — and
  no claim here — asserts that a model will obey the framing.
- The measured p95 below 25 ms covers single-writer transition and context
  overhead on the supported SQLite profile, excluding model, tool, and verifier
  execution. Contended correctness is guaranteed separately and carries no
  timing claim.
- Task progress is not durable personal memory. A fact worth keeping must go
  through the ordinary memory proposal and admission path.
- Whether a host actually populates `sessionId`, `sessionKey`, or its owner
  signal at runtime is not proven by any test, and cannot be from outside the
  host. The declared surface is pinned per version, and everything fails closed
  on absence. That gap is the reason for the fail-closed rules, not an oversight
  in them.
- A withholding where no task resolved is not recorded as a delivery: deliveries
  are keyed to a task, and there is none. Inventing a placeholder would put a
  task id in the evidence that never existed. Those turns show up as the absence
  of a delivery, and as an unbound-conversation count in health.
