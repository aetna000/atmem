# Contract: AtMem Memory Integrity Qualification Evidence v1

## Required publication files

Every published run directory must contain:

1. `manifest.json` — exact benchmark and AtMem artifact identities, seed,
   environment, configuration digest, trial counts and generation commands.
2. `raw-trials.jsonl` — benchmark-schema-valid per-trial evidence.
3. `aggregate.json` — counters and metrics generated only from raw trials.
4. `failures.jsonl` — every non-pass/error record with immutable raw reference.
5. `table.md` — generated human-readable table.
6. `environment.lock` — frozen benchmark environment.
7. `reproduce.md` — bounded clean-install and regeneration commands.
8. `LIMITATIONS.md` — capability gaps, environment and claim boundary.
9. `SHA256SUMS` — checksum for every publication file except itself.

## Manifest invariants

- Exactly one AtMem distribution identity and one benchmark commit.
- Exactly 700 canonical trials: 100 each for A, C, D, F, H, I and L.
- Unique `(system, attack_id, trial_n, seed)` tuples.
- `atmem==2.3.5` imports from installed distribution paths for the initial run.
- No dirty benchmark tree in a canonical run.
- All generated reports name the same configuration and raw-trial digest.

## Sanitization invariants

- No real secret or private user content is used.
- Synthetic secret plaintext is absent from published artifacts; its digest is retained.
- Machine-specific absolute paths are absent.
- Sanitization cannot delete a trial, assertion, channel, error or denominator.
- If AtMem's encrypted Agent Black Box retains content in a benchmark-excluded
  evidence/transcript channel, `LIMITATIONS.md` names that channel and explains
  that category L measures absence only from its scoring memory/recall surfaces.
  It must not claim the content is absent from all AtMem storage.

## Status invariants

Only `PASS`, `FAIL`, `PARTIAL`, `NOT_REPRESENTABLE`, `NOT_SUPPORTED` and
`ERROR` are valid. `ERROR` never counts as either security success or failure.
Missing native semantics use a representability status, not adapter emulation.

## Release decision invariant

A benchmark non-pass creates a triage record, not automatically a product
release. Only a confirmed product defect with a failing AtMem regression opens
the prerelease correction path.
