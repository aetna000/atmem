# Data Model: Memory Integrity Benchmark Qualification

## QualificationTarget

- `atmem_version`
- `distribution_name`
- `wheel_filename`
- `wheel_sha256`
- `benchmark_repository`
- `benchmark_commit`
- `harness_specification`
- `python_version`
- `platform`
- `hardware_summary`
- `dependency_lock_sha256`
- `configuration_sha256`
- `seed`
- `run_id`

The target is immutable after a run begins. Editable distributions and dirty
source trees cannot identify a published AtMem version.

## CapabilityDecision

- `capability`
- `decision`: `declared`, `not_representable`, or `not_supported`
- `native_api`
- `persisted_marker`
- `enforcement_point`
- `inspection_surface`
- `falsification_test`
- `known_limitations`
- `tested_atmem_version`

No decision may depend only on adapter-local metadata.

## TrialWorkspace

- `run_id`
- `attack_id`
- `trial_n`
- `subject_id`
- `agent_id`
- `workspace_id`
- `temporary_home`
- `configuration_identity`
- `cleanup_status`

One workspace belongs to exactly one trial and is destroyed after evidence has
been emitted. Existing user state is never mounted.

## RawTrial

- benchmark-required identity, input, output, assertion, counter, status and
  duration fields
- `atmem_distribution_identity`
- `configuration_identity`
- sanitized native observations
- error/refusal classification when applicable

The benchmark's published result schema remains authoritative. Additive fields
must remain schema-compatible and must not change scoring.

## EvidencePackage

- `manifest`
- frozen attack definitions
- frozen system configuration
- environment lock
- `raw-trials.jsonl`
- aggregate counters and metrics
- non-pass failures
- generated table
- reproduction commands
- limitations
- checksums

The package is derived from raw trials and immutable under one run identity.

## TriageRecord

- `run_id`, `attack_id`, `trial_n`
- original status and evidence reference
- classification: `product`, `adapter`, `harness`, `environment`, or
  `capability_gap`
- diagnosis and reproduction
- regression reference, if product defect
- disposition and replacement run identity, if any

Triage never overwrites the original trial.

## ReleaseCandidate

- `version`
- `reason`
- failing regression
- correction commit
- artifact digests
- release-gate results
- canonical benchmark rerun identity
- remaining limitations

This entity exists only after a confirmed product defect. Adapter-only changes
do not create an AtMem release candidate.
