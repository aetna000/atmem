# JEV-Lab: governed memory judgment experiment

## Overview

JEV-Lab is an isolated, reproducible experiment that demonstrates how
TypeSafe's Jev model can help AtMem evaluate retrieved memory candidates without
becoming an authority over memory. It uses a synthetic, non-production subject,
records no API secret, and produces a self-contained report with metrics and
visuals. The experiment is opt-in and must still produce an offline baseline if
the API is unavailable.

## User scenarios

### US1 — Show the value of Jev safely

As an AtMem maintainer, I run one command and receive a side-by-side comparison
of AtMem's deterministic candidate ranking and Jev-assisted judgment, including
precision/recall-style metrics, latency, and representative decisions.

Acceptance: the command exits successfully with `JEV_API` present or absent,
writes JSON and an HTML/SVG report, and clearly labels live versus offline mode.

### US2 — Preserve AtMem authority

As an auditor, I can see that Jev only scores nominated candidates. AtMem still
performs candidate generation, scope filtering, final thresholding, and context
assembly.

Acceptance: every decision records the candidate IDs, question contract, model
ID (when live), AtMem final decision, and a digest of the evaluated state; no
Jev answer can admit a memory by itself.

### US3 — Reproduce and inspect the experiment

As a researcher, I can rerun a fixed synthetic dataset with a seed and compare
results without network access. The report includes dataset version, seed,
configuration, counts, timing, and limitations.

Acceptance: offline runs are deterministic for the same seed; live runs never
claim reproducibility and record the returned pinned model ID and API error or
latency when applicable.

## Functional requirements

- **FR-001**: Provide a versioned synthetic dataset with relevant, distractor,
  stale, contradictory, and permission-ineligible memory candidates.
- **FR-002**: Run AtMem's deterministic baseline ranking and a Jev-assisted
  scoring path over the same candidates and questions.
- **FR-003**: Send only the minimum structured state required for the experiment
  to `https://api.typesafe.ai/v1/systemone`; read `JEV_API` from the environment
  and never write or print its value.
- **FR-004**: Require a pinned model ID by default (`jev-1.13.0`) and record the
  response model ID; aliases may be selected explicitly for exploratory runs.
- **FR-005**: Keep AtMem's final authority local: scope, lifecycle, exclusion,
  provenance, threshold, and context decision remain deterministic and are
  recorded separately from Jev's recommendation.
- **FR-006**: Produce machine-readable JSON containing per-case decisions,
  candidate ranks, probabilities/confidence, latency, mode, digests, and summary
  metrics.
- **FR-007**: Produce an eye-catching, dependency-light HTML report with inline
  SVG charts: baseline versus Jev ranking, decision agreement, latency, and a
  candidate-to-authority flow diagram.
- **FR-008**: Provide an offline mode that uses a deterministic local judge and
  does not require network access, while visibly distinguishing it from live
  Jev results.
- **FR-009**: Add tests covering secret redaction, deterministic offline output,
  authority gating, request/response parsing, and report generation.
- **FR-010**: Keep all implementation under `research/jev_lab/`; do not modify
  production retrieval, memory authority, or dashboard behavior.

## Success criteria

- **SC-001**: A fresh checkout can run the offline demo with one documented
  command and obtain JSON plus HTML/SVG artifacts.
- **SC-002**: A live run with a valid key makes one batched Jev request per
  configured trial, records the pinned returned model ID, and redacts secrets.
- **SC-003**: The report makes the distinction between candidate relevance and
  AtMem authorization understandable without reading source code.
- **SC-004**: All JEV-Lab tests pass and existing AtMem retrieval tests remain
  unchanged and passing.

## Non-goals and limitations

This is not a production Jev adapter, a replacement for embeddings or graph
retrieval, a claim that Jev improves every workload, or a benchmark against
external vendors. Live evaluation sends synthetic state to TypeSafe; real user
memory must not be used by this experiment. Jev currently accepts text/JSON,
not raw media, so multimodal records are represented by synthetic metadata only.
