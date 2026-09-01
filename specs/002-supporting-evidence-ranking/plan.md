# Implementation Plan: Governed Supporting-Evidence Ranking

## Technical Context

- **Language/runtime**: Python 3.10–3.13; standard library only for the new ranker.
- **Canonical authority**: `atmem.memory.Memory` and `atmem.store.sqlite.SQLiteStore`.
- **Current retrieval path**: lexical/graph/semantic candidates → `_hybrid_memory_candidates()` → `create_candidate_set_v1()` canonical reload and authorization → `AtBotCompanionClient.query()` → `prepare_context_v1()` final revalidation.
- **AtBot boundary**: loopback companion protocol v1; AtBot can rank only AtMem-provided record IDs and owns no storage.
- **Persistence**: existing protocol candidate-set JSON; no SQLite schema change.
- **Public compatibility**: additive keys in `EligibleCandidate.signals`; existing format identifiers remain unchanged.
- **Benchmark**: optional LongMemEval-S runner with local Ollama embeddings and isolated pinned Mem0 environment; not part of base dependencies or offline release gate.

## Constitution Check

| Principle | Plan compliance |
|---|---|
| I. Authority Before Intelligence | Aggregation executes only inside `create_candidate_set_v1()` after canonical reload and every eligibility check. AtBot receives the resulting durable set; `prepare_context_v1()` remains the final authority boundary. |
| II. Provenance and Exact Evidence | Grouping uses canonical `source_session_id`; only an opaque scope-bound digest and bounded numeric signals persist. Candidate digest binds signals. |
| III. Safe Defaults and Reversibility | Deterministic ordering works without AtBot, a model, network, or optional dependency. Removing the additive signals restores previous consumer behavior. |
| IV. Scope, Privacy, and Verifiable Deletion | Ineligible records are filtered before grouping. Raw session identifiers never enter candidate signals, AtBot payloads, or audit payloads. Final generation/lifecycle/exclusion validation remains unchanged. |
| V. Contract-First Host Neutrality | Implementation lives in host-neutral retrieval and memory components. OpenClaw remains an adapter. Additive signal fields require no persisted migration. |
| VI. Executable Claims | Unit, contract, integration, fallback, privacy, benchmark, and full regression tests cover every changed boundary. |
| VII. Local-First and Replaceable Intelligence | Ranker is dependency-free and AtBot remains optional and non-authoritative. |

No constitution conflict or unresolved authority ambiguity remains; `speckit-clarify` is not required.

## Architecture

### 1. Dependency-free supporting-evidence ranker

Create `atmem/retrieve/support.py` with:

- `SUPPORT_AGGREGATION_VERSION = "supporting-evidence-v1"`;
- immutable, validated score normalization;
- a scope-bound opaque group digest computed from canonical subject, workspace, agent, and source-session material;
- record-local singleton group material when `source_session_id` is absent;
- `aggregate_supporting_evidence()` accepting only already-eligible internal rows;
- strongest-peer support mean and `record + 0.15 × peer support × (1 - record)` aggregation;
- singleton preservation and deterministic `aggregate_score`, original rank, record-ID ordering;
- a minimal public signal mapping with no raw provenance identifier.

The helper receives raw session provenance only in-process. Its return value contains no raw session identifier.

The optional offline LongMemEval report is a separate evaluation artifact. It
retains the dataset's evidence-session labels because its declared scorer and
per-case diagnostics require them; these fixture labels never enter AtBot,
product responses, audit events, or remote egress.

### 2. Aggregate after final eligibility validation

Modify `Memory.create_candidate_set_v1()`:

1. preserve existing canonical reload, active-state, exclusion, authority-scope, sensitivity/egress, and supplied-content checks;
2. build an internal eligible list containing canonical `source_session_id` and original retrieval score;
3. pass only that eligible list into the ranker;
4. construct durable `EligibleCandidate` objects in aggregate order;
5. store original and aggregate numeric signals inside `signals`;
6. include aggregation version and signal digest in the existing audit event;
7. preserve the existing candidate-set digest, expiry, generation, and JSON persistence.

`eligible_candidates()` remains the per-query candidate producer. Aggregation occurs at the final fused candidate-set boundary used by both dashboard and `control_prepare`, avoiding double aggregation across query expansions.

### 3. AtBot signal consumption with backward compatibility

Modify `packages/atbot/src/atbot/companion.py` to allowlist and copy only:

- `support_aggregation_version`;
- `record_score`;
- `support_score`;
- `aggregate_score`;
- `eligible_support_count`;
- `support_group_id`.

AtBot includes those fields in `eligible_memories` for local or hosted model ranking. It never receives `source_session_id`. Older companions ignore new signals and continue working. AtMem's client continues rejecting returned IDs outside the durable set.

### 4. Deterministic fallback

No new fallback branch is required. Both `AtBotCompanionClient._fallback()` and AtBot's deterministic provider choose the first candidate. Because the durable set is now sorted by aggregate score, fallback automatically consumes the improved order. Tests will make this dependency explicit.

If an AtBot model throws or returns malformed output, AtBot's internal fallback also selects the first aggregate-ranked candidate. If the companion is unavailable, AtMem does the same locally.

### 5. Evidence and diagnostics

Candidate `signals` are inspectable and already covered by `candidate_digest`. Add audit metadata containing:

- algorithm version;
- aggregation signal digest;
- grouped candidate count;
- supported group count.

Audit payloads contain neither memory content nor group/session identifiers. Product responses expose candidate signals through existing `used_memories` and retrieval structures.

### 6. Benchmark diagnostics

Extend `tools/run_longmemeval_retrieval.py` with:

- repeatable `--case-id` selection;
- per-case aggregation evidence for AtMem;
- session ordering using the same host-neutral aggregation helper after vector candidate eligibility;
- full `case_results` retained in generated external results;
- explicit separation between the fixed 12-case regression and larger held-out selections.

The checked-in comparison summary remains historical evidence. New result artifacts use a new filename rather than overwriting the earlier run.

## Data and Contract Design

No new dataclass or schema version is necessary. `EligibleCandidate.signals` is already an additive `dict[str, Any]` extension point.

Example additive signals:

```json
{
  "support_aggregation_version": "supporting-evidence-v1",
  "record_score": 0.71,
  "support_score": 0.69,
  "aggregate_score": 0.707,
  "eligible_support_count": 3,
  "support_group_id": "sgrp_<sha256-prefix>"
}
```

The candidate's top-level `score` equals `aggregate_score`. No raw source session appears in the persisted value.

## Score Rules

1. Reject boolean, NaN, and infinite inputs.
2. Convert finite numeric values and clamp them to `[0, 1]`.
3. Group eligible rows by scope-bound digest of canonical source session; missing session uses a record-local group.
4. For each record, sort the other eligible group scores descending and take at most two.
5. `support_score = mean(top_two_peers)`, or zero when there is no peer.
6. For group size one, `aggregate_score = record_score`.
7. Otherwise, `aggregate_score = record_score + 0.15 * support_score * (1 - record_score)`.
8. Round persisted numeric signals to six decimal places.
9. Order by descending aggregate score, ascending original rank, then record ID.

## Security and Failure Analysis

- **Cross-scope collision**: group digest material contains version plus full subject, workspace, agent, and canonical session values.
- **Identifier disclosure**: only a prefixed SHA-256 digest leaves the in-process helper.
- **Ineligible support poisoning**: aggregation is called only after every row passed canonical eligibility checks.
- **Duplicate query expansion**: final input is record-ID deduplicated before grouping.
- **Stale candidate support**: any memory mutation changes generation; `prepare_context_v1()` rejects the entire stale set.
- **Model widening**: AtMem client filters unknown IDs and final preparation rejects anything outside the durable set.
- **Non-finite JSON**: ranker rejects non-finite or boolean scores before candidate persistence.
- **Remote privacy**: sensitivity filtering precedes aggregation; raw provenance identifiers are never serialized.

## Implementation Touch Points

```text
atmem/retrieve/support.py                         new deterministic ranker
atmem/retrieve/__init__.py                        public internal exports
atmem/memory.py                                   post-authorization aggregation
packages/atbot/src/atbot/companion.py             bounded signal forwarding
tools/run_longmemeval_retrieval.py                focused runs and diagnostics
tests/test_supporting_evidence.py                  unit/security coverage
tests/test_contracts_v1.py                        additive contract evidence
tests/test_atbot_companion.py                      dashboard/control/fallback boundaries
packages/atbot/tests/test_companion.py             AtBot payload and ID constraints
tests/test_benchmark_external.py                   metric/result compatibility
docs/benchmarks.md                                 reproduction and interpretation
docs/examples/                                    new result artifact after live run
```

## Phases

1. Implement and unit-test the dependency-free aggregation helper.
2. Integrate it after canonical eligibility validation in durable candidate-set construction.
3. Forward bounded signals through AtBot and verify both fallback paths.
4. Add end-to-end dashboard and `control_prepare` authority tests.
5. Extend benchmark diagnostics and run focused, fixed, and held-out evaluations.
6. Run focused suites, AtBot package tests, deterministic gate, and full regression suite.

## Verification Strategy

- Unit tests for formula, clamping, singleton behavior, strongest-two-peer cap, ties, invalid values, opaque grouping, and scope separation.
- Memory contract tests for canonical reload, inactive/excluded/cross-scope/remote-sensitive non-influence, durable signal digest, and generation invalidation.
- AtBot tests proving signals are available to ranking while raw sessions and unknown IDs are absent.
- Control-plane tests proving dashboard query and `control_prepare` share the final aggregation boundary.
- Fallback tests with unavailable companion and provider exception.
- Benchmark tests for `--case-id`, per-case results, selection identity, score metrics, and the explicit offline-fixture boundary for dataset session labels.
- `python -m pytest -q` for the entire project and package-local AtBot tests.
- Live LongMemEval runs only after deterministic tests pass; results are evidence, not a reason to weaken gates.

## Rollback

The implementation introduces no schema or package migration. Rollback removes the helper call and additive signals. Existing persisted candidate sets expire after five minutes and remain readable because consumers already treat `signals` as an open mapping.
