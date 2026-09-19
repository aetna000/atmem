# Production memory benchmark track

## Overview

AtMem needs benchmark evidence that is suitable for production-quality claims,
not only synthetic demonstrations. This feature creates a reproducible,
license-aware benchmark harness. LoCoMo is the first executable adapter;
LongMemEval and BEAM are registered as staged adapters with explicit readiness
gates so the project never reports a missing corpus as a passing result.

## User scenarios

### US1 — Run LoCoMo retrieval evaluation

As a maintainer, I provide a local path to the official LoCoMo dataset and run
the AtMem adapter against the complete corpus or an explicitly named split. The
runner ingests the transcript through AtMem, recalls for each gold question, and
reports evidence recall, MRR, p50/p95 latency, throughput, errors, and resource
metadata.

### US2 — Audit a benchmark claim

As a reviewer, I can inspect a manifest that identifies the source URL, license,
immutable dataset digest, split, ingestion mode, AtMem version, configuration,
hardware, seed, and evaluator version. A report with missing provenance is
invalid or visibly marked exploratory.

### US3 — Compare fairly

As a researcher, I can run the same corpus and questions against the AtMem
baseline and an explicitly configured Jev-assisted nomination path without
changing the authority gate. The report keeps retrieval quality separate from
answer-generation quality and does not compare unlike workloads.

### US4 — Stage long-history and scheduling benchmarks

As a maintainer, I can see readiness and exact acquisition instructions for
LongMemEval and BEAM. The CLI refuses to call these production-ready until the
corpus, split, scoring contract, and resource gates are present.

## Functional requirements

- **FR-001**: Define a versioned manifest schema containing corpus identity,
  source, license, digest, split, task, ingestion/evaluation mode, and claim
  status.
- **FR-002**: Load official LoCoMo JSON without copying dataset contents into
  the repository; reject malformed records and missing evidence IDs.
- **FR-003**: Ingest LoCoMo transcript turns through the real AtMem `Memory`
  authority and map returned records back to dialogue IDs.
- **FR-004**: Compute retrieval-only Recall@1/5/10, MRR@5, evidence coverage,
  p50/p95 recall latency, ingest throughput, errors, and resource metadata.
- **FR-005**: Support a fixed, explicitly named split and a deterministic
  sample/seed for development; full-corpus runs must be labelled separately.
- **FR-006**: Emit raw JSON results and a human-readable Markdown summary with
  exact configuration and limitations.
- **FR-007**: Reject production-level status unless the manifest, immutable
  digest, full or named held-out split, baseline, and systems metrics exist.
- **FR-008**: Register LongMemEval and BEAM manifests and report `staged` until
  their adapters and scoring contracts are implemented.
- **FR-009**: Never download, commit, or send licensed corpus contents to a
  hosted model automatically; external egress requires an explicit flag.
- **FR-010**: Add tests for schema validation, digest mismatch, evidence mapping,
  metric calculation, missing-corpus refusal, and report claim downgrade.

## Success criteria

- **SC-001**: The full LoCoMo corpus can be evaluated from a user-provided local
  file with no source changes and produces reproducible machine-readable output.
- **SC-002**: A LoCoMo report includes all required provenance and quality/system
  metrics and is labelled `production-candidate` only when gates pass.
- **SC-003**: Missing, altered, or partial data cannot produce a production-level
  claim.
- **SC-004**: Existing AtMem retrieval and authority tests remain passing.
- **SC-005**: LongMemEval and BEAM are visible as staged, never falsely reported
  as completed.

## Non-goals

This feature does not redistribute LoCoMo, LongMemEval, or BEAM data, claim
state-of-the-art performance, or add a hosted evaluator by default. End-to-end
answer-generation scoring is a later track; this first adapter measures
retrieval and evidence coverage directly.
