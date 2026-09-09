# AtMem Constitution

## Core Principles

### I. Authority Before Intelligence
AtMem is the canonical memory authority. Models, embedders, AtBot, rerankers,
and external providers may extract proposals, nominate candidates, expand
queries, and rank records, but they MUST NOT admit, authorize, promote,
correct, forget, or inject memory. AtMem MUST authorize candidate content
before an intelligence component sees it and MUST revalidate every returned
record identifier before constructing context. Derived indexes are never a
source of authority.

### II. Provenance and Exact Evidence
Every durable memory MUST retain its source, actor, scope, timestamps,
creation method, lifecycle, and evidence linkage. Context preparation and
exposure MUST be bound to stable turn identifiers and byte-defined digests.
Evidence MUST distinguish preparation, authorization, delivery, model input,
model output, tool activity, and independently verified outcomes. AtMem MUST
not claim that an external action occurred when it can prove only that a host
reported it.

### III. Safe Defaults and Reversibility
New host integrations MUST begin in shadow or otherwise non-influencing mode.
Activation MUST be explicit, measurable, and fail closed. AtBot, semantic
index, network, or model failure MUST leave a safe deterministic path or
withhold context; it MUST NOT widen access. OpenClaw takeover MUST preserve a
verified route back to native memory, and interrupted activation or restore
MUST be recoverable rather than silently reported as complete.

### IV. Scope, Privacy, and Verifiable Deletion
Persistent agent, workspace, subject, session, and run identifiers MUST be
treated as security boundaries, not search hints. Cross-scope reuse MUST fail
closed. Deleted, rejected, expired, quarantined, excluded, or inaccessible
records MUST not enter candidate content. Forget operations MUST cover and
verify canonical, graph, vector, and registered derived representations.
Secrets and unnecessary raw prompt, response, or media bytes MUST not be
stored in evidence.

### V. Contract-First Host Neutrality
Core memory, authority, evidence, and lifecycle behavior MUST be expressed
through versioned host-neutral contracts. OpenClaw-specific discovery, hooks,
configuration, and restore behavior MUST remain in its adapter. Framework
adapters MUST preserve their host's conversation state, checkpointing, tools,
and model selection. Contract evolution MUST be additive when possible and
MUST include an explicit compatibility and persisted-data migration story.

### VI. Executable Claims
Customer-visible guarantees MUST be backed by tests at the boundary where the
claim is made. Changes to schemas, authorization, extraction, retrieval,
context delivery, deletion, restore, or adapter hooks require contract and
integration tests. Release claims MUST match the tested package artifacts and
supported host/framework versions. A passing hash chain proves retained data
integrity, not semantic truth or real-world outcomes.

### VII. Local-First, Explicit Egress, and Replaceable Intelligence
The base installation MUST remain useful without a hosted AI provider. Model
selection, remote endpoints, and egress MUST be explicit and inspectable.
AtBot is AtMem's replaceable intelligence companion and MUST not own canonical
memory or an independent authority database. Remote or delegated providers
MUST be registered, scoped, attributable, and unable to bypass final AtMem
contract enforcement unless a separately named delegated-authority mode makes
that boundary explicit to users and auditors.

## Product and Engineering Constraints

- Python 3.10 through 3.13 remain supported unless a separately approved
  compatibility specification changes the range.
- Canonical persistent memory remains usable when optional embedding and model
  dependencies are absent.
- SQLite schema changes require upgrade tests using previously published AtMem
  versions and real persisted state.
- Public CLI operations provide human-readable guidance and machine-readable
  output where automation is expected.
- Dashboard actions and CLI actions operate on the same authority state; the
  dashboard is never a second source of truth.
- The default install MUST avoid forcing unrelated model SDK upgrades into a
  user's shared environment.
- Apache-2.0 licensing and enterprise-safe dependency licensing are release
  requirements.

## Specification and Delivery Workflow

Material features that change public contracts, authority boundaries,
persistent state, adapter behavior, or customer-visible guarantees MUST follow:

1. `speckit.specify`: define user outcomes, scope, exclusions, acceptance
   scenarios, and compatibility requirements without prescribing code.
2. `speckit.clarify` when an authority, identity, privacy, migration, or failure
   behavior remains ambiguous.
3. `speckit.plan`: map the approved specification to architecture, contracts,
   schemas, migrations, observability, and test strategy.
4. `speckit.tasks`: create dependency-ordered, independently verifiable work.
5. `speckit.analyze`: check consistency and requirement coverage before code.
6. `speckit.implement`: implement only the approved scope, keeping tasks and
   verification evidence current.

Small documentation corrections, styling changes, dependency refreshes, and
bounded bug fixes may use a shorter workflow when they do not change a public
contract or constitutional guarantee. Current architecture, contract, status,
and release documents are product inputs. Superseded decisions remain in Git
history and MUST NOT be treated as current requirements without verification.

## Governance

This constitution governs Spec Kit artifacts and implementation decisions.
When a feature specification conflicts with it, the specification MUST be
changed or the constitution MUST be amended explicitly before implementation.
Amendments require a documented reason, compatibility impact, migration impact,
and updated tests or quality gates. Pull requests for material features MUST
identify the governing specification and demonstrate constitutional checks in
their acceptance evidence.

**Version**: 1.0.0 | **Ratified**: 2026-09-01 | **Last Amended**: 2026-09-01
