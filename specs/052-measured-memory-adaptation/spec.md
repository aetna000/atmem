# Spec 052 — Measured Memory Adaptation

Status: specified, 2026-11-18. User authorized naming, research, implementation,
bounded real testing, and beta publication without further questions.

## Outcome
An owner can test whether a proposed change to an agent's memory instructions
improves independently verified task results over simple native-style baselines,
under identical runtime budgets. The application preserves failed and inconclusive
experiments. A successful retrieval, reflection, model score, or selected validation
result cannot certify learning, production activation, or general efficacy.

## Scope and scenarios
1. Owner preregisters a study, independent grader identity, immutable corpus,
   train/validation/test memberships, runtime identities, hypotheses and budgets.
2. Training observations inform at most one LOAD/OFFLOAD revision. The model only
   proposes bounded text; it cannot alter tools, authority, evaluation or code.
3. Both policies are compared on validation; the selected policy and starting
   memory are frozen before the final set is opened. Final evaluation compares
   no-memory, bounded raw training transcript, generic notes and revised notes.
4. The owner inspects exact retained trials and a report including all denominators,
   objective grades, paired outcomes, errors, uncertainty and total resources.
5. A crash/restart cannot replay paid requests or change final policy to improve
   the published score. Incomplete work remains unknown rather than successful.

## Functional requirements
- FR-001: Owner-authorized fixed FeedbackScope, existing encrypted feedback store,
  application-only API. No model-facing write/activation API or global default change.
- FR-002: Closed, finite, versioned manifest; unique case IDs, input/target digests,
  disjoint splits, episode identity, exact corpus/runtime/grader versions, resource
  ceilings, fixed selection and final assessment rules. Freeze before inference.
- FR-003: Separate actor input from hidden targets; trusted application verifier
  executes objective checks on actual output. No caller-supplied pass totals.
- FR-004: Generic incumbent plus at most one bounded text revision. Every arm gets
  the same task prompt, model settings, action/tools/context budgets. Account for
  proposal/construction calls in total resources. Include bounded transcript and
  no-memory controls; label these native-style, not actual Codex/Claude host runs.
- FR-005: Each arm starts validation/final from a frozen training-memory snapshot;
  final policies and memory cannot change after selection. Validation labels and
  final targets never become memory or proposal inputs. No final-set tuning.
- FR-006: Reserve trials and every potentially paid call durably before execution;
  pending/failed attempts consume budgets and cannot automatically retry. Enforce
  call, input/output token, worst-case USD, wall-time and retained-byte ceilings at
  actual entry points, not merely a checklist. Content-free provider errors.
- FR-007: Retain exact authorized model exchanges, tool arguments/results, outputs,
  memory and verifier evidence encrypted in the existing store. Inspection requires
  owner authority and audit. Keep credentials out of evidence. Test restart,
  authorization, tampering, scope isolation, ciphertext canaries and missing evidence.
- FR-008: Selection requires complete validation, higher objective reward and no
  accuracy regression over generic. Ties retain generic. Final reports distinguish
  candidate, selected policy, all controls, selection bias, missing/unknown trials,
  paired differences, clustered uncertainty and inconclusive efficacy.
- FR-009: A finite real public CL-Bench database pilot uses read-only SQLite with
  bounded operations, separate hidden-label grading, fresh agent context per task,
  preregistered split, drift stratum and cost. It is an adapted feasibility pilot,
  not a full official campaign, production qualification, or Meta reproduction.
- FR-010: Research review identifies primary papers, pinned available code/license,
  design alternatives, leakage risks and honest Meta comparability. No arbitrary
  evolved code, weight training, or new DolphinBench run in this release.
- FR-011: Ship SDK and executable study CLI/example with setup, opt-in, safe failure,
  retention, reproducibility, resources and limitations. Beta publication follows
  AGENTS.md and docs/release-coordination.md; website PR stays owner-reviewed.

## Success criteria and exclusions
- SC-001: Tests prove FR-001–008 at the real encrypted service and runner boundary.
- SC-002: One bounded external pilot completes or records an exact blocker; all
  attempted trials and costs are reported. Improvement is an empirical outcome,
  never a requirement satisfied by changing the threshold or rerunning the test.
- SC-003: A comparison table separates our matched pilot from Meta's published
  selected-harness and weight-distillation results. No cross-benchmark score ranking.
- SC-004: Release/install/upgrade/docs/bridge gates pass for an explicitly versioned
  beta. Website source refresh is prepared separately and never self-merged.

No canonical memory schema migration. Existing feedback format-4 opt-in and downgrade
constraints remain. The existing production qualifier remains inconclusive; this
experimental service cannot issue activation receipts. Local uncommitted Spec 051
and pgvector work is excluded from this isolated release.
