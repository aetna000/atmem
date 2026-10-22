# Spec 046 — Evaluation-gated retrieval performance

Date: 2026-10-21. Target: AtMem 2.3.10; optional beta publication only after
release gates. Branch: `feat/retrieval-performance-2310`.
Status: offline foundations implemented; beta qualification in progress.
Research acceptance and benchmark-quality claims remain separately gated.

## Outcomes and scope

An agent receives relevant, temporally applicable and sufficiently complete
source-backed evidence, can request additional evidence, and can explain what
was found or remains unknown. Improve the actual product relative to current
Mem0, not a benchmark-specific adapter. Keep AtMem canonical authority and the
agent's responsibility for external actions.

Implement four pillars in order: (1) hybrid semantic/lexical retrieval and
reranking; (2) read-only agent-callable search and bounded follow-up;
(3) grounded preferences and temporal-state views; (4) semantic completeness
checking and complementary packing. Measure each before adding the next.

## User scenarios

- US1: An implicit request such as ordering a drink finds supported venue and
  option preferences, without converting one purchase into an asserted habit.
- US2: An agent missing evidence can search again within its existing scope and
  budget. Exhaustion returns explicit missing needs, not fabricated context.
- US3: A current-state request distinguishes requested, approved and completed
  events using effective time, source authority and contradictions; historical
  questions do not automatically receive the newest assertion.
- US4: A multi-fact request receives complementary evidence for figures,
  qualifications and exclusions rather than many topical fragments.
- US5: An operator can see profile, optional providers, egress, latency, cost,
  omissions and feature changes, and restore the previous safe profile.

## Functional requirements

- FR-001: Authorize scope and lifecycle before sending any candidate content to
  embedders/models; revalidate identifiers, generation and policy before delivery.
  Preserve encryption, evidence, deletion, audit and standalone reconstruction.
- FR-002: Preserve public deterministic behavior and local-first operation when
  optional intelligence is absent. No default Torch/CUDA installation, silent
  egress, provider switch or implicit opt-in. Existing integrations remain usable.
- FR-003: Add persistent, generation-aware semantic nomination alongside lexical
  exact matching, with bounded fusion/reranking. Record channel contribution,
  model revision, budget, failures and degradation. No whole-store per-query scan.
- FR-004: Expose bounded read-only search/inspect through shared product contracts,
  including Hermes and MCP. Query-time follow-up cannot admit or mutate memory,
  expand tenancy, bypass an authority rejection or replace the native agent loop.
- FR-005: Derive source-linked preference/state proposals; explicitly distinguish
  observed behavior, inferred preference and explicit instruction. Preserve event,
  effective and observation time, competing assertions and supersession evidence.
  AtMem validates mutations; models are not canonical truth or authority.
- FR-006: Extend existing obligations, sufficiency and packing rather than create
  a parallel API. Semantic checking nominates missing needs and supporting ranges;
  similarity/confidence alone cannot establish sufficiency. Preserve V3 statuses,
  fail-closed V2 translation, temporal/polarity/order and source references.
- FR-007: Benchmark adapters remain inert consumers of installed product APIs.
  No test IDs, answer keys, fact annotations, persona-specific heuristics or gold
  evidence enter product formation, embeddings, prompts or runtime planning.
- FR-008: Use the owner's fixed DolphinBench development slice as the active
  evaluation source. Source history, tasks, tools and upstream grading remain
  unchanged. Stop further RHELM/REALTALK collection and scored runs. Retain past
  artifacts privately; no model training is authorized here.
- FR-009: Freeze stratified sampling, cluster-separated roles, baseline, expected
  evidence, metrics, thresholds, retries and seeds before candidate evaluation.
  Existing DolphinBench is diagnostic/known-benchmark evidence. Public uninspected
  data is held out from this development effort, not proven absent from pretraining.
- FR-010: Require per-pillar baseline, pillar-only and cumulative comparisons,
  retained passing controls, ablations, independent confirmation and all failures.
  Cap initial candidate attempts at three per pillar; further tuning requires an
  explicit revised protocol, never reuse of a failed confirmation as sealed data.
- FR-011: Record full task success, complete-evidence coverage, applicable-state
  correctness, false assertions/refusals, uncertainty, p50/p95 time, tokens, ingest
  and query costs, throughput and storage. Primary task utility is not replaced
  by retrieval-only metrics. Resolve power and numeric guardrails before paid runs.
- FR-012: Reconcile the existing USD 250 total ledger before paid work; reserve
  final evaluation and confirmation cost, including rentals/storage/transfer and
  uncertain/in-flight calls. No automatic paid fallback; stop before overspend.
- FR-013: Preserve all benchmark and correction evidence/dependencies. Upload
  authorized large artifacts to Hugging Face and verify download hashes before
  removing only redundant inactive copies. Keep recoverable, pinned manifests.
- FR-014: Before each implementation/evaluation stage review constitution, all
  feature spec headers/requirements and relevant plans/contracts/docs. Persist
  their hashes, requirement dispositions, findings, affected test gates and exact
  reviewed source/config. Block execution on unresolved critical/high conflicts.
- FR-015: Maintain a feature-change register. Before removing, disabling or changing
  an existing feature/default, notify the user of exact behavior, reason, expected
  benefit, migration and rollback; report measured benefit afterward. This spec
  proposes no removal. Owner permission does not waive constitutional guarantees.
- FR-016: Preserve Code structure/experience, adapter setup/disable/restore,
  subscriptions, external-provider routing and companion compatibility. Apply
  versioned migrations and cross-platform installed tests before any beta release.
- FR-017: Freeze current-Mem0 release/commit and actual recommended configuration
  at comparison time, distinguish OSS/hosted, and match source, reader/judge,
  resources, tool opportunity and denominator. Hosted published scores alone
  cannot establish a matched superiority claim. Respect licenses and attribution.

## Acceptance and stage gates

- SC-001: Contract, integrity, scope, deleted/stale evidence, fallback and upgrade
  regression suites pass; no unauthorized disclosure or mutation in negative tests.
- SC-002: Each pillar has a predeclared primary diagnostic plus task utility and
  regression controls. Target 3x the *same sample's* baseline; unattainable ceilings
  and zero baselines are explicitly handled before evaluation, never relabelled.
  Unmet targets remain unmet; no tick based merely on implementation completion.
- SC-003: Combined confirmation targets 2.5x its own matched baseline. Historical
  32% implies an 80% full-suite aspiration, not an invented hard-sample baseline.
  The owner's updated ambition is 90%+ task success; the lower historical target
  does not establish readiness at 90%. Report task accuracy separately from
  statistical confidence that it exceeds the matched comparator.
  Confidence intervals and paired wins/losses must support the claimed effect;
  insufficient data means inconclusive, not pass. Safety gates remain mandatory.
- SC-004: The full 600-task rerun begins only after four accepted pillars and
  combined confirmation. Freeze artifacts/settings, retain all attempts and grade
  with the upstream protocol. Do not market it as an untouched test.
- SC-005: Superiority requires completed matched evidence, not selection of the
  best model/run or multiplication of per-pillar ratios. Report transfer outcomes
  separately because QA and tool-action task scores are not interchangeable.
- SC-006: A valid pre-stage review receipt is tied to current specs/source/config;
  edits invalidate it. Missing dataset qualification, gates, funding or archive
  dependencies prevent dispatch rather than fail after hours of paid execution.

## Compatibility and precedence

Spec 040 remains the V3 authority, package/status, integrity and source foundation.
046 extends its internal semantic nomination, navigation and state-view options
for 2.3.10; it does not retroactively alter 2.3.8 evidence or release claims.
040's historical fixed 23/30 samples and RunPod configuration are historical
campaign identities, not this campaign's sampling or rental mandates. This
campaign is controlled by FR-008–FR-013 and the evaluation protocol.
Specs 037, 042 and 044 retain adapter/Code behavior and their independent budgets.
For the explicitly selected investigative workflow only, this spec supersedes
040 FR-043's requirement to block the reader on semantic incompleteness: an
authorized reader may investigate via scoped read-only tools. This does not
change the strict deterministic/removal-control profile or turn an incomplete
V3 package into sufficient V2 context. Policy denial, stale/revoked authority and
inactive bindings remain terminal. External actions remain the host's decisions;
this workflow is not claimed to enforce semantic prerequisites at every app call.
Spec 045 checked-experience-learning is a separate workstream, not replaced by
retrieval improvement. No 2.3.10 publication promise bypasses release coordination.

## Edge cases and exclusions

Handle no supporting evidence, contradictory dates, inferred sensitive traits,
same entity across scopes, stale model results, absent embeddings, malformed
proposals, unavailable archives, disk pressure and incomplete grading explicitly.
No new Laya training, raw-source pruning, Cognee dependency, hosted-service clone,
benchmark-specific fix, silent feature removal or weakened governance is in scope.

Subscription-first primary confidence runs are required where the supported
provider preserves the frozen model, recording and limits. Paid testing services
are authorized within the same USD 250 cap, not an additional allocation; no
silent paid fallback or substitution of an unmatched reader is permitted.

## Owner execution amendment — 2026-10-21

Freeze a 60-task working set with 20 randomly selected tasks per persona. Use a
fixed random 18-task subset (six per persona) as the recurring check after each
pillar, then evaluate all 60 before the final full run. Select by IDs and seeded
sampling, not candidate scores. The owner explicitly selects this bounded
development workflow; do not make a new external dataset or separate transfer
corpus a prerequisite. Keep correctness, integrity, matched settings and budget
gates. Do not reopen the data-source choice during the implementation loop.

Keep task selections, prompts, labels, model exchanges, tuning evidence and score
tables in ignored/private storage or on MEM. Do not commit or force-add those
artifacts. Generic product and execution-tool source remains versionable.
