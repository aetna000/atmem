# Implementation plan — Spec 046

## Technical context

Python 3.10–3.13 product; encrypted canonical SQLite, V3 evidence ranges, typed
views and generation-aware indexes. Reuse `atmem/context_engine/{formation,
planner,retrieval,navigator,sufficiency,packing,service,contracts}.py`, existing
optional embedding/provider boundaries and `atmem/adapters/hermes/`.
Do not import the legacy retrieval engine wholesale into V3 or put memory logic
in `benchmarks/dolphinbench/`. Base reference is the completed 192/600 research
artifact, not a claim that the stock 2.3.9 release was tested identically.

## Architecture and changes

The governing architectural refinement is `architecture.md`: independent hybrid
discovery precedes semantic completeness; read authorization is separate from
evidence certainty, and host execution is measured separately. Offline foundations
may now be built across pillars before a scored acceptance; scored dispatch and
the full-run acceptance gates remain unchanged.

1. **Nomination**: add a V3 semantic channel behind an optional provider protocol.
   Persistent encrypted vectors bind model revision, unit/source IDs and generation.
   Apply eligibility before model content disclosure. Fuse independently bounded
   lexical/semantic nominations; optional reranker sees authorized text only.
   Retain exact lexical matches and channel diagnostics. No change to admission.
2. **Discovery**: extend the shared governed query/inspect boundary for iterative
   evidence discovery. A query session binds generation, scope, request ID and
   remaining time/token/byte/operation budgets. Expose through Hermes and MCP
   without replacing native tools. Keep authorization denial terminal; incomplete
   evidence may be searched further but never relabelled sufficient without proof.
3. **Views**: extend source-backed formation proposals with typed preference and
   temporal assertions and multi-range evidence where required. Validate source
   bounds, scope and schema separately from semantic entailment. Use governed
   reconciliation for current-state projections; retain conflicting histories.
   Do not overwrite original evidence or use freshness alone as authority.
4. **Coverage**: strengthen query-need decomposition and complementary packing.
   The model may propose needs/ranges, never a sufficient verdict solely from its
   confidence. Revalidate evidence IDs and material support, recompute packed
   coverage and preserve explicit partial/conflicted/withheld outcomes.

All four changes are in product code, optional and independently configurable
for ablation. Existing profile behavior stays fixed unless explicitly selected.
Missing dependencies produce visible safe fallback, not paid rerouting.

### Findings-driven continuation

Apply the dispositions in `architecture.md` dated 2026-10-22 before introducing
another scored variant. First reconcile the stopped recording/export boundary
from retained wire data, preserve all completed grades, and complete the missing
same-host comparator. Qualify persistent runtime dependencies and explicit
supervision so a child failure cannot leave the campaign described as running.
Do not change conflicting tool arguments or rerun a completed answer merely to
produce an exportable trace. If upstream-compatible reconstruction is impossible,
retain and report the technical failure in the requested denominator.

Then diagnose remaining task failures separately at discovery, applicable-state,
evidence-assembly and application-execution boundaries. Request-specific evidence
dossiers are a proposed refinement of pillars 3 and 4, not completed work or a
reason to discard the current comparison. Any implementation requires reviewed
contracts, negative tests, independent component selection and a frozen paired
evaluation. Preserve original sources and deterministic defaults. Detailed trial
outcomes belong in ignored `validation.md`, not versionable specifications.

The first bounded architectural experiment is initial source-state assessment
(T036), using the existing quoted interpretation contract before the first reader
packet rather than only after agent-initiated search. Implement it in the product
V3 binding/context boundary, with explicit application-owned provider/egress
selection, a distinct receipt and live authority rechecks. The adapter may select
that product profile but must not implement its reasoning, rendering or validation.
Retain the entire original source packet; measure the bounded annotation overhead
and compare against the unchanged same-host source-state condition. Keep all source
state, source bundles and computed-time switches independently configurable.

If annotation-only initial assessment fails its frozen gate, retain the complete
trial and test a separately selected source dossier presentation (T037). Implement
query-specific information-need/quote selection in AtBot, independent host
validation/rendering and the existing read-only inspection route. Bound the
delivered dossier independently, preserve source and fallback receipts, and do
not change the native application policy or deterministic/default profile.
Its evaluation starts only after the preceding condition is terminal and a fresh
source/config review passes. No gains may be manufactured by combining answers
from different presentations.

## Evaluation infrastructure

Create `research/retrieval_2310/` with small standard-library-first tooling:

- `corpora.json`: immutable pins, provenance, licensing status, inspected data and
  intended roles. Fetch only required files to MEM, not whole repositories.
- `qualify.py`: schema, evidence-reference integrity, temporal accessibility,
  duplicate/participant clusters and license/egress eligibility. Output decisions
  and exclusions without displaying confirmation questions/answers.
- `protocol.py`: typed manifests, frozen split hashes, stage states and budget
  reservations. Role checks must reject overlapping source/evidence clusters.
- `preflight.py`: validate a review receipt, current code/config/spec inventory,
  installed artifact, data qualification, selected role and budget before dispatch.
- `evaluate.py`: paired inert product invocations, evaluator-owned evidence scoring,
  end-task execution, failure-stage ledger and uncertainty. Support reader-free
  diagnostics first, then bounded paid evaluation. No gold annotation in the
  adapter or authorized product memory surface.
- `report.py`: all-trial registry, sample composition, paired wins/losses, component
  ablations, runtime/storage/tokens/cost and immutable archive links.
- `tests/research/test_retrieval_2310_*.py`: no-network/no-paid validation of
  gates, overlap, unknown usage, review staleness, metrics and archive recovery.

Product tests belong in existing V3/adapter suites. Tiny fabricated fixtures can
test plumbing/security only, not quality. No training is part of this campaign.

The fixed working-set dispatch decision is `evaluate.working_set_readiness`,
not the historical generalization/superiority `readiness` helper. It requires
complete paired 60- and 18-task records, at least 54/60 and 18/18 candidate passes,
a positive observed paired effect, four explicit accepted pillar decisions,
complete recorded usage, and review, resource, artifact, recording, budget and
archive qualifications. It does not create any missing qualification or establish
generalization or Mem0 superiority. Statistical-claim qualification remains
separate and unchanged. Do not dispatch from an incomplete report or pending
pillar decision; all unmet targets and ceiling limitations remain reportable.

## Dataset qualification and split design

**Active owner amendment:** use the fixed 60-task DolphinBench working sample
and recurring random 18-task stage check defined in the spec. The external
corpus work below is historical research, not a gate or active run plan. No more
data hunting. Store task selections and execution/tuning evidence privately;
do not commit them. Reuse the exact saved baseline grades when identities match.

Use RHELM for generated, independently published temporal/aggregation/contradiction
stress; REALTALK for real human-conversation transfer; DolphinBench for known-suite
diagnosis and final actions. All scores remain separate. Consider PersonaMem-v3
only after non-commercial data-license applicability is resolved; its MIT code
license does not license its data for every purpose.

Research has inspected REALTALK Chat_1 QA and one RHELM David Reyes example.
Mark these conversation/persona evidence clusters development-only. Metadata-only
counts across other files do not imply their answers were inspected. REALTALK
participants recur across files: split participant connected components, not
individual filenames. Few independent clusters may make transfer uncertainty
wide; do not compensate by treating correlated questions as independent users.

Before candidate work, classify eligibility/difficulty from baseline and source
requirements, randomly sample within strata and freeze manifest seeds/IDs.
Baseline-passed controls remain present. Gold/evidence stay evaluator-only.
Define minimum practical effect and paired power under the budget. Never claim
an arbitrary 20-question sample establishes a 3x/2.5x general improvement.

## Stage sequence and stop conditions

0. Spec/research/qualification; initial consistency review. No paid execution.
1. Implement and test preflight/gates, reconcile ledger and reserve spend; freeze
   matched current-Mem0 config, initial baseline and stage-specific numeric limits.
2. Pillar 1 offline diagnostics → bounded tuning → fixed validation → one reserved
   confirmation. Preserve candidate even if rejected; maximum three initial trials.
3. Pillar 2 follows the same ladder with pillar-only and cumulative ablations.
4. Pillar 3 follows the same ladder, including state/provenance/refusal negatives.
5. Pillar 4 follows the same ladder, including complete-support packing and controls.
6. Frozen combined evaluation on the owner-selected fixed 60 tasks and
   leave-one-out analysis. No external transfer corpus is required or collected.
   Keep later generalization or matched-superiority claims separately qualified.
7. Full 600-task campaign only after acceptance; upstream packaging/replay, exact
   installed artifact and actual matched-Mem0 execution if claiming superiority.
8. Optional beta release: migration, installed macOS/Windows/Linux gates, companion
   alignment, documented installation and full release coordination.

Owner release-preparation amendment: qualify the release-quality 2.3.10b1 beta
before the intended full600 campaign, then freeze the actual tested/published
beta artifacts. Stage 8's packaging/release checks may therefore precede stage 7;
this does not waive T021/T022 quality, review, recording or budget prerequisites.
No publication or paid dispatch is implied by preparing the version. A later
version-metadata-only 2.3.10 promotion needs installed/upgrade/equivalence checks;
behavior, dependencies, prompts, models or configuration changes require affected
reevaluation rather than relabelling the beta's results.

Before EVERY numbered stage and candidate evaluation, refresh the spec inventory,
resolve impacted requirements, inspect code diff, run relevant regression gates,
and bind review findings to exact specs/source/config in a receipt. A change makes
the receipt stale. Missing numeric budgets/metrics, unqualified corpus or unresolved
critical/high finding blocks dispatch; offline research may continue.

## Budget and storage

The existing total cap is USD 250; previously reported paid spend USD 3.200023
must be reconciled against actual ledgers, not assumed current. Reserve priced
full-run/confirmation/comparator spend before allocating tuning. Track ingestion,
query, grader, storage/transfer/rental and uncertain call costs separately.
Subscription usage retains tokens and limits, not invented API charges.

On 2026-10-21 Mac free space was about 3 GiB, MEM about 47 GiB. Use bounded
downloads and existing MEM workspace; do not clone all candidate repositories or
download new model weights until disk requirements are checked. Retain existing
benchmark inputs/outputs and frozen DBs. Archive verified redundant artifacts only
after privacy/license review, pinned HF upload and download/hash verification.

## Compatibility and feature changes

Maintain `feature-changes.md`; initially no removal. User-visible notice must
precede any removal or changed default. A change entry includes owned feature,
affected contract/spec, expected gain, measured evidence, migration and rollback.
Authoritative source pruning and weakening governance are not optimization options.
Historical 040 campaign-specific hardware/samples do not constrain this campaign;
its API/authority/coverage rules do. 042/044 Code discovery keeps native exact
tools and disable semantics. 045 is absent here but its uncommitted spec was read
in `/Users/javadtaghia/gitlab/aetnamem-learning-2.3.10/specs/045-checked-experience-learning`.
It owns checked-lesson promotion, not this retrieval campaign. Do not copy or
modify that worktree; bind its spec digest in reviews and recheck before merge.

## Fixed working-set continuation without answer replay

A separately frozen corrected condition may first execute the recurring18, then
extend to the original working60 only if all 18 pass and operational/budget gates
remain qualified. Declare this policy before dispatch; a failed check is retained,
not rerolled. Continuation requires the exact original fixed subset, complete
terminal parent records, unchanged product/companion/model/host/source settings
and hashes linking every inherited execution/grade. Run only the remaining 42
tasks and report all 60 together with their original provenance and costs. Keep
the combined parent/continuation cash below the predeclared persona cap. This
is known-benchmark diagnostic continuation, not independent confirmation or a
waiver of component acceptance, T021 or full600 readiness. Never modify an active
frozen source to introduce the continuation flag; qualify a separate harness
snapshot with identical installed product bytes.

### Retained terminal grading and pooled cash reservation

If a reader execution is already durably complete but an unsent grader call is
blocked by a conservative reservation, finish grading that exact saved execution
in a separate linked stage. Require the original pre-forwarding guard receipt,
no prior provider reservation/response, unchanged upstream rubric/model/settings,
and fresh review before the first grader request. Do not rerun the reader, tools
or a completed grade. A prospective grader-only reservation may borrow unused
cash from the fixed three-persona allocation pool when its full bound fits that
pool, confidence40 and total250; record this transfer explicitly rather than
pretend the original per-persona reservation was sufficient. Preserve original
cash ledgers, actual charges, unknown usage, source files and incomplete reports.
Publish a new linked complete report, never overwrite the earlier partial one.
