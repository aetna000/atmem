# Implementation Plan: Memory Integrity Benchmark Qualification

**Branch**: `benchmarking/memory-integrity-benchmark` | **Date**: 2026-09-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/benchmarking/001-memory-integrity-benchmark/spec.md`

## Summary

Qualify the immutable `atmem==2.3.5` PyPI wheel against Harness Specification
v1 of `iluxu/memory-integrity-benchmark`, using only public/native AtMem APIs.
The work is deliberately split across two repositories: this repository owns
AtMem boundary regression tests and the qualification record; a public fork of
the benchmark owns the adapter, runner generalization, raw results and generated
report. A capability spike precedes the adapter so unsupported concepts remain
`NOT_REPRESENTABLE` or `NOT_SUPPORTED` instead of being emulated.

The canonical run uses a clean Python 3.11 environment, a pinned benchmark
commit, the published wheel plus its digest, a deterministic seed, isolated
temporary AtMem Homes, one smoke trial per category and then all 700 official
trials. The first 2.3.5 evidence package is immutable. Only a confirmed AtMem
product defect starts a regression-first `2.3.6b1` correction path; adapter or
harness fixes do not cause an AtMem release.

## Technical Context

**Language/Version**: Python 3.11 canonical benchmark; AtMem regression matrix remains Python 3.10–3.13

**Primary Dependencies**: published `atmem==2.3.5`; Memory Integrity Benchmark v1; PyYAML; jsonschema; pytest

**Storage**: one temporary encrypted AtMem Home/SQLite store and derived indexes per trial; JSONL evidence in the benchmark fork

**Testing**: pytest unit/contract tests, installed-wheel smoke, benchmark schema/publication tests, 7-category smoke, 700-trial canonical run, checksum regeneration

**Target Platform**: canonical macOS arm64 run on the nominated host plus a clean Linux/Python 3.11 portability smoke where CI permits

**Project Type**: cross-repository library adapter, benchmark harness extension and evidence publication

**Performance Goals**: finish all 700 local trials without leaked processes or state; report durations and resource metadata, but make no latency-leadership claim

**Constraints**: no credentials or private data; no direct SQLite mutation; no adapter-created authority/taint/procedure/secret semantics; no existing `~/.atmem`; no change to attacks, scoring, seeds or competitor results

**Scale/Scope**: seven official categories (A, C, D, F, H, I, L), 100 trials each, one AtMem system adapter, one immutable publication package

## Constitution Check

*GATE: Must pass before implementation and be re-checked after adapter design.*

| Constitutional gate | Plan response | Status |
|---|---|---|
| Authority before intelligence | The adapter calls source capture, governed admission/review and governed recall. It never edits canonical rows or promotes based on harness metadata. | PASS |
| Provenance and replay | Every operation retains public native IDs and observations; the evidence package freezes attacks, config, versions, raw trials, report code and checksums. | PASS |
| Safe defaults | Unsupported concepts fail as explicit benchmark statuses. Optional intelligence and network services are not required. | PASS |
| Scope and deletion | Every trial receives a unique subject/agent/workspace and temporary Home; cleanup and cross-scope regression tests are mandatory. | PASS |
| Contract-first host neutrality | Mapping targets host-neutral AtMem Python contracts, not OpenClaw or dashboard internals. | PASS |
| Executable claims | Every declared capability has an adapter test and an AtMem boundary test; public conclusions name exact version, categories and denominators. | PASS |
| Local-first and egress | Qualification is local and provider-free. No benchmark content leaves the machine. | PASS |
| Production-level benchmark evidence | This is a public security-control benchmark, not a retrieval-quality/performance benchmark. Synthetic attacks support only the seven narrow integrity assertions; no production retrieval or broad security claim is permitted. | PASS |
| Release governance | 2.3.5 remains immutable. A product correction requires regression-first prerelease, full release gates and a complete rerun; benchmark success alone cannot publish a release. | PASS |

## Design Decisions

### 1. Two-repository ownership

- `aetnamem` owns the governing Spec Kit artifacts, public-contract regression
  tests, qualification summary and any real product correction.
- `aetna000/memory-integrity-benchmark` owns `AtMemAdapter`, its capability
  mapping, generalized registry/report plumbing, raw evidence and upstream PR.
- The benchmark adapter is not shipped inside the AtMem runtime and cannot
  become an alternate authority path.

### 2. Capability-decision gate

Before adapter implementation, create an executable matrix for all six benchmark
capabilities. Each row must identify the AtMem API, persisted native marker,
enforcement boundary, expected benchmark status and falsification test.

Provisional mapping to validate against the installed 2.3.5 wheel:

| Benchmark capability | Candidate native AtMem surface | Provisional decision |
|---|---|---|
| `source_trust` | `capture_source`, `submit_proposal`, record trust/lifecycle fields | representable |
| `derivation_tracking` | source evidence, related records/memory lineage, quarantined derivation | representable only if parent taint is natively inspectable and enforced |
| `procedural_memory` | v2 `MemoryClass.PROCEDURE`, review queue and committed record | representable only through the public review contract |
| `authority_gating` | `ReviewService.decide` plus scope/revalidation | representable if approval principal is validated rather than merely used as an actor label |
| `purpose_scoped_recall` | `RecallRequest` scope and governed context preparation | do not declare unless purpose itself has native enforcement |
| `secret_blocking` | sensitive admission/protected evidence behavior | do not declare unless the secret is absent from every scoring persistence surface |

The provisional table is intentionally conservative. In particular, actor names
are not authorization, quarantine is not deletion, encryption is not absence,
and adapter-local handle metadata is not a native AtMem procedure or taint label.
Category L additionally requires an explicit surface inventory: benchmark-scoring
persistent memory/recall surfaces are tested for absence, while any encrypted
Black Box evidence retained under the constitution is disclosed as a separate,
non-scoring evidence channel when the benchmark excludes it. No result may turn
that scoring exclusion into a broad "AtMem retained nothing" claim.

### 3. Trial isolation and artifact identity

Each trial creates a unique temporary directory and AtMem Home, fixed scope and
fresh key material. The adapter records AtMem distribution metadata and verifies
that imports resolve to the installed wheel, not this source checkout. Canonical
publication refuses a dirty benchmark tree, editable AtMem distribution, changed
attack digest or mixed configuration identity.

### 4. Honest first-run and triage ladder

1. Run conformance tests and one trial per category against 2.3.5.
2. Freeze and classify the first complete 700-trial result.
3. For an adapter defect, correct the adapter and publish a new run identity.
4. For a harness defect, propose a general fix and rerun without changing AtMem.
5. For a capability gap, retain the result and limitation; do not manufacture a pass.
6. For each confirmed product defect, write a failing AtMem regression first.
   Defects may share one beta only when triage shows one root cause or one
   inseparable correction; independent defects retain distinct triage records,
   tests and dispositions even if the user approves one coordinated release.
   Pass release gates, install the beta artifact in a clean environment and
   rerun all 700 trials.
7. Consider a stable release only after the prerelease artifact and full rerun
   are clean and the user explicitly proceeds with release completion.

### 5. Evidence and publication

The evidence package is generated, not hand-edited. It contains a manifest,
wheel and commit digests, frozen attacks/configuration, environment lock, raw
JSONL, aggregate metrics, failures, durations/resources, report, reproduction
commands, limitations and SHA-256 manifest. Raw evidence is append-only per run
identity. Synthetic secret plaintext and machine-local absolute paths are
rejected by publication tests.

## Project Structure

### Documentation (this feature)

```text
specs/benchmarking/001-memory-integrity-benchmark/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── qualification-evidence.md
└── tasks.md
```

### AtMem repository

```text
docs/benchmarks/
└── memory-integrity.md
tests/
├── test_benchmark_memory_integrity_contracts.py
└── test_installed_artifact.py
```

### Public benchmark fork

```text
adapters/
├── atmem_adapter.py
└── atmem/CAPABILITIES.md
runner/
├── run.py
├── report.py
├── merge.py
├── revise.py
└── combined_report.py
tests/
├── test_atmem_adapter.py
├── test_contract.py
└── test_publication.py
system-configurations/
└── adapter-sources.json
results/published/<run-id>/
├── manifest.json
├── raw-trials.jsonl
├── aggregate.json
├── failures.jsonl
├── table.md
├── environment.lock
├── reproduce.md
├── LIMITATIONS.md
└── SHA256SUMS
```

**Structure Decision**: Keep product contracts and regressions in AtMem while
placing benchmark-specific code and evidence in the benchmark fork. This avoids
a runtime dependency or benchmark-shaped product API and keeps upstream review
narrow.

## Verification Strategy

1. **Capability conformance**: public wheel API inspection plus falsification
   tests for each declared capability.
2. **Adapter contract**: deterministic reset, ingest, derivation, recall,
   procedure review, inspection, outcome handling and secret scan behavior.
3. **Harness regression**: existing systems and published inputs remain
   unchanged after registry/report generalization.
4. **Smoke**: seven trials, one per category, validates schema, isolation,
   sanitization, report regeneration and cleanup.
5. **Canonical run**: exactly 700 trials against clean-installed 2.3.5 with
   deterministic seed and frozen configuration.
6. **Product gates**: installed-artifact, invariant, authority, extraction,
   retrieval, lifecycle, deletion, evidence, encryption, integration and
   metadata suites remain passing.
7. **Independent reproduction**: clean clone/venv regenerates report and verifies
   checksums without this source checkout.

## Claude Read-only Review Protocol

Claude CLI receives only repository paths and public benchmark material. Every
prompt says read-only and prohibits file edits, mutation commands, credentials
and private data. The first review covers spec/plan/tasks, capability honesty,
anti-gaming and release logic. Material findings are applied and reviewed again
until no critical/high finding remains or a documented disagreement explains why
the recommendation would violate AtMem or benchmark contracts. After
implementation, Claude reviews the diff and test/evidence outputs; its agreement
is recorded as review evidence, never as a benchmark result.

## Complexity Tracking

No constitutional violation is requested. The cross-repository split is required
by ownership and upstream reproducibility, not an additional runtime component.
