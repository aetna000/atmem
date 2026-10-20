# Repository-disjoint Code evaluation — prospective plan

Status: research/review and the 30 eligible Windows validation attempts complete;
pack plus tools meets the aggregate 20% input/full-task gate, with reduced partial
target correctness. Independent confirmation and archive recovery remain pending.
The owner requested
broader repositories and a Claude Opus 5.5 medium review; see the recorded
[adoption decisions](../../RandD/2026-10-17-benchmark-review-adoption.md).

## Scope and invariants

Keep the requested goal: 50% fewer TOTAL input tokens versus native tools,
accept exact 20% if 50% is not demonstrated, and equal or better task test-pass
rate. No goal completion from unit tests, tool uptake or selected Click rounds.
Retire the familiar five Click tasks from further scored tuning. Spec 043 keeps
their historical protocols/results; it is not silently relabeled multi-repo.
The unused Click set is not repository-disjoint confirmation and is not used
to pick candidates. Its existing gates and all historical scores stay intact.

Only Python-first qualification is currently proposed. A multi-language task
source does not establish multilingual code extraction/packing competence.
No owner install/configuration, release/main changes, API/GPU spending or model
training. Coding inference remains Luna-low subscription CLI; review-model use
is separately identified. MEM holds benchmark inputs/protected archives only.

Owner-authorized execution update, 2026-10-18: use the Windows machine's existing
Ubuntu WSL2 for benchmark execution. Installing benchmark prerequisites there
and isolated CLI/product runtimes is authorized; normal owner CLI configuration
remains unchanged. Do not move/delete Mac data without approval. Keep Windows
measurements separate from historical Mac/emulation measurements. Actual setup
qualification and its limitations are recorded in
`RandD/2026-10-18-windows-benchmark-worker.md`; no repair/benefit batch follows
merely from a passing public test or instructed MCP-discovery diagnostic.

## 0. Read-only catalog and environment qualification

Reuse official task metadata/base commits and FAIL_TO_PASS/PASS_TO_PASS grading
instead of extending Click-specific pass judgments. Pin harness, dataset/catalog
revision, task license and per-task worker recipe/image by immutable identity.
The inspected task catalog is not yet a locally qualified pool.

Proposed validation repository group: marshmallow, Requests, Astroid. Proposed
different-repository confirmation candidates: pydicom, SQLFluff, pvlib, pytest,
Sphinx. These are feasibility candidates, not declared runnable tasks. Before
model runs, freeze eligibility by language, reproducible environment, authentic
issue provenance, resource bounds and parent-fail/reference-pass controls.
Retain every qualification failure and reason. Do not filter by model outcome,
expected token saving, patch simplicity or a preferred AtMem mechanism.

Upstream task directories contain gold/test patches and hints. Keep the task
catalog and evaluator outside solver mounts. Expose sanitized base source plus
the authentic allowed issue description only; no future Git objects. Execute
untrusted repository setup/test scripts only in disposable constrained workers,
never in the owner environment or with the Docker socket/owner credentials.

Keep AtMem's runner isolation/provenance layer. Replace or parameterize the
Click-specific patch collector, `src/click/` allowance, grade paths and syntax
audit before claiming generic support. Qualify ARM/build/runtime equivalence;
do not assume published images work on the Mac. No instance starts scoring
until both source/grader integrity and environment controls pass.

## 1. Exposure and measurement gates, before repair scoring

Observe server startup, initialized version, returned tools/list, host enabled
tool config, client attempts, server prepared-response receipts, actual source
bytes and refusal/currentness. Distinguish prepared, written-to-transport,
client-observed and model-consumed; missing full model-input capture remains
explicit. No source text may enter trusted server guidance.

Use a small prospective set of repository-diverse read-only discovery tasks that
require cross-file source inspection; include ordinary native access. Define
questions from base source without hidden patch/test labels. Freeze paired
guidance-none/bounded order and task set before inference. The unrun one-pair
getLogger draft is not the active mechanism test. A positive wiring test is not
benefit evidence. No MCP-specific claim without observed authorized source use.

Primary total-input comparison requires complete accounting. Preserve raw host
usage, distinguish cached components without double counting, and test accounting
at normal completion and resource stops. Partial cumulative snapshots remain
partial until completeness is proven. No cap-value/arm-maximum imputation.
If this gate fails, improve measurement or report the experiment incomplete;
do not launch a large cohort hoping incomplete rows can be discarded later.

## 2. Bounded repository-disjoint validation

Proposed engineering scale: six authentic tasks over three qualified validation
repositories, two fresh repeats per task, three arms (36 solver attempts).
This is a feasibility/variance pilot, not enough for a broad research claim.
Pre-register a seeded sampler and stratification before issue/solution outcomes.
Freeze at most TWO product candidates, with no edits during the batch:

- V1: source pack only, no registered MCP tools.
- V2: the same source pack plus scoped read-only MCP and fixed trusted guidance.
- Native: ordinary source/search/test tools, no AtMem pack/tools.

Generic task/policy wording, environment, model, native capabilities and
prospective resource caps are matched. Randomize and balance arm order; retain
alias/date limitations. A V2 contrast measures the combined integration, not
graph, tool or guidance causality individually. A separately predeclared flat
lexical-retrieval control can test graph contribution, but it cannot be added
after viewing favorable outcomes or pooled into the primary denominator.

Report all tasks and repeats, functional repair passes, F2P/P2P outcomes,
schema/authority failures, complete/unknown usage counts, total input and cached
components, native/MCP turns and response bytes. Report setup/index/context/
solver latency, cold and amortized indexing separately. Output bytes are not
tokens. Investigate failure mechanisms without feeding hidden grades to the
same solver or retrying an unchanged candidate.

Use this batch to estimate variance and feasibility. If neither candidate meets
the predeclared quality/token gates, report failure rather than invent more
variants on these same tasks. Do not switch quality to an easier margin or
optimize only successful runs. The owner’s equal-or-better requirement remains.

## 3. Locked confirmation, after a qualifying validation result

Freeze one candidate and analysis before examining confirmation outcomes.
Proposed engineering minimum: 20 authentic tasks across five NEW qualified
repositories, two repeats, native/candidate pairs (80 attempts). Final sizing
must use validation variance before confirmation, not a convenient success
threshold. This size is not a promised statistical power or publication claim.

Primary endpoints: complete paired total-input ratio and observed task-pass
rate, preserving the exact 50%/20% and equal-or-better thresholds. Report paired
uncertainty with task/repository clustering; repeats are not independent new
tasks. Report per-repository outcomes, failures and latency, not only a pooled
headline. No newly introduced non-inferiority margin is approved here.

Run the locked batch once. No mid-run code/prompt/cap changes, cherry-picked
native control, unknown-as-zero, dropped failures, or repeat-until-pass. Failed
confirmation remains failed; it does not complete the goal. Any later research
cycle needs an explicitly new protocol and unexposed pool, not relabeling the
same holdout as fresh. No claim of public-pretraining decontamination merely
because an issue is recent or comes from another repository.

## Deliverables / current state

- Complete: external-model review, primary-source research and recorded adoption
  decisions; historical Click evidence remains unchanged.
- Progress: six metadata-verified tasks selected by a fixed identity-only rule;
  immutable registry descriptors recorded; one constrained amd64 interpreter
  control passed. Neutral source-only snapshot boundary and protocol exposure
  receipts have local tests. See `external-preflight-v1.md`,
  `external-runtime-control-v1.md` and the RandD preflight report. None is yet a
  task environment/reference/model qualification or performance result.
- Subsequent explicit same-task v2 passes first Marshmallow parent/reference:
  8/8 target failures on parent, 8/8 target passes on reference, 61/61 regression
  passes each. V1's two zero-execution space stops remain retained. Retired
  scratch is recoverably archived, not discarded. This qualifies one task
  environment/control only; no model repair or benefit result exists.
- Source-to-grader and public-source identity controls now pass for that same
  task. 76 public files are verified; six image-only runtime files remain out
  of solver input and preserved during proposal assembly. No model ran.
  See the RandD external-source-boundary report; native development-test access,
  actual candidate-worker/host integration and full accounting remain open.
- Pending: pinned eligible catalog manifest, neutral source/evaluator adapter,
  environment/exposure/full-usage qualification, preregistered sampler and batch
  manifests, execution, complete comparison and independent archive recovery.
- No new scored Click iteration, uptake-model turn or multi-repo repair solve
  has started under this plan. Unit/contract checks are not performance results.

Before the full validation batch, the first qualified task will run one frozen
native/AtMem repair integration pair under
`windows-first-repair-integration-v1.md`. This tests actual patch/usage/lifecycle
binding, not independent benefit or goal acceptance. Keep the six-task,
three-repository validation and locked different-repository confirmation intact;
do not substitute this small pair, select a winner from it or silently retry
failed attempts. Public testing uses the same qualified common interface in
both arms. Historical Click trials and discovery diagnostics remain separate.

2026-10-18 execution update: that integration pair is now complete, with both
arms passing 4/8 target and 61/61 regression checks but neither solving the issue.
AtMem uses 286,923 total input tokens versus 219,942 native (30.453938% more);
both receipts are complete. Zero Code MCP calls completed. Earlier statements
above describe chronological qualification stages, not the current absence of
model results. See `RandD/2026-10-18-first-windows-repair-comparison.md`.
This result does not change the fixed task pool, candidate count, quality/token
thresholds, batch scope or separate confirmation requirement.

Further Windows qualification update: the other four parent/reference-qualified
tasks now have passing governed source-assembly controls and byte-verified public
exports. Requests-1327 needs explicit evaluator-only `.eggs` runtime projection;
its two original snapshot-cap stops remain recorded. Requests-4356 remains an
unqualified environment after its recorded v2 partial reference result, not a
replaced task or failed solver. Public-test/proposal qualification and prospective
cohort accounting for this attrition are still required before broader scoring.
See `RandD/2026-10-18-selected-repository-source-controls.md`.

Completed validation update: the original 36-slot manifest retains six unrun
Requests-4356 environment slots. All other 30 attempts have full usage, actual
stopped sources and private grades. Native/pack/pack-plus-tools each fully solve
4/10 attempts. Total input is respectively 2,678,786 / 3,144,771 / 2,013,987;
pack plus tools reduces aggregate input 24.817175%, meeting the predeclared
20% validation fallback only. Target checks fall from 12/24 native to 8/24 pack
and 4/24 tools, while all declared regression checks pass. Only one Code MCP
call completes. Cold solver/index/context sums are slower than native. These
qualifications prohibit a broad quality, latency or graph-causality claim.
The earlier progress bullets are chronological; the authoritative completed
comparison and recovery disclosures are in
`RandD/2026-10-18-windows-validation-cohort.md`. Do not rerun these tasks to select
a better outcome. T062/T077 remain open for confirmation and archive recovery.

Subsequent confirmation qualification identifies an incomplete exposed v1
pool, not a completed confirmation: only three tasks qualify. A new explicit
graph-omission candidate preserves strict execution identities and is separately
built/installed/qualified. The old artifacts and results remain unchanged.
The active prospective continuation is `windows-confirmation-v2.md`: forty
fixed feasibility candidates from five wholly new repository groups, then the
first four mechanically qualifying identities per repository before any solver
inference. This stage distinction is frozen before metadata fetch, not an
outcome-based substitution. The final design remains twenty issues and eighty
attempts with the same acceptance thresholds; insufficient eligibility is
incomplete. See `RandD/2026-10-18-explicit-source-omissions-candidate.md`.
