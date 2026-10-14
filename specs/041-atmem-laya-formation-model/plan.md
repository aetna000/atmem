# Implementation Plan: AtMem Laya Formation Model

**Spec**: [spec.md](spec.md)
**Target**: AtMem `2.3.9b1`
**Status**: Selective V3 revision approved for implementation at
`experiment_scale_percent=10`; the rejected always-on V2 checkpoint remains
research-only and external compute remains subject to the existing hard caps
and prerequisite gates

## Delivery strategy

Deliver the feature in four independently gated layers: authentic-conversation
state construction and transition adjudication; reproducible multilingual model
training/calibration; optional governed runtime integration; and matched
evaluation/publication. Spec 040 stays authoritative.
Dataset and model can publish after their own gates even if Jev superiority is
not established. Package release requires the full product and release gates.

## Technical context

**Runtime**: Python 3.10–3.13; existing AtMem library, CLI, local service,
dashboard, MCP and host adapters
**Model**: exact revision of `convaiinnovations/laya-multilingual`, optional inference extra,
Safetensors-only public export
**Training**: upstream-supported Laya tooling pinned after a reproducibility
spike; PyTorch device routes for Windows CUDA, macOS MPS/CPU, Linux CUDA/CPU
**Data**: 130,000 source-licensed authentic human–AI conversation observations,
partitioned into state history and state-aware train/validation/calibration/
sealed-test/holdback transitions; current run scale 10%, later configurable to
100%; exported as SQLite/vector snapshots plus JSONL/Parquet manifests and
checksums; heavy work rooted at `/Volumes/MEM/AtMem-Laya-Formation/` on the Mac
**Evaluation**: deterministic fixtures, installed-artifact integration tests,
paired cluster bootstrap, frozen public benchmark adapters outside product code
**External services**: Hugging Face for three public artifacts and conditional
credit-backed compute; Jev only for explicitly authorized comparison; Vast.ai
only after both local routes fail; no RunPod; Vast spend capped at USD 8 and
fallback Hugging Face compute capped at its separate USD 11 existing credit

## Constitution check

| Principle | Plan response | Blocking evidence |
| --- | --- | --- |
| Authority before intelligence | Models receive authorized bounded choices; AtMem verifies and commits | mutation/scope/race tests |
| Provenance and replay | Exact source, model, data, prompt/schema and decision digests | receipt round trips and manifest verifier |
| Safe defaults | Optional extra, no upgrade download, explicit preview/activation/rollback | clean install and 2.3.8 upgrade tests |
| Scoped transparency/deletion | No model expands scope; derived metadata follows lifecycle | cross-scope and deletion tests |
| Host-neutral contracts | Typed decision schema is independent of CLI/MCP/host | golden contract tests |
| Executable claims | Frozen matched protocol, paired uncertainty and artifact identities | report validator |
| Local-first intelligence | Deterministic fallback always works; egress explicit | provider-offline suite |
| Production benchmark evidence | Machine-labeled training evidence and independent public evaluation remain separate | cards and claim lint |

No constitutional exception is requested.

## Architecture

### 1. Strict typed evaluation and authority boundary

Replace the Choice-only V1 assumption with one versioned evaluation envelope
and three strict discriminated response contracts matching Laya/Jev mechanics:
Choice (2–255 options, complete distribution, one argmax), Noul (probability the
positive predicate is true), and Score (2–10 ordered levels, distribution and
verified expected value). A request contains the authorized observation,
canonical generation, actual same-scope retrieved memories, retrieval receipt
and exactly one versioned question. It omits storage authority and unrestricted
database access. Responses contain no free-form reasoning or generated memory.

A versioned formation-plan state machine selects questions and conditions. Its
validated outputs become one `AtMemFormationRuling`; a receptor maps that ruling
to a Spec 040 proposal. The governance adapter reloads canonical records,
verifies generation, targets, evidence, lifecycle, scope and policy, and alone
may call mutation services. Receipts preserve both classifier proposal and
authority outcome.

The request packer uses the pinned tokenizer, reserves the full question and
choice set, counts special tokens and admits evidence only as deterministic
source-range units. It emits a loss/overflow receipt and escalates or reviews
when the mandatory fields cannot fit; silent tokenizer truncation is disabled.

### 2. Mutually exclusive classifier routing

Implement Laya behind an optional runtime extra and lazy artifact resolver.
Activation pins an immutable revision and validated question-schema digest.
Device selection is explicit and doctor-tested. The router selects exactly one
semantic classifier: unchanged `2.3.8` deterministic, Laya, or Laya followed by
configured escalation. AtMem governance is always applied but must not repeat
semantic classification or ignore a valid Laya ruling. Any unavailable
dependency, revision mismatch, calibration failure, malformed response,
overflow or timeout produces explicit review or the configured receipted
failure policy.

### 3. Bounded generative escalation

An escalation policy evaluates only named reasons. It sends minimal authorized
evidence through the existing AtBot provider abstraction using a strict output
schema and budgets. The returned proposal goes back through the same authority
adapter. Laya remains useful with escalation disabled or offline.

### 4. Stateful snapshot and transition pipeline

Load original-language observations and conversation chronology from approved
authentic sources into an immutable work database. Generated, translated and
hand-authored replacement rows are ineligible. Build global exact/multilingual
semantic duplicate graphs and scoped chronology, then partition whole identity,
scope, conversation and duplicate components according to a scale manifest.
Superseded isolated weak labels may stratify selection for authentic multi-turn
state and rare operations, but never supply V2 targets; all selected transitions
are re-adjudicated against the frozen scoped state and the selector distribution
is recorded.

Chronologically replay the state-building allocation through an adjudicated
formation path to construct canonical state per scope. Freeze SQLite and vector
snapshots with embedding/configuration/source/canonical manifests and digests.
For each later transition, run actual AtMem retrieval against its pre-state and
store the bounded retrieval result, expected typed judgments, expected target,
expected mutation and exact post-state. Use copy-on-write/reset execution for
independent cases and evolving state for trajectory cases.

Codex CLI and Claude CLI operate as isolated, stateful transition judges through
the same restricted read-only database query surface. Each adjudicates every
transition once with its pre-state and retrieved memories,
then reviews its own work through duplicate-cluster, chronology, stratified and
contradiction/outlier passes. Each pass writes an append-only receipt containing
the prior decision, revised decision, query/evidence references and change
reason. The judges cannot see each other's annotations until both review loops
freeze under the declared convergence rule. Deterministic comparison follows;
unresolved disagreement uses a separate adjudication path rather than repeated
majority voting.

Full-corpus validators check snapshot/retrieval membership, expected-transition
and post-state validity, source authority,
privacy/license rules, language mismatch, judge coverage, pass completion,
duplicate topology and split isolation. Store rationales as audit metadata, not
inference targets. Language metadata is excluded from model-visible state.
Dataset export and runtime requests call one shared versioned packing module;
golden parity tests reject any byte, ordering, token-count or overflow-receipt
difference, preventing train/serve skew and invalid calibration.

### 5. Scale control, training and calibration

One checked-in scale schema defines the full allocation
`50000/20000/5000/5000/20000/30000`. A run manifest supplies
`experiment_scale_percent`; the current authorized value is 10. Deterministic
group-aware allocation records requested and achieved counts without splitting
security scopes, conversations, chronology chains or duplicate components. No
code or contract changes are allowed between 10% and 100% runs.

Freeze base revision, dataset revision and environment lock. Run a representative
smoke on Windows and Mac, recording capability, throughput, memory and expected
completion. Choose a viable local route. Only if neither is viable, query current
Vast offers and select under the total-cost cap. Train fixed-seed objective
controls over typed state transitions, select on validation only and fit
calibration/abstention on calibration only. Freeze the unmodified-base and tuned
evaluation configurations before opening the sealed test; evaluate both on the
identical snapshots/cases without using sealed outcomes for reselection, then
export/reload in a clean environment.

### 6. Evaluation

Use one frozen transition manifest for all arms. Formation/store evaluates
operation, target and exact post-state in both independently reset and sequential
trajectory modes. Retrieval uses fixed candidate membership and permits only
ranking/abstention differences. Combined tests replay formation then future
queries and attribute the first failing stage. Resolve Jev's concrete model
identity before calls. Reports include per-item raw results, action macro-F1,
target accuracy, exact-state accuracy, false-store/duplicate/unsafe-mutation
rates, abstention, Brier/ECE, latency/cost, paired cluster bootstrap intervals
and explicit gate outcomes.

Machine-labeled training evidence and independent evaluation tiers are separate.
Training-set results may support only a clearly named weak-supervision result. A
production-level superiority statement additionally runs a disjoint,
human-origin held-out conversation protocol at intended scale under Spec 040
and the constitution. LoCoMo is excluded. LongMemEval may be reported
separately but does not replace authentic-conversation confirmation; failure or
absence leaves the production claim blocked without blocking honest artifact
publication.

### 7. Publication and release

Create three separate private Hugging Face staging repositories for the loadable
SQLite/vector database, viewer-ready transition dataset and model. Upload each
by immutable manifest using an environment token; independently verify license,
privacy, secret scan, clean load/query and anonymous download before making it
public and recording its revision. First mark the already-public fictional V1
dataset/model cards deprecated without deleting or rewriting history. Package
integration follows only after all replacement artifact identities are frozen.
Release work follows `docs/release-coordination.md`; release/website sources are
revalidated against final revisions and the website source-pin PR remains
owner-reviewed and unmerged by the agent.

### 8. Selective single-call V3 correction

Treat the 2026-10-14 matched negative result as a design failure, not a tuning
parameter. Remove the sequential learned context/durability gates from the
candidate path. A deterministic structural router either completes the existing
deterministic path or delegates an unresolved semantic case; it never computes
a semantic answer and then asks the model to replace it.

For delegated cases, construct one finite Choice option set from the authorized
retrieved state. Non-relational options are `STORE_NEW` and `DO_NOT_STORE`.
Relational options are the Cartesian product of permitted operations and the
bounded opaque target aliases retained by AtMem. One Laya call selects among
these joint action-target options. The receptor maps the opaque option through
the request-bound table, revalidates the generation/target/scope/policy and
commits atomically or returns explicit review.

Derive a V3 transition-level training view from the existing authentic work
database and frozen split assignments. Reuse observation text only; generate no
conversations or translations. Add teacher-forced and on-policy replay states,
but keep source trajectory and split identity immutable. Before training, emit
class/target coverage and majority-control reports. Unsupported classes are
removed from automatic model options rather than fabricated through synthetic
data.

Train a simple cost-sensitive cross-entropy control before any RLCD variant.
Select using sequential validation exact-transition accuracy, macro-F1,
missed-durable-memory rate, false-store rate, wrong-target rate and runtime
failure. Fit per-action calibration on the isolated calibration partition.
Freeze the V3 packer, router, checkpoint and thresholds before evaluating the
same immutable SQLite/vector baseline used by the deterministic, original-Laya
and rejected-V2 arms.

Activation remains two-stage: shadow records invocation rate, decisions and
latency without influencing memory; explicit cutover is available only if the
FR-047 quality, safety, validity and latency gates pass. A failed candidate is
retained as negative research evidence and deterministic AtMem remains active.

## Work phases

1. Freeze contracts, schemas, sources, threat model, claims and external-cost
   protocol.
2. Build the scale-bound scoped SQLite/vector baselines, retrieve stateful
   challenges, adjudicate expected transitions and stage the transition dataset
   privately. Execute 10% now; retain the same path for a later owner-authorized
   100% run.
3. Qualify Windows and Mac; conditionally qualify/rent Vast; train, calibrate,
   export and stage the model privately.
4. Implement optional Laya runtime, shadow qualification, escalation,
   setup/status and fallback tests before stateful adjudication/export consumes
   the shared V2 validators.
5. Run matched evaluation and decide only the claims supported by evidence.
6. Publish the three Hugging Face artifacts, then prepare and execute the
   coordinated beta release under separate approvals/gates.
7. Build and evaluate the selective single-call V3 correction against the same
   immutable baseline; activate or release it only if its independent gates pass.

## Verification gates

- Contract/property tests reject unknown choices, forged evidence, stale
  generations, cross-scope IDs and malformed or over-budget model output.
- Dataset generation is deterministic from manifest/seed; leakage, duplication,
  audit and secret/license gates pass before training or visibility changes.
- Training smoke and full-run manifests prove exact inputs, objective, device,
  numeric local-viability envelope, checkpoints and off-device recovery; sealed
  data remains unopened until objective/checkpoint/threshold/analysis freeze.
- Clean-wheel tests cover no-extra, offline, activation, rollback and the declared
  OS/device matrix; no production import depends on benchmark code.
- Evaluation validator checks matched items/options/budgets, concrete model IDs,
  candidate membership, missing rows, paired statistics, latency effect size,
  authentic-confirmation provenance and quarantined historical-result wording.
- Private-to-public publication verifies downloaded files, SQLite/vector clean
  load/query behavior and digests for all three artifacts, not merely successful
  upload calls.
- Release gates verify source commit, annotations/tags, workflows, GitHub release,
  PyPI, npm and website states independently.
- V3 gates reject absent/underpowered action classes, any train/serve option or
  packing drift, more than one model call per delegated transaction, any model
  call on deterministic-resolved transactions, malformed output, context
  overflow, missed-durable regression or an unproven latency/quality claim.

## Risks and controls

| Risk | Control |
| --- | --- |
| Laya is specialized but weak zero-shot or overconfident | fine-tune, isolated calibration, abstention/review and base-Laya control |
| Conversation or teacher patterns leak across splits | conversation/user grouping, semantic near-duplicate checks and teacher metadata excluded from model input |
| Fine-tune learns label priors/collapses | per-question balance, adversarial swaps, collapse metrics and objective control |
| Model output gains authority | finite opaque IDs plus canonical revalidation and mutation tests |
| Jev is a moving service | resolve exact identity/config at run time; block claims if unresolved |
| Cheapest rental becomes expensive | total-cost estimate, USD 8 hard cap, resume proof and immediate teardown; no RunPod |
| Credentials leak through tooling | environment/interactive secrets, redacted subprocesses, scans before upload |
| Cross-platform promise exceeds evidence | claim only tested device/OS profiles and publish the matrix |
| Spec 040 changes concurrently | bind integration to versioned public contracts; re-run alignment before merge |
| 2.3.8 is not yet published | allow bounded development against a named candidate, but block final upgrade evidence and release until rerun against the verified PyPI artifact |
| Natural conversations overwhelmingly favor DO_NOT_STORE | transition-level class-aware selection/weighting, majority controls, macro-F1 and missed-durable gates |
| Teacher-forced training hides error accumulation | authentic on-policy state replay and sequential validation |
| Multi-call gates amplify errors and latency | one joint action-target Choice call only for ambiguous cases |
| Retrieved state exceeds the model ceiling | shared deterministic candidate/token budget before training and serving; overflow is a blocking result |

## Approval boundaries

This plan does not authorize paid compute, remote login, credential use, external
API calls, Hugging Face visibility changes, package publication, tagging, website
merge or deployment. Each occurs only in its relevant implementation task after
its prerequisites and authorization are satisfied.

## Release prerequisite

The `2.3.8` candidate may support early development, but it is not an
authoritative upgrade baseline. T034's final evidence, version/pin freeze and all
Phase 6 release actions require the exact published and registry-verified AtMem
`2.3.8` artifact. If its final behavior differs from the development candidate,
the Spec 041 alignment, migrations and installed-artifact tests are rerun.
