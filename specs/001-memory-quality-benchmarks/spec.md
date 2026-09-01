# Feature Specification: Memory Quality Benchmarks

**Feature Branch**: `atbot`

**Created**: 2026-09-01

**Status**: Draft

**Input**: P0.1 from `todo.md`: establish repeatable memory-quality benchmarks and release gates for AtMem, including deterministic regression data, LongMemEval compatibility, execution-mode isolation, and a reproducible Mem0 OSS comparison.

## Overview

AtMem needs evidence for claims about memory extraction and retrieval quality. This feature gives maintainers and evaluators one repeatable benchmark workflow that measures quality, safety, performance, and cost without weakening AtMem's authority or requiring network access for the baseline release gate.

The benchmark distinguishes AtMem's deterministic fallback, local semantic retrieval, local AtBot intelligence, and hosted AtBot intelligence. It reports results by mode so a successful hosted-model run cannot hide a regression in the local-first product. It also defines a compatible external-run format for LongMemEval and a pinned Mem0 OSS comparison using the same selected dataset and model configuration.

## Clarifications

### Session 2026-09-01

- Q: Which benchmark failures should block an AtMem release? → A: Safety must be perfect; other quality metrics cannot fall below a checked-in baseline.

## User Scenarios & Testing

### User Story 1 - Run the release gate offline (Priority: P1)

As an AtMem maintainer, I can run a small deterministic benchmark without credentials, hosted models, or downloaded datasets and receive an unambiguous pass/fail result plus a machine-readable report.

**Why this priority**: AtMem's base installation and release claims must remain independently verifiable and local-first.

**Independent Test**: Run the benchmark release-gate command twice in clean temporary state and compare the normalized reports. Both runs must complete without network access, return the same quality counts, and enforce the same thresholds.

**Acceptance Scenarios**:

1. **Given** the base development installation and no model API keys, **when** the deterministic release gate runs, **then** it evaluates extraction, contradiction handling, recall, incorrect injection, privacy isolation, poisoning resistance, and degraded fallback behavior.
2. **Given** every required threshold is met, **when** the run completes, **then** the command exits successfully and writes a versioned JSON report identifying the code, dataset, mode, configuration, measurements, and limitations.
3. **Given** any required threshold is missed, **when** the run completes, **then** the command exits unsuccessfully and names each failed metric without suppressing the complete report.

---

### User Story 2 - Compare execution modes fairly (Priority: P2)

As an evaluator, I can run the same benchmark cases against deterministic fallback, local embeddings, local AtBot, and hosted AtBot and compare their results without mixing unavailable or skipped modes into passing results.

**Why this priority**: Memory quality depends on the configured intelligence path; aggregate claims are misleading unless each path is identified and isolated.

**Independent Test**: Select two available modes for the same dataset and verify that separate reports retain identical case identities while recording distinct provider, model, embedding, latency, token, and cost information.

**Acceptance Scenarios**:

1. **Given** a selected execution mode is available, **when** the benchmark runs, **then** every result is labeled with the exact mode and relevant provider/model/index identity.
2. **Given** a selected optional mode is unavailable, **when** the benchmark runs, **then** it is reported as skipped with an actionable reason and cannot count as a pass.
3. **Given** a hosted mode, **when** token or price information is unavailable, **then** usage and cost are reported as unknown rather than zero.

---

### User Story 3 - Evaluate standard and competitor datasets (Priority: P2)

As a researcher, I can adapt LongMemEval data and results and compare AtMem with a pinned Mem0 OSS setup using the same eligible inputs, query set, models, and scoring definitions, producing an explicit better, equal, worse, or mixed result.

**Why this priority**: External comparability is needed before publishing relative quality claims, but it must not make the offline release gate depend on a third-party service or dataset download.

**Independent Test**: Import a small fixture in the documented external-case format, run it through the common scorer for two system labels, and verify that the comparison rejects mismatched dataset/configuration identities.

**Acceptance Scenarios**:

1. **Given** a locally supplied LongMemEval-compatible file, **when** it is imported, **then** supported cases are normalized into the benchmark case contract and unsupported cases are counted with reasons.
2. **Given** AtMem and Mem0 result files with the same dataset and declared model configuration, **when** comparison runs, **then** the output names the winner for every comparable metric and states whether AtMem is better overall, Mem0 is better overall, both are equal, or results are mixed.
3. **Given** result files with different dataset digests, case sets, or declared model configuration, **when** comparison runs, **then** the tool refuses to describe the result as a fair comparison.

---

### User Story 4 - Reproduce a published result (Priority: P3)

As a user reading an AtMem quality claim, I can find the exact command, configuration, input identity, thresholds, output schema, and known limitations needed to reproduce it.

**Why this priority**: A benchmark is useful only when its evidence can be independently inspected and rerun.

**Independent Test**: Follow the checked-in benchmark guide from a clean checkout and reproduce the deterministic report without relying on undocumented local files.

**Acceptance Scenarios**:

1. **Given** a checked-in benchmark report, **when** a reviewer inspects it, **then** the report identifies its schema version, dataset digest, runner version, AtMem version, selected mode, thresholds, environment, and limitations.
2. **Given** a documented optional external run, **when** credentials, models, datasets, or dependencies are required, **then** the guide names them explicitly and separates them from the release gate.

### Edge Cases

- Empty, malformed, duplicate, or unsupported benchmark cases fail validation or are reported explicitly; they never disappear silently.
- A query with no authorized useful memory is scored as correct only when no memory is injected or returned as an answer.
- A semantically related but non-answering memory counts as incorrect injection when the expected result is withhold.
- Cross-subject, cross-workspace, deleted, rejected, quarantined, expired, or excluded memory counts as privacy leakage if exposed as a result or context candidate.
- An instruction embedded in user content or a retrieved memory must not be treated as an admission policy override; an admitted poisoned fact or unauthorized exposure is a failure.
- Contradictory or correcting statements are evaluated against an explicit expected current value and expected lifecycle outcome rather than raw record count alone.
- Timeouts, provider errors, missing models, and missing price metadata remain distinguishable from quality failures.
- Non-deterministic fields such as wall-clock timestamps and measured duration do not affect deterministic quality counts or report identity.

## Requirements

### Functional Requirements

- **FR-001**: The project MUST provide a versioned benchmark case contract and validator for small checked-in deterministic datasets.
- **FR-002**: The deterministic dataset MUST contain cases for extraction accuracy, contradiction or correction handling, recall, no-answer withholding, incorrect injection, scope privacy, poisoning resistance, and deterministic fallback.
- **FR-003**: The benchmark runner MUST execute the deterministic suite using isolated temporary AtMem state and MUST require no network access, API key, optional model SDK, or external dataset.
- **FR-004**: The runner MUST measure, where applicable, extraction precision/recall/F1, answerable-query recall, no-answer correctness, incorrect-injection rate, privacy-leak count, poisoning-success count, contradiction-resolution accuracy, latency, token usage, and model cost.
- **FR-005**: Metrics whose source data is unavailable MUST be represented as unknown or not applicable with a reason; they MUST NOT silently become zero.
- **FR-006**: Every run MUST identify the dataset name/version/digest, case IDs, runner/report schema version, AtMem version, execution mode, provider/model identity, embedding/index identity when applicable, thresholds, environment facts relevant to reproducibility, and limitations.
- **FR-007**: The runner MUST support distinct profiles for deterministic fallback, local embeddings, local AtBot, and hosted AtBot and MUST keep their results separate.
- **FR-008**: Unavailable optional profiles MUST be recorded as skipped with a reason and MUST NOT satisfy a release threshold.
- **FR-009**: A release-gate command MUST apply checked-in thresholds to the deterministic profile, exit nonzero on threshold failure or invalid input, and always emit the complete report when execution reaches scoring. Privacy, poisoning, authorization, and incorrect-injection safety thresholds MUST require perfect results; extraction, contradiction, and retrieval quality MUST meet or exceed checked-in non-regression floors.
- **FR-010**: Quality scoring MUST treat inaccessible or lifecycle-ineligible memory exposure as a privacy failure and MUST preserve AtMem authorization and revalidation boundaries during benchmark execution.
- **FR-011**: The benchmark MUST distinguish retrieval from injection: returning or considering a candidate is not proof of delivery, and incorrect-injection scoring MUST use the final prepared authorized context or explicit withhold decision.
- **FR-012**: The project MUST accept locally supplied LongMemEval-compatible input through a documented adapter that records supported, skipped, and unsupported cases without automatically downloading or redistributing the upstream dataset.
- **FR-013**: The project MUST define a versioned external-result contract usable by AtMem and a pinned Mem0 OSS harness or import path.
- **FR-014**: A comparison tool MUST reject comparison when dataset digest, evaluated case IDs, relevant model configuration, or scoring schema differ. For compatible results it MUST apply declared metric direction, name the winner or tie for each comparable metric, and produce one overall outcome: `atmem_better`, `mem0_better`, `equal`, or `mixed`. A system is better overall when it is no worse on every comparable quality/safety metric and strictly better on at least one; if each system wins at least one metric, the result is mixed.
- **FR-015**: Published commands and reports MUST state whether results are deterministic release-gate evidence, optional local-model evidence, optional hosted-model evidence, or external competitor evidence. A compatible external report MUST state its measured outcome directly, including “AtMem performed better than Mem0 on this benchmark” when FR-014 selects `atmem_better`.
- **FR-016**: Benchmark artifacts MUST avoid raw secrets and unnecessary private prompt/response content; case-level output MUST use fixture identifiers and bounded diagnostic text.
- **FR-017**: The deterministic release gate MUST be runnable through the repository's normal test tooling and documented as a release-quality check.
- **FR-018**: Adding the benchmark MUST NOT alter canonical memory schemas, authority rules, production retrieval behavior, or the base package dependency set.

### Key Entities

- **Benchmark Case**: A stable case identifier, category, input events, authenticated scope, query, expected memory/lifecycle/context outcome, and optional scoring metadata.
- **Benchmark Profile**: An execution mode plus provider/model, embedding/index, timeout, egress, and availability information.
- **Case Result**: The observed admission, retrieval, context, privacy, poisoning, timing, usage, and diagnostic outcome for one case.
- **Benchmark Report**: A versioned aggregate containing run identity, dataset identity, profile identity, metric values, thresholds, failures, skips, limitations, and case results.
- **Comparison Manifest**: The common dataset, case set, scoring, and model configuration required to compare two labeled reports.

## Success Criteria

### Measurable Outcomes

- **SC-001**: The deterministic release gate runs from a clean development installation without network access or credentials and returns the same case count and quality metric values across two consecutive runs.
- **SC-002**: The checked-in deterministic dataset includes at least one positive and one negative case for every category in FR-002, with at least 16 total cases.
- **SC-003**: The release gate requires 100% scope-privacy success, zero poisoned-memory admissions, zero unauthorized injections, 100% deterministic-fallback completion, and extraction, contradiction, and retrieval results at or above the checked-in baseline values.
- **SC-004**: Every required quality metric in FR-004 is present in the report with a numeric value or an explicit unknown/not-applicable reason.
- **SC-005**: Every case result traces to a stable case ID, expected outcome, observed outcome, and pass/fail reason; aggregate counts equal their case-level inputs.
- **SC-006**: A deliberately altered dataset digest or case set causes comparison validation to fail; compatible controlled fixtures deterministically produce AtMem-better, Mem0-better, equal, and mixed outcomes.
- **SC-007**: Automated tests cover schema validation, scoring math, threshold failure, optional-profile skipping, privacy/poisoning failures, report determinism, external import behavior, and comparison compatibility.
- **SC-008**: The benchmark documentation provides copyable commands for the offline release gate and each optional profile, plus a limitations section that prevents unsupported Mem0 or LongMemEval claims.

## Out of Scope

- Comparing AtMem and Mem0 runs that do not share the required dataset, cases, scoring schema, and model configuration.
- Bundling, downloading, or relicensing the full LongMemEval dataset.
- Making Mem0, LongMemEval, hosted providers, local model servers, or optional embedding libraries required by the base installation or deterministic release gate.
- Changing AtMem extraction, retrieval, ranking, admission, authorization, or storage behavior to improve scores; those changes belong to later P0 specifications.
- Establishing production-scale throughput targets or storage-backend benchmarks.
- Publishing model pricing without explicit run-time pricing metadata.

## Assumptions

- P0.1 delivers the measurement and release-gate foundation; it exposes quality gaps but does not silently tune product behavior.
- The deterministic profile uses existing AtMem public or stable host-neutral contracts and checked-in synthetic fixtures.
- Optional local and hosted profiles are enabled explicitly and may be executed outside continuous integration.
- LongMemEval and Mem0 versions/configurations are pinned in reproducibility manifests when their optional runs are performed.
- Raw upstream datasets and third-party outputs remain outside source control unless their licenses explicitly allow redistribution.
