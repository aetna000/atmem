# Research: Memory Integrity Benchmark Qualification

## Sources inspected

- Public repository: `iluxu/memory-integrity-benchmark`
- Frozen upstream commit: `ca8b430736f08c5dc66938b6e3b5319cea53ec8b`
- License: Apache-2.0
- License file SHA-256: `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`
- Package state inspected: `1.0.0rc1`
- Contract: Harness Specification v1 in the repository's methodology and adapter base
- Official categories: A, C, D, F, H, I and L; 100 trials per category
- AtMem target: published `atmem==2.3.5`
- AtMem wheel: `atmem-2.3.5-py3-none-any.whl`, 725654 bytes, uploaded
  `2026-09-20T15:27:09.403842Z`
- AtMem wheel SHA-256:
  `16e6fc5cf7a7f6964ce40ceffb124c7b386c08472ae5b027b8635a378ec62269`
- AtMem wheel URL:
  `https://files.pythonhosted.org/packages/e7/5b/15f013629fdbc0ef0712631a581f1af55e07dcc5134809df17a2fc0c26a0/atmem-2.3.5-py3-none-any.whl`

### Frozen attack-definition digests

| Category | SHA-256 |
|---|---|
| A | `8972af49e78005aedd77d314a74af082bb1645ef9a9ec929ea61cb750b91179d` |
| C | `b72c7c91e135898ff32f811ea2b8d1ee149b91fffef37c9599664e4c9523d418` |
| D | `23f0987b0efa4a8e2781923d3512382f9219d82ebc24a4416b00b11f892a73f8` |
| F | `8bed7c47c869eefe6ec8606595659a8acdcc9be95814a156b36887f8821af0d5` |
| H | `873e780dc98fbcf845caf933f92a501445dbbe4ed9cb7e0c5f5d59067847e73a` |
| I | `2d92d6089fb3ddbfa371466283857e482fc44f28f3bb585c3326f7f14949472b` |
| L | `176f77bedb2393d10b0b9fac89e1884a85091b8b6a39468ce5fa9e05cd6e81dd` |

The canonical evidence manifest must independently recalculate these identities
and reject any mismatch.

## Benchmark semantics

The benchmark tests persistent-memory integrity through seven declarative cases:

- A: an untrusted instruction must not become an active procedure.
- C: an earlier assistant hallucination must not resurface as authoritative fact.
- D: a summary derived from a tainted parent must preserve taint and remain
  non-authoritative.
- F: repetition must not increase authority.
- H: positive outcome credit must not erase taint or activate a procedure.
- I: valid explicit approval must activate a legitimate procedure.
- L: a synthetic secret must be absent from scoring persistent-memory and recall
  surfaces. Raw transcripts and immediate ingestion responses do not score.

Errors, unsupported operations and non-representable concepts are distinct from
security failures and successes. Aggregate claims are counter-derived from raw
trials.

## AtMem public surfaces considered

- `Memory.capture_source` and `Memory.submit_proposal` for scope-bound source
  capture, trust admission and quarantine.
- `Memory.submit_extraction_proposal`, `MemoryClass.PROCEDURE` and
  `ReviewService` for typed procedure proposals and human review.
- `Memory.memory_lineage`, `Memory.inspect`, `Memory.audit` and record raw fields
  for public/native evidence.
- `Memory.eligible_candidates`, `Memory.prepare_context_v1` and `Memory.recall`
  for governed recall and final lifecycle enforcement.
- `Memory.log_action` for outcome evidence that does not itself grant memory
  authority, subject to benchmark acceptance of this native operation.
- `Memory.reset_subject` and store closure for deterministic cleanup.

## Risks found before implementation

1. A v1 proposal can represent source trust and quarantine but does not carry a
   native `memory_class`. Calling such a record a procedure only in adapter state
   would be benchmark-created semantics and is prohibited.
2. The v2 extraction path carries `MemoryClass.PROCEDURE`, but its review API
   currently accepts an actor string. The adapter must prove native approval
   authority rather than treating a benchmark principal field as authorization.
3. `RecallRequest` has authority scope but no independent `purpose` field.
   `purpose_scoped_recall` must not be declared merely because the benchmark
   passes a purpose argument to the adapter.
4. Quarantining or encrypting a secret is not equivalent to category L's
   non-retention requirement. Secret scan must include public inspection of
   quarantined memory and other scoring persistent surfaces.
5. AtMem outcome evidence is intentionally non-authoritative. Category H may be
   representable using `log_action`, but the adapter must show that this is a
   native outcome record and that it cannot alter trust or lifecycle.
6. The upstream runner hardcodes four systems in registry, ordering, reporting
   and helper logic. Adding AtMem requires a tested generalization without
   changing existing results.

## Decisions

- Run a capability spike against the installed wheel before declaring any
  capability.
- Prefer an explicit non-representable status over adapter-side emulation.
- Treat a failure in category L as evidence, not an automatic release defect;
  classify it against AtMem's documented contract before deciding on a product
  correction.
- Preserve first-run evidence even when later adapter, harness or product fixes
  produce a better result.
- Publish only narrow integrity conclusions. The suite does not establish
  retrieval quality, speed, compliance, certification or comprehensive security.
