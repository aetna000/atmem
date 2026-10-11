# Implementation Status

**Updated**: 2026-10-11
**Current phase**: Phase 6
**State**: T001–T046 complete; website handoff and package publication next

## Completed

- T001–T007: authority alignment, immutable public source lock, Jev no-call
  identity preflight, threat model, Hugging Face staging contract, matched
  evaluation protocol and compute qualification protocol.
- T008–T011: shared tokenizer-exact packer, dataset contracts/schemas,
  deterministic fictional scenario generator, executable oracle, group-disjoint
  splits, exact/near-duplicate validation and sealed-label-safe training loader.
- T012: generated and checksum-verified 12,000 synthetic scenarios and 60,000
  typed decisions at `/Volumes/MEM/AtMem-Laya-Formation` (94 MiB, 17 inventoried
  files, zero validator critical findings). Generator `1.3.0` uses semantically
  compatible operation/class pairings, makes every transition explicit, and
  fails unresolved contradiction cases closed. Dataset manifest SHA-256:
  `a8193d66a0184f1dbbb94ec73d2f85b6362ddfb8457a5a18dc829082a8851d60`.
  The exporter removes macOS/exFAT metadata sidecars before inventory generation.
- T013: generated the blinded 400-row packet with every required
  high-risk tag at or above 60 rows; added an Ed25519-signed, packet-bound
  independent review and deterministic scoring workflow. The unsigned response
  template is under `/Volumes/MEM/AtMem-Laya-Formation-Review/` and is not part
  of the publication inventory. A firewalled `gpt-4.1` review received no answer
  key, returned all 400 rows, verified its Ed25519-bound receipt and passed with
  399/400 exact targets (99.75%) and zero critical findings. Result SHA-256:
  `38d57dc8b720020f84e268cf294e1ab3f2ac1c3523b3cfbeffc38ea66796607e`.
- T014: added and linted the dataset card/data statement, Apache-2.0 license,
  three JSON Schemas and signed audit artifacts. The final local publication
  inventory has 25 files; every downloaded/upload candidate digest and JSONL
  record passes local staging validation. Final dataset manifest SHA-256:
  `d67d371c8c1d6de85a0293cded5aa5b3f7d078e92197130ce1f9edef68e863d4`.
- T015: corrected the reference-publisher namespace to the project-owned `atmem`
  organization, privately staged `atmem/atmem-laya-formation-v1`, and verified
  immutable revision `4436089b38cbe3a5374aaaa92c4c77703cdbf668` by clean
  redownload. All 25 inventoried files passed size/digest/schema/secret checks;
  the sole additional remote file is Hugging Face-managed `.gitattributes`.
  Receipt: `research/laya_formation/receipts/hf-dataset-private-staging-20261010.json`.
- T016: added the immutable representative workload and executable smoke runner.
  It pins both source revisions, uses group-safe non-sealed samples, trains the
  full encoder for `soft-ce` and `rlcd`, fits isolated calibration, verifies an
  optimizer-bearing checkpoint in a fresh process, reloads Safetensors and emits
  the frozen FR-020 viability decision. Focused training/publication tests pass.
- T017: ran the fixed full-encoder CUDA smoke on the Windows Quadro P2000. Both
  objective steps were finite and checkpoint restart plus Safetensors reload
  reproduced the decisions exactly. The finalized runner measured no device
  headroom and projected about 347 hours for both controls. The candidate is
  `infeasible`. Final receipt:
  `research/laya_formation/receipts/windows-smoke-20261011.json`.
- T018: ran the byte-identical finalized workload on Mac MPS. Both objectives,
  calibration, fresh-process optimizer restart and Safetensors reload passed;
  the projection was about 953 hours, so the route is `infeasible`. The process
  also reached a separately sampled 15.4 GiB physical-footprint peak on the
  16 GiB host; that host-level sample is retained as supplemental evidence and
  is not substituted for the runner's MPS allocation metric. Receipt:
  `research/laya_formation/receipts/mac-smoke-20261011.json`; sample:
  `research/laya_formation/receipts/mac-smoke-process-sample-20261011.txt`.
- Local focused suite: 22 passing tests and one expected mount-presence skip
  across dataset and Jev protocol modules.
- Real pinned-tokenizer probe: total checkpoint limit 512, head cap 192; the
  representative five-operation head uses 51 tokens and the one-range fixture
  uses 99 total tokens with no truncation.

## Current gate

T019 is eligible because both local candidates are recorded `infeasible`. A
live on-demand search used the preselected minimum reliability `0.99`, verified
CUDA, at least 24 GiB VRAM, at least 100 GB available disk and direct SSH. The
approved route rented a verified, non-VM-deverified RTX 5090 with 32 GB VRAM,
99.91% reliability and 100 GB disk at USD 0.481111/hour including storage. The
warm representative smoke is viable with 72.5% memory headroom and exact
restart/reload checks. A complete model-plus-optimizer checkpoint was copied to
`MEM`; all 10 files match the remote SHA-256 manifest. Qualification receipt:
`research/laya_formation/receipts/vast-qualification-20261011.json`.

T020 adds validated Draft 2020-12 schemas for the run manifest, metric report
and calibration bundle; deterministic identity, finite-value, tokenizer-exact
truncation, collapse, class-prior, calibration-power and secret checks; and the
frozen FR-019 same/cross-backend tolerances. The selection policy is fixed
before results and cannot read sealed-test data. Focused training tests pass.

T021 completed both frozen objectives on the qualified Vast RTX 5090. Soft-CE
trained for 2,485.76 seconds and RLCD for 4,390.91 seconds; both reached 1.0
validation and calibration accuracy/macro-F1 with zero measured NLL, Brier and
ECE on the synthetic nonsealed splits, with no truncation, collapse or missing
class. This is not yet a sealed-test or real-world claim. The predeclared stable
tie-break selected RLCD; selection digest
`bbfaf2557e05465a7eaba9404dc6cdc88dfc7167e1904ccd5a2efa3621026db6`.
The selected Safetensors digest is
`f2ba3dd7679da45aabab4cac30e9a079baeb2dc98229ff3b1618e6a06fc6d683`.
It and the frozen training evidence were recovered directly from the instance
to private `atmem/atmem-laya-formation-model-v1` revision
`d4e46a5b8cf11c5808f9e745f19145c0a4fb5dfd`, then redownloaded by that exact
revision and checksum-verified locally. This is recovery evidence, not the
final T026 publication revision.

T022 froze the already-fitted calibration/abstention bundle, selected model,
question definitions, dataset inventory and one-shot sealed analysis code before
parsing either sealed JSONL file. Freeze digest:
`fe07a64028dcfdc9c362195965dee9d52ff5b3638bd1606c769ec32a36655f80`;
analysis-code digest:
`f3344d3bb899cf6b18d266e4a2de7e8bec8316929723ffb4713ac0030249060b`.
The exclusive markers make both audit preparation and model evaluation
single-attempt operations, and the analysis refuses a sealed audit from the
same `gpt-4.1` reviewer identity used for the nonsealed audit.

T022A used a deterministic 400-row sealed sample balanced at 80 examples for
each question. The firewalled `gpt-5.5` reviewer received the blinded packet
but not the answer key, returned all rows, and produced a signed 400/400 result
with zero critical findings. The reviewer identity differs from the nonsealed
`gpt-4.1` audit. Receipt:
`research/laya_formation/receipts/sealed-audit-20261011.json`.

T022B consumed the exclusive sealed-evaluation attempt on Mac MPS with the
frozen model, calibration and analysis. All 7,200 examples were correct overall
and in each 1,440-row question class; macro-F1 was 1.0, calibrated NLL
`2.444728370361525e-13`, Brier `3.579108993448185e-25`, ECE
`2.4447111002245947e-13`, accepted coverage 1.0, and there were zero failures,
truncations, missing classes or collapse. No result was used for selection or
tuning. These remain synthetic held-out results, not production evidence.
Evaluation digest:
`422d644ed5d37c5bf2ff4cd1b8279b645d0e61d265e3d3cd8eaf7d6657104486`.

T023 assembled the portable Safetensors export with exact tokenizer, agent
config, question definitions, calibration and training lineage. Export digest:
`6f7d53c18431c27baa617ab95ebcc4cad669917a6508145fa001eb7c8e799900`.
Two fresh CPU reloads and one fresh MPS reload each scored 100/100 on the fixed
nonsealed probe. Same-backend agreement was 1.0 with zero score delta;
CPU/MPS agreement was 1.0 with maximum normalized-score delta
`7.202209016348514e-16` and zero aggregate accuracy delta, passing all frozen
FR-019 tolerances. Receipt:
`research/laya_formation/receipts/model-reproduction-20261011.json`.

T024 recovered the selected model and all RLCD epoch checkpoints off-instance,
retained every recorded failure, captured final Vast spend of USD 1.5418210255,
destroyed instance `55225996`, and verified zero active instances. Receipt:
`research/laya_formation/receipts/vast-final-20261011.json`.

T025 adds `research/laya_formation/publication/MODEL_CARD.md` with exact base,
source, dataset, model, question, calibration and export lineage; full synthetic
metrics; calibration/application requirements; intended use; AtMem authority,
fallback and AtBot escalation boundaries; compatibility evidence; and explicit
synthetic/public-corpus/Jev/production limitations. It contains no placeholders
or secret-like material.

T026 published the complete candidate privately to
`atmem/atmem-laya-formation-model-v1` revision
`1698278c4b158fac30e4eb2fefd10ef8b8f873b3`. A clean revision-pinned
redownload verified all nine runtime/export inventory entries, the 13-file Hub
inventory including Hub-managed `.gitattributes`, the exact card and Apache-2.0
license, zero secret findings, and a fresh CPU load/inference probe. The repo is
confirmed private; public visibility remains the separately controlled T044
action. Receipt:
`research/laya_formation/receipts/hf-model-private-staging-20261011.json`.

T027–T029 add the v1 question/calibration/request/response/receipt contracts,
golden round trips, malformed/version/nonfinite/overflow checks, and an
authority-first adapter. The adapter reloads scope, canonical generation,
exact source bytes/ranges, active candidates and policy through the owning Spec
040 SQLite state before invocation and again before disposition. Forged,
stale, cross-scope, invented, deleted, policy-denied and unauthorized-provider
cases fail closed; model proposals and authoritative mutation remain separate.
The focused product contract/governance suite passes 14 tests.

T030 adds the optional `laya-formation` dependency group and an immutable,
lazy artifact resolver. Base installs import without Laya or network access;
explicit resolution verifies every inventoried byte plus model, question,
calibration and export identities. T031 adds strict CPU/MPS/CUDA selection,
the exact pinned-tokenizer whole-range packer, question/calibration binding,
finite complete probability checks, frozen-threshold abstention, deadline and
truncation rejection, content-free diagnostics and fail-closed governance for
runtime or authority-reload failure. A wheel-only Python 3.12/macOS CPU run
loaded the pinned model, reproduced frozen structural packer digest
`b77f1dce7cf1cb2e48efefe14899d699520a2868ea06d5eba0de4e86f88c0f85`
and completed a non-truncated 199.56 ms inference. Receipt:
`research/laya_formation/receipts/installed-runtime-20261011.json`. The focused
slice passes 51 tests with one expected external-mount skip.

T032 adds an explicit one-call/no-retry escalation policy for ambiguity,
coupled mutations, unsupported normalized values, packing overflow and
calibrated low confidence. AtMem sends only the finite question, included
authorized ranges and candidate IDs through the existing loopback-authenticated
AtBot companion. Provider input/output tokens, timeout, remote egress and cost
are bounded; remote results without a cost receipt fail closed. The AtBot
provider interfaces now accept per-call output/deadline controls, and the
companion validates a strict dynamic choice schema while retaining no storage
authority. Every result is rechecked against the post-call authority snapshot;
disabled, offline, malformed, over-budget or denied-egress paths require
deterministic fallback/review. Escalation provider/model/usage/cost metadata is
additive in decision receipts. The broader Laya/AtBot/provider regression slice
passes 114 tests with three optional integration skips.

T033 adds `atmem formation preview|setup|activate|status|doctor|rollback`.
Interactive setup shows the inactive transaction before confirmation, while
`--yes` is the noninteractive equivalent; setup never activates. Activation
loads the exact staged model and requires separate confirmation. Rollback
restores the byte-identical pre-activation profile. Status and doctor are
content-free and expose revision, device, calibration, optional escalation and
fallback readiness. The same read-only state is exposed through MCP tool
`memory_formation_profile_status`, dashboard endpoint
`/api/formation/profile`, and the dashboard status payload. A real clean
Python 3.12/macOS CPU journey passed preview, local artifact verification,
activation/load, doctor and exact rollback. Receipt:
`research/laya_formation/receipts/profile-e2e-20261011.json`.

T033A verified stable AtMem `2.3.8` on the live PyPI registry, including PyPI
Trusted Publishing provenance from commit
`267c5b3ac08e8cac26dfee13c6eac2842d4bb876`. The binary-only no-dependency
redownload of `atmem-2.3.8-py3-none-any.whl` matches registry SHA-256
`05ca2c579be1af55de1da056ae257062417831b2e8eb4f2fda2a6413ba3ee923`;
wheel metadata confirms version `2.3.8`, Python `>=3.10`, and
`atmem-atbot==0.1.0`. Receipt:
`research/laya_formation/receipts/pypi-baseline-2.3.8-20261011.json`.

T034 rebuilt the candidate wheels after constraining `cryptography` to the
tested `<49` line; this avoids the macOS loader failure reproduced with 50.0.2.
A source-isolated Python 3.12 fresh install passed the installed CLI/store/
recall/verification smoke with AtMem `2.3.9b1`, AtBot `0.1.1b1`, AtFlows
`0.1.4b3` and cryptography `48.0.1`. A separate environment installed the
registry-verified `2.3.8` baseline, persisted a record, upgraded to the exact
candidate wheels, recalled the same record and proved no model download or
default-profile change, byte-exact profile rollback and additive CLI, MCP,
AtBot and OpenClaw surfaces while retaining AtBot protocol 1 and AtFlows
`0.1.4b3`. Candidate wheel SHA-256 values are recorded in
`research/laya_formation/receipts/wheel-compatibility-20261011.json`.

T035 executed source-isolated base-wheel smokes on Python 3.10, 3.11, 3.12 and
3.13, then loaded the exact final model through the exact candidate wheel for
macOS CPU/MPS, Windows CPU/CUDA and Linux CPU/CUDA. All six real device rows
returned valid bounded decisions with the pinned model, question and calibration
identities. Explicitly unsupported CUDA-on-Mac and MPS-on-Windows/Linux requests
failed with actionable diagnostics and no activation. The Linux rows used a
verified Vast RTX 2070 Super at USD 0.07222/hour; the measured account delta was
USD 0.04436064394, the instance was destroyed and zero active instances remain.
The receipt publishes only executed combinations:
`research/laya_formation/receipts/installed-compatibility-matrix-20261011.json`.

T036 adds a benchmark-only normalized choice contract and all six frozen arms:
deterministic AtMem, pinned Qwen 3.5 9B, base Laya, fine-tuned Laya, resolved
Jev and fine-tuned Laya with a one-call AtBot escalation. Every row binds the
authorized-input, option, candidate-pool and question-schema digests; identity,
hardware, dtype, batching, call/token/deadline/retry/egress budgets are explicit.
The remote adapters enforce response identity and strict finite choices, while
provider, schema and timeout failures are retained as review/error rows. Expected
labels never enter payloads. A repository scan confirms product modules import no
evaluation code, and the focused adapter suite passes.

T037 froze a balanced 400-case synthetic comparison packet as 80 complete
scenario clusters with all five typed questions, with answers in a separate
checksum-bound file on `MEM`. The
exact AtMem wheel, base Laya files, fine-tuned Laya export, current Qwen Hub
revision, option/candidate/question sets and per-call budgets passed no-egress
verification. The paid route is capped at USD 2 with no top-up and uses existing
Vast prepaid credit; a live verified RTX 3090 offer was available at USD
0.20089/hour. Jev's authenticated `/v1/models` returned only the moving aliases
`jev-latest` and `jev-preview`, so zero Jev decision calls are authorized and the
Jev comparison/superiority claim is explicitly blocked rather than silently
using an alias. Receipt:
`research/laya_formation/receipts/evaluation-preflight-20261011.json`.

T038 executed all six formation/store arms over the same blinded 400 cases and
retained 400 normalized rows plus 80 exact post-state rows per arm. Fine-tuned
Laya and fine-tuned Laya with bounded escalation both achieved 1.0 synthetic
exact-state success, zero safety violations and zero errors; the escalation arm
made zero provider calls. Base Laya achieved 0.3625 with three safety
violations, while deterministic AtMem achieved 0.425 with 19. Jev remains a
400-row concrete-identity error arm. Three bounded Vast attempts for pinned
Qwen failed before inference (incompatible host CUDA, host DNS, then the frozen
15-minute startup ceiling), so its 400 rows are retained as
`VAST_STARTUP_TIMEOUT`, no Qwen outcome is inferred, and no Qwen comparison is
conclusive. All instances were destroyed; account delta was USD 0.01492406563
against the USD 2 cap. These results are synthetic only. Receipt:
`research/laya_formation/receipts/formation-evaluation-20261011.json`.

T039 froze a separate 80-query retrieval packet before retrieval execution,
with ten identical candidate IDs per query, deterministic hard negatives, 61
evidence-bearing queries and 19 negative/abstention queries. Every successful
arm ranked exactly the frozen membership through AtMem 2.3.9b1 lexical recall.
Fine-tuned Laya and deterministic AtMem tie at synthetic MRR@5 0.3798 and
Recall@5/10 1.0; base Laya reaches MRR@5 0.2951 and Recall@5/10 0.7705 because
14 positive queries were incorrectly abstained. Qwen and Jev upstream errors
receive zero retrieval credit. This shows formation improvement, not an
independent ranker improvement. Receipt:
`research/laya_formation/receipts/retrieval-evaluation-20261011.json`.

T040 joined the retained formation, exact post-state and fixed-pool retrieval
rows into 80 store-to-retrieve cases per arm. It attributes source, formation,
mutation, nomination, ranking, packing and delivery independently, then permits
success only when every stage passes and neither upstream stage has an error.
Fine-tuned Laya and its bounded-escalation profile pass 80/80; deterministic
AtMem and base Laya pass 7/80 under this strict all-stage definition, with
formation the first failure in 73 cases. Qwen and Jev errors receive zero
credit. Receipt:
`research/laya_formation/receipts/combined-evaluation-20261011.json`.

T041 ran 10,000 fixed-seed paired resamples at the scenario-cluster level and
emitted aggregate intervals, operation/memory-class tables, matchedness,
identity, safety and latency gates. Against deterministic AtMem, fine-tuned
Laya improves synthetic exact-state formation by 0.575 (95% CI 0.468–0.684)
and strict combined sufficiency by 0.9125 (95% CI 0.848–0.964), with zero
safety violations and no required-class loss. Retrieval MRR@5 is an exact tie
(difference and interval 0). Qwen, Jev, latency and production claims remain
blocked rather than treating errors as comparison losses. Report:
`research/laya_formation/reports/statistical-analysis-20261011.json`.

T042 publishes the checksum-bound synthetic evaluation report with exact
artifacts, matched metrics, paired intervals, costs, failures, reproduction
commands and the end-user quality/latency/cost trade-off. Formation, retrieval
and combined comparisons against Jev are each explicitly inconclusive. T042A
records the production claim as blocked because no separately frozen candidate
run exists for both LoCoMo and LongMemEval/store-to-retrieval; unrelated prior
repository results are not reused. Report:
`research/laya_formation/reports/evaluation-report-20261011.md`; binding receipt:
`research/laya_formation/receipts/evaluation-report-20261011.json`.

T043 and T044 changed the separately verified Hugging Face repositories to
public after owner approval. The exact dataset revision was anonymously
redownloaded and all 25 inventory files, 12,000 scenarios, 60,000 decisions,
schemas, digests and secret scan passed. The exact model revision was
anonymously redownloaded; all 13 repository files and bound model/question/
calibration digests passed, followed by a clean AtMem 2.3.9b1/Laya 0.4.2 CPU
load and valid inference. Receipts:
`research/laya_formation/receipts/hf-dataset-publication-20261011.json` and
`research/laya_formation/receipts/hf-model-publication-20261011.json`.

T045 and T046 add the complete 2.3.9b1 release note, public website manifest
and affected guides; align AtMem `2.3.9b1`, AtBot `0.1.1b1`, AtFlows
`0.1.4b3` and OpenClaw bridge `2.3.9-beta.1`; and tighten the optional runtime
to `torch>=2.3,<3` after a clean Intel-macOS Python 3.12 environment reproduced
the unsupported Torch 2.2 failure. The final full suite passed 2,329 tests with
83 optional skips, the AtBot suite passed 18 tests, and OpenClaw install,
typecheck, build, tests, smokes and package dry-run passed. Website inventory,
release metadata, wheel/sdist builds, metadata checks, sdist rebuilds, clean
base install, native Apple-silicon model inference and the published 2.3.8
upgrade/rollback journey passed. Final pre-publication artifact hashes and the
honest Intel-macOS/npm-audit boundaries are recorded in
`research/laya_formation/receipts/release-gates-20261011.json`.

## External execution status

`MEM` is mounted read-write and passed filesystem, partition-map and write/read
verification. The Windows SSH endpoint was reachable and its host key was trusted;
interactive password authentication succeeded without retaining password
material. The redacted capability receipt is
`research/laya_formation/receipts/windows-capability-20261010.json`: Windows 11
Pro, about 64 GiB RAM, 308 GiB free disk, Quadro P2000 with 4 GiB VRAM, driver
573.71, Python 3.12.6 and CUDA-enabled PyTorch 2.7.1+cu118. The pinned Laya
source and weights were installed only for the recorded smoke. Paid training is
complete; final cost was USD 1.5418210255 and the Vast instance was destroyed
after off-instance checksum verification.
