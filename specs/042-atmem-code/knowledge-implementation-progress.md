# Knowledge implementation progress — 2026-10-17

Worktree: `feature/atmem-code-2.3.9`, based on `afdefbb` plus local changes.
No release, tag, merge or published benchmark is claimed.

## Implemented and locally verified

- Versioned source/snapshot/object/relation/attempt/execution/applicability and
  capability contracts. Source paths remain repository-relative; probabilities
  or Laya classification are not introduced in this Code branch.
- Mechanically incorporated pure upstream query/renderer and identity/relation
  helpers, with pinned hashes, notices and a reproducible import check. Original
  method differential fixtures cover eight operations; broad language/platform
  parity is still unqualified.
- Optional pinned Enola Docker worker: offline, no source/owner-home mounts,
  read-only root, unprivileged execution, capability/PID/memory/CPU limits and
  tmpfs-only source/output processing. A public-file extraction passed with two
  facts, one relation and zero reported parse errors. This is a boundary diagnostic,
  not repository/task quality evidence.
- Existing encrypted Code document storage holds coherent generations, original
  source/artifact bytes, extraction coverage and pending/completed jobs. Failed
  workers and changed-source publication races leave no partial active generation.
- Authenticated attempt observations use existing typed admission. A signed
  producer report binds command, source, environment, result and attempt. It does
  not independently prove execution, semantic truth or a generally successful fix.
  Local Python identity and an explicitly approved producer-declared tool
  environment are distinguished. The latter must be refreshed by the trusted
  producer, not inferred from an agent's prose.
- Source/config anchored applicability works without graph enablement. Unrelated
  files can change; affected files, known dependency configuration, worktree or
  environment changes withhold evidence. Whole-file hashes are conservative and
  can withhold useful lessons after unrelated edits within the same file.
- Rich structure and existing memory use the same context byte ceiling, with a
  source-generation recheck at submission. The syntax-only fallback retains its
  distinct label.
- CLI/application/dashboard commands provide rich indexing, eight typed query
  operations, current coverage and bounded source excerpts. A browser Explorer
  surface is implemented; browser/accessibility and five-user study gates remain.
- Versioned encrypted v2 bundles retain typed sources/units and new project
  documents; v1 reading remains supported. Experience deletion removes its copies
  and retained receipts when unshared; an opaque tombstone prevents replay.
  Bundle round trips and deletion checks pass. Cross-machine source applicability
  still requires an explicit verified identity rebind; import does not assert that
  an old worktree is the new worktree.

## Verification so far

- Broad Code/knowledge/replay portable selection: 268 passed, 15 native-host
  probes explicitly skipped. Native shell isolation/network checks additionally
  passed with a working local-network positive control; no inference was used.
  A run including native host probes initially had two Grok/Muse failures from
  the fixture importing an unrelated globally installed AtMem before selecting
  the tested checkout. Pinning the fixture import first corrected both: the two
  actual controlled Grok/Muse journeys pass. The complete combined rerun then
  passed: 282 passed, one pre-existing expected failure. None of these controlled
  fixtures upgrades normal adapter activation claims.
- `node --check` accepts the Explorer JavaScript.
- Local wheel build succeeds; inspection found the new modules and all selected
  upstream legal materials. The local preview still has package version 2.3.8;
  it is not the public 2.3.8 artifact or a new published release. A final wheel
  must be rebuilt after any product edits before a future installed claim.
  The separately frozen local wheel passed installed Click structure and real
  experience diagnostics; the reduced pilot verifies every installed product
  file against that exact wheel before dispatch.

## Still open

Full extraction/insight/delta coverage, dependency SBOM and binary/source build
reproducibility; all-source lifecycle/crash/deletion/restore coverage; disjoint
full normal-host qualification; browser and cross-platform qualification; the
five-human formative study; complete application-issued capability receipts.
The disjoint authentic experience journey and installed structural preparation
have passed. The actual Click comparison completed 20 attempts under the explicit
reduced benchmark-integration assurance, not normal automatic Codex hooks:
structure 7/10 versus combined 6/10, eight admitted observations but zero earlier
memory exposures, identical context digests in all ten pairs. No memory benefit
or harm can be attributed. The qualified report is
`RandD/2026-10-17-click-structure-experience-final.md`.
Task fixtures and grader qualification are never reported as solver results.
