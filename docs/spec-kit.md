# Spec-driven development

AtMem uses GitHub Spec Kit 1.0.2 with the Lean preset and repository-local
Codex skills. The governing principles are in
`.specify/memory/constitution.md`.

Use Spec Kit for material changes to public contracts, authority boundaries,
persistent state, adapters, privacy guarantees, or release claims. Small
documentation, styling, dependency, and bounded bug fixes may use the normal
development workflow.

## Start a feature

Start a new Codex session after installing or refreshing the scaffold so the
repository-local skills are discovered. Use a stable directory such as
`specs/003-delegated-context-provider`, then run:

```text
$speckit-specify <feature outcome and motivation>
$speckit-clarify
$speckit-plan <architecture and technology constraints>
$speckit-tasks
$speckit-analyze
$speckit-implement
```

The Lean `speckit-specify` skill asks for the feature directory before writing
`spec.md`. Keep one bounded feature in each directory. Large roadmaps should be
split into independently testable feature specifications rather than one
long-running implementation plan.

## AtMem conventions

- Reference current architecture, contract, status, and release documents.
  Historical decisions remain available through Git history and must not be
  reconstructed as current requirements without verification.
- Put user outcomes, exclusions, acceptance scenarios, and compatibility
  requirements in `spec.md`.
- Put architecture, schemas, provider boundaries, migrations, and verification
  strategy in `plan.md`.
- Make every task independently verifiable and bind public claims to tests.
- Run `speckit-analyze` after task generation and before implementation.
- Treat constitution changes as reviewed architectural changes, not incidental
  edits made to satisfy a feature.

## Refresh the tooling

The CLI is installed as a user-level tool. Refresh it deliberately to a reviewed
official release, then use Spec Kit's own integration refresh flow rather than
copying prompt files by hand. Check the installed version and active preset with:

```bash
specify version
specify preset list
specify preset resolve speckit.specify
```

Machine-local feature selection is stored in `.specify/feature.json` and is
ignored by the repository-local `.specify/.gitignore`.
