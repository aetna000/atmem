# Spec Kit help for AtMem

AtMem uses GitHub Spec Kit with the Lean preset and repository-local Codex
skills. In Codex, invoke a Spec Kit skill with the `$speckit-*` name.

## Recommended workflow

```text
$speckit-specify
        ↓
$speckit-clarify       optional when requirements are ambiguous
        ↓
$speckit-plan
        ↓
$speckit-checklist     optional requirements-quality review
        ↓
$speckit-tasks
        ↓
$speckit-analyze       consistency check before implementation
        ↓
$speckit-implement
        ↓
$speckit-converge      find and schedule anything still missing
```

Use one stable directory for each feature, for example:

```text
specs/001-delegated-context-provider/
├── spec.md
├── plan.md
├── tasks.md
└── checklists/
```

## `$speckit-constitution`

Creates or updates the principles that govern every specification and
implementation decision.

AtMem already has a constitution at `.specify/memory/constitution.md`. Use this
command only when deliberately changing a project-wide principle.

Example:

```text
$speckit-constitution Add a principle requiring every delegated authority
provider to use signed, turn-bound, replay-protected receipts.
```

Expected result:

- Updates the AtMem constitution.
- Records an amendment date and version.
- Propagates the changed principle into future feature decisions.

Do not use it merely to make one feature easier to implement.

## `$speckit-specify`

Defines what a feature must achieve and why, without deciding the implementation
technology. The Lean skill asks for the feature directory before writing.

Example feature directory:

```text
specs/001-delegated-context-provider
```

Example command:

```text
$speckit-specify Add an opt-in delegated context-provider mode. A registered
provider may authorize and prepare exact context for one turn. AtMem must verify
the provider envelope, deliver the exact bytes once, record provider and receipt
evidence, and avoid its normal second retrieval. Existing installations must
remain in AtMem-authority mode unless explicitly changed.
```

Expected result:

```text
specs/001-delegated-context-provider/spec.md
```

The specification should contain testable requirements, user scenarios,
success criteria, exclusions, failure behaviour and compatibility expectations.

## `$speckit-clarify`

Finds important ambiguity in the active feature specification, asks up to five
focused questions, and writes the answers back into `spec.md`.

Example:

```text
$speckit-clarify Clarify whether delegated-provider failure should withhold
context, fall back to AtMem retrieval, or be configurable per workspace.
```

Good clarification subjects for AtMem include:

- Who owns authorization?
- Which identity and scope fields are mandatory?
- What fails closed?
- Is fallback allowed?
- What is stored in evidence?
- What must remain byte-for-byte stable?
- How are replay and expiry handled?

Expected result: the active `spec.md` contains explicit answers rather than
leaving those decisions for the implementation phase.

## `$speckit-plan`

Translates the approved specification into a technical implementation plan.

Example:

```text
$speckit-plan Use a versioned delegated-context-v1 JSON contract, AtMem's
control store for trusted-provider configuration and replay protection, and the
existing control_prepare response for host delivery. Preserve the current
OpenClaw, Pydantic AI and LangGraph adapter interfaces. Include schema migration,
CLI, dashboard, audit evidence and contract-test strategy.
```

Expected result:

```text
specs/001-delegated-context-provider/plan.md
```

The plan should cover architecture, contracts, data model, migrations, security
boundaries, adapter changes, observability, compatibility and verification.

## `$speckit-checklist`

Creates a checklist that evaluates whether requirements are complete, clear and
internally consistent. It reviews the quality of the written requirements; it
is not a runtime test suite.

Example:

```text
$speckit-checklist Create a security and audit checklist covering provider
identity, scope binding, context hashes, receipt signatures, expiry, replay,
duplicate injection, fallback and evidence wording.
```

Expected result: a checklist under the active feature directory, normally:

```text
specs/001-delegated-context-provider/checklists/
```

## `$speckit-tasks`

Converts `spec.md` and `plan.md` into dependency-ordered, independently
verifiable work items.

Example:

```text
$speckit-tasks Generate contract-first tasks. Put schema and failing contract
tests before service code, then control-plane integration, OpenClaw delivery,
framework adapters, dashboard and CLI, compatibility tests, documentation and
release gates.
```

Expected result:

```text
specs/001-delegated-context-provider/tasks.md
```

Each task should name its expected files or boundary, dependencies and a clear
verification condition.

## `$speckit-analyze`

Performs a read-only consistency and coverage analysis across `spec.md`,
`plan.md` and `tasks.md`. Run it after task generation and before implementation.

Example:

```text
$speckit-analyze Check that every authorization, exact-delivery, replay,
fallback, backward-compatibility and audit requirement has a planned component
and at least one verification task.
```

Expected result: a report identifying missing coverage, contradictions,
ambiguous requirements, constitution violations and task-ordering problems. It
does not modify the implementation.

Resolve material findings before running `$speckit-implement`.

## `$speckit-implement`

Executes the approved tasks in dependency order and marks progress in
`tasks.md`.

Example:

```text
$speckit-implement Implement the active delegated-context-provider feature.
Preserve unrelated working-tree changes and stop if a required authority or
compatibility decision is absent from the specification.
```

Expected result:

- Code and documentation implement the approved scope.
- Tests and quality gates are run in proportion to risk.
- Completed tasks are marked in `tasks.md`.
- Unapproved architectural changes are not silently introduced.

## `$speckit-converge`

Compares the current codebase with the feature specification, plan and tasks,
then appends any remaining implementation work to `tasks.md`.

Example:

```text
$speckit-converge Verify that delegated mode works across OpenClaw, Pydantic AI
and LangGraph; exact bytes and receipts are correlated; duplicate injection is
prevented; and AtMem-authority mode remains unchanged.
```

Expected result: unfinished or partially implemented requirements become new,
actionable tasks. Run `$speckit-implement` again if tasks were added.

## `$speckit-taskstoissues`

Converts existing feature tasks into dependency-ordered GitHub issues.

Example:

```text
$speckit-taskstoissues Convert the delegated-provider tasks into GitHub issues.
Preserve requirement references, dependencies, acceptance checks and security
labels.
```

Expected result: actionable GitHub issues linked back to the feature artifacts.
This command changes external GitHub state, so use it only when the tasks have
been reviewed and issue creation is intended.

## Complete example

```text
# 1. Start the feature
$speckit-specify Add opt-in delegated context-provider mode to AtMem.
# When asked, provide: specs/001-delegated-context-provider

# 2. Resolve product and security ambiguity
$speckit-clarify Clarify authority, failure, fallback and receipt boundaries.

# 3. Design the implementation
$speckit-plan Use a versioned JSON contract and preserve existing adapter APIs.

# 4. Review requirement quality
$speckit-checklist Create security, privacy and audit checklists.

# 5. Break the plan into work
$speckit-tasks Generate contract-first, dependency-ordered tasks.

# 6. Check alignment before coding
$speckit-analyze Check requirements, plan and task coverage.

# 7. Build and verify
$speckit-implement Implement the active feature tasks.

# 8. Find anything unfinished
$speckit-converge Compare the implementation with all approved requirements.
```

## Spec Kit CLI maintenance

These are terminal commands, not Codex skills:

```bash
specify version
specify preset list
specify preset resolve speckit.specify
specify preset resolve speckit.plan
specify preset resolve speckit.tasks
specify preset resolve speckit.implement
```

They show the installed CLI version, enabled presets and the exact templates
that will be used.

## When not to use the full workflow

The complete workflow is intended for material features. A shorter normal
development flow is usually sufficient for:

- spelling and documentation corrections;
- small visual styling changes;
- routine dependency refreshes;
- bounded bugs that do not change a public contract;
- changes with no authority, persistence, privacy or compatibility impact.

If a change affects authorization, storage, deletion, context injection,
receipts, adapters, schema migration or a public guarantee, use Spec Kit.
