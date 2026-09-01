# Implementation Plan: Memory Quality Benchmarks

## Technical Context

- **Runtime**: Python 3.10–3.13, standard library first.
- **Existing boundaries reused**: `atmem.Memory`, host-neutral candidate/context contracts, deterministic extraction rules, local hashing semantic index, and AtBot companion configuration.
- **Persistence**: one temporary SQLite authority database and derived vector sidecar per benchmark case; no production schema change.
- **Public surface**: an `atmem benchmark` CLI group with human-readable output and `--json`/report-file support.
- **Data formats**: checked-in versioned JSON case, threshold, report, external-result, and comparison manifests.
- **Optional systems**: local embeddings, local/hosted AtBot, LongMemEval input, and Mem0 OSS are explicitly selected and never imported by the deterministic gate.
- **Testing**: pytest unit, CLI, schema/validation, deterministic integration, safety, adapter, and comparison tests.

## Constitution Check

| Principle | Design response |
|---|---|
| Authority Before Intelligence | Every executable case calls AtMem admission/retrieval/context boundaries. Optional systems only propose or rank; final scoring inspects AtMem-authorized records/context. |
| Provenance and Exact Evidence | Case results distinguish admitted records, retrieved candidates, and prepared context; dataset/configuration/report digests bind evidence without storing secrets. |
| Safe Defaults and Reversibility | The default profile is offline deterministic fallback in disposable state. Missing optional services produce explicit skips and never widen access. |
| Scope, Privacy, and Verifiable Deletion | Cross-scope and lifecycle cases are absolute safety gates. Reports contain fixture IDs and bounded diagnostics, not arbitrary private content. |
| Contract-First Host Neutrality | Benchmark contracts exercise `Memory` and host-neutral context APIs rather than OpenClaw-specific hooks. |
| Executable Claims | The deterministic benchmark becomes a pytest-backed release gate. Optional external results cannot be called comparable unless manifest identities match. |
| Local-First and Explicit Egress | No base dependency or network requirement is added. Local/hosted profiles require explicit selection and record egress/provider identity. |

No constitution amendment, authority migration, persistent-data migration, or compatibility break is required.

## Architecture

### 1. Versioned benchmark contracts

Create `atmem/benchmark/contracts.py` with validated immutable representations for:

- dataset/case input;
- execution profile;
- metric value including `value`, `unit`, and an explicit unavailable reason;
- case result and aggregate report;
- comparison compatibility.

Canonical JSON serialization sorts keys and hashes the normalized dataset, evaluated case IDs, relevant profile configuration, and scoring schema. JSON Schemas under `atmem/schemas/v1/` document the public case and report envelopes. Validation rejects unknown schema versions, duplicate IDs, missing expectations, and malformed external results.

### 2. Deterministic dataset and profile

Store at least 16 synthetic cases under `atmem/benchmark/data/`. Cases cover positive and negative forms of:

- rule extraction;
- correction/contradiction lifecycle;
- answerable recall;
- unrelated/no-answer withholding;
- incorrect injection;
- cross-subject and lifecycle privacy;
- instruction-as-memory poisoning;
- AtBot/semantic unavailability fallback.

Each case runs with a new temporary authority database. The benchmark never copies a developer's real AtMem state into output.

### 3. Runner and scorer

Create `atmem/benchmark/runner.py` to:

1. validate the dataset and selected profile;
2. establish isolated AtMem state;
3. apply typed fixture setup operations;
4. exercise admission, recall/candidate creation, and final context preparation as required by the case;
5. capture bounded observations and durations;
6. score case expectations;
7. aggregate precision/recall/F1, answerable recall, no-answer correctness, incorrect injection, privacy leaks, poisoning success, contradiction resolution, latency, token usage, and cost;
8. apply the checked-in release policy.

Safety thresholds are exact: zero privacy leaks, poisoned admissions, or unauthorized/incorrect injections. Other deterministic metrics must equal or exceed versioned floors in `atmem/benchmark/data/thresholds-v1.json`. Missing usage or pricing becomes an unavailable metric with a reason.

The report contains deterministic `quality` content and non-deterministic `observations` (timestamps/durations). A stable quality digest excludes volatile observations so repeated runs can be compared without pretending latency is byte-identical.

### 4. Optional execution profiles

Create `atmem/benchmark/profiles.py` with four named modes:

- `deterministic`: mandatory, offline, rules + local hashing fallback;
- `local-embeddings`: optional, uses the configured verified local semantic epoch;
- `local-atbot`: optional, uses an explicitly configured local AtBot provider;
- `hosted-atbot`: optional, requires explicit remote-egress configuration and provider credentials.

Unavailable optional profiles return a structured skip report and cannot pass the deterministic release gate. Provider/model/index identity, token accounting, supplied pricing metadata, and limitations are recorded separately per run.

### 5. External adapters and comparison

Create `atmem/benchmark/external.py` to:

- normalize locally supplied LongMemEval-style JSON/JSONL records into the benchmark external-case contract;
- count supported, skipped, and unsupported input with reasons;
- validate/import results from an external runner such as a pinned Mem0 OSS environment;
- compare reports only after dataset digest, case IDs, scoring schema, and relevant model configuration match;
- apply fixed metric directions, report every per-metric winner, and calculate the overall Pareto outcome (`atmem_better`, `mem0_better`, `equal`, or `mixed`).

Add a checked-in Mem0 environment manifest containing an exact OSS package version and setup command, but do not add Mem0 to AtMem dependencies or execute it in the default test suite. Do not vendor LongMemEval data.

### 6. CLI and documentation

Add these commands:

```text
atmem benchmark run [--profile ...] [--dataset ...] [--thresholds ...] [--output ...] [--json]
atmem benchmark import-longmemeval INPUT --output OUTPUT [--json]
atmem benchmark compare LEFT RIGHT [--output ...] [--json]
atmem benchmark profiles [--json]
```

`run` defaults to the checked-in deterministic dataset/profile and applies the release gate. Human output states pass/fail/skipped and failed metrics; JSON output contains the full report. Documentation separates reproducible offline evidence from optional and external evidence and lists limitations.

## File Structure

```text
atmem/
  benchmark/
    __init__.py
    contracts.py
    profiles.py
    runner.py
    external.py
    data/
      deterministic-v1.json
      thresholds-v1.json
      mem0-oss-v1.json
  schemas/v1/
    benchmark-cases.schema.json
    benchmark-report.schema.json
tests/
  fixtures/benchmarks/
    longmemeval-small.jsonl
    external-result-small.json
  test_benchmark_contracts.py
  test_benchmark_runner.py
  test_benchmark_external.py
  test_benchmark_cli.py
docs/
  benchmarks.md
specs/001-memory-quality-benchmarks/
  spec.md
  plan.md
  tasks.md
  checklists/quality.md
```

Existing files changed:

- `atmem/cli.py`: register and dispatch benchmark commands.
- `pyproject.toml`: package benchmark JSON data; no dependency changes.
- `README.md`: link the release gate and state evidence boundaries.
- `tests/test_documentation.py`: protect the public benchmark entry points.

## Verification Strategy

1. Contract tests reject invalid versions, duplicate cases, malformed metrics, secrets, and comparison mismatches.
2. Scoring tests use hand-calculated confusion matrices and unavailable usage/cost values.
3. Runner integration tests execute all deterministic categories in isolated state and assert absolute safety gates.
4. Repeatability tests run twice and compare case IDs, expected/observed quality values, aggregates, thresholds, and stable quality digest.
5. CLI tests cover default pass, deliberate threshold failure, report creation, JSON output, optional-profile skip, import, and compare mismatch.
6. Full existing tests confirm no authority, schema, packaging, CLI, adapter, or retrieval regression.

## Delivery Sequence

1. Contracts, schemas, fixture validator, and deterministic data.
2. Scorer, runner, thresholds, and offline release gate.
3. Optional profile detection and reporting.
4. LongMemEval import, external-result validation, and fair comparison.
5. CLI, documentation, packaging, and release-gate tests.
6. Full suite, Spec Kit convergence, and evidence review.

## Risks and Mitigations

- **Comparison inputs drift**: fail compatibility checks on data, case set, scoring, or model mismatch before selecting a winner.
- **An arbitrary aggregate hides trade-offs**: publish every per-metric winner and use Pareto dominance for the overall result; report `mixed` when each system wins something.
- **Latency makes reports unstable**: separate volatile observations from deterministic quality digest and publish environment facts.
- **Optional model dependencies pollute base installs**: detect availability lazily and never import optional SDKs in the deterministic path.
- **Benchmark accidentally bypasses authority**: score final AtMem context and inspect record lifecycle; do not score AtBot output as admitted or injected memory.
