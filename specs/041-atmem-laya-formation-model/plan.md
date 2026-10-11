# Implementation Plan: AtMem Laya Formation Model

**Spec**: [spec.md](spec.md)
**Target**: AtMem `2.3.9b1`
**Status**: Draft for approval; execution and external spending are not authorized

## Delivery strategy

Deliver the feature in four independently gated layers: protocol and synthetic
data; reproducible model training/calibration; optional governed runtime
integration; and matched evaluation/publication. Spec 040 stays authoritative.
Dataset and model can publish after their own gates even if Jev superiority is
not established. Package release requires the full product and release gates.

## Technical context

**Runtime**: Python 3.10–3.13; existing AtMem library, CLI, local service,
dashboard, MCP and host adapters
**Model**: exact revision of `convaiinnovations/laya`, optional inference extra,
Safetensors-only public export
**Training**: upstream-supported Laya tooling pinned after a reproducibility
spike; PyTorch device routes for Windows CUDA, macOS MPS/CPU, Linux CUDA/CPU
**Data**: generated JSONL/Parquet plus manifest and checksums; heavy work rooted
at `/Volumes/MEM/AtMem-Laya-Formation/` on the Mac
**Evaluation**: deterministic fixtures, installed-artifact integration tests,
paired cluster bootstrap, frozen public benchmark adapters outside product code
**External services**: Hugging Face for two public artifacts; Jev only for
explicitly authorized comparison; Vast.ai only after both local routes fail

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
| Production benchmark evidence | Synthetic evaluation is labeled synthetic; public benchmark evidence separate | cards and claim lint |

No constitutional exception is requested.

## Architecture

### 1. Typed decision boundary

Add a versioned `FormationDecisionRequest/Response` contract. The request
contains authorized facts, current candidates, finite option identifiers and
question definitions. It omits authority the model does not need. The response
contains only selected identifiers/scores and diagnostics. A governance adapter
reloads canonical records, verifies evidence and policy, and alone may call
Spec 040 mutation services.

The request packer uses the pinned tokenizer, reserves the full question and
choice set, counts special tokens and admits evidence only as deterministic
source-range units. It emits a loss/overflow receipt and escalates or reviews
when the mandatory fields cannot fit; silent tokenizer truncation is disabled.

### 2. Laya profile and deterministic fallback

Implement Laya behind an optional runtime extra and lazy artifact resolver.
Activation pins an immutable revision and validated question-schema digest.
Device selection is explicit and doctor-tested. Any unavailable dependency,
revision mismatch, calibration failure, malformed choice or timeout routes to
the deterministic path or review according to policy.

### 3. Bounded generative escalation

An escalation policy evaluates only named reasons. It sends minimal authorized
evidence through the existing AtBot provider abstraction using a strict output
schema and budgets. The returned proposal goes back through the same authority
adapter. Laya remains useful with escalation disabled or offline.

### 4. Synthetic scenario compiler

Build fictional world states and ordered evidence events from versioned
templates. An executable oracle derives canonical state and typed decisions.
Independent validators reconstruct state, check answer membership, enforce
privacy/license rules, cluster paraphrases and freeze disjoint train,
validation, calibration and sealed-test manifests. Store rationales as audit
metadata, not inference targets unless a later reviewed experiment requires it.
Dataset export and runtime requests call one shared versioned packing module;
golden parity tests reject any byte, ordering, token-count or overflow-receipt
difference, preventing train/serve skew and invalid calibration.

### 5. Training and calibration

Freeze base revision, dataset revision and environment lock. Run a representative
smoke on Windows and Mac, recording capability, throughput, memory and expected
completion. Choose a viable local route. Only if neither is viable, query current
Vast offers and select under the total-cost cap. Train fixed-seed objective
controls, select on validation/calibration only, open the sealed test once, then
export/reload in a clean environment.

### 6. Evaluation

Use one frozen scenario manifest for all arms. Formation/store evaluates exact
post-state. Retrieval uses fixed candidate membership and permits only ranking/
abstention differences. Combined tests replay formation then future queries and
attribute the first failing stage. Resolve Jev's concrete model identity before
calls. Reports include per-item raw results, per-class tables, latency/cost,
paired cluster bootstrap intervals and explicit gate outcomes.

Synthetic and production-evidence tiers are separate. Synthetic results may
support only a clearly named synthetic benchmark statement. A production-level
superiority statement additionally runs a disjoint public held-out protocol at
intended scale under Spec 040 and the constitution, including LoCoMo and the
applicable LongMemEval/store-to-retrieval workflow; failure or absence leaves the
production claim blocked without blocking honest artifact publication.

### 7. Publication and release

Create separate private Hugging Face staging repositories. Upload by immutable
manifest using an environment token, scan/download/reload, then make public and
record revisions. Package integration follows only after artifact identities are
frozen. Release work follows `docs/release-coordination.md`; the website source-
pin PR remains owner-reviewed and unmerged by the agent.

## Work phases

1. Freeze contracts, schemas, sources, threat model, claims and external-cost
   protocol.
2. Implement and audit the synthetic dataset; stage it privately.
3. Qualify Windows and Mac; conditionally qualify/rent Vast; train, calibrate,
   export and stage the model privately.
4. Implement optional Laya runtime, escalation, setup/status and fallback tests.
5. Run matched evaluation and decide only the claims supported by evidence.
6. Publish the two Hugging Face artifacts, then prepare and execute the
   coordinated beta release under separate approvals/gates.

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
  candidate membership, missing rows, paired statistics, latency effect size and
  the separate synthetic/production claim wording.
- Private-to-public publication verifies downloaded files and digests, not merely
  successful upload calls.
- Release gates verify source commit, annotations/tags, workflows, GitHub release,
  PyPI, npm and website states independently.

## Risks and controls

| Risk | Control |
| --- | --- |
| Laya is specialized but weak zero-shot or overconfident | fine-tune, isolated calibration, abstention/review and base-Laya control |
| Synthetic patterns leak across splits | group split on four correlated keys plus near-duplicate checks |
| Fine-tune learns label priors/collapses | per-question balance, adversarial swaps, collapse metrics and objective control |
| Model output gains authority | finite opaque IDs plus canonical revalidation and mutation tests |
| Jev is a moving service | resolve exact identity/config at run time; block claims if unresolved |
| Cheapest rental becomes expensive | total-cost estimate, USD 20 hard cap, resume proof and immediate teardown |
| Credentials leak through tooling | environment/interactive secrets, redacted subprocesses, scans before upload |
| Cross-platform promise exceeds evidence | claim only tested device/OS profiles and publish the matrix |
| Spec 040 changes concurrently | bind integration to versioned public contracts; re-run alignment before merge |
| 2.3.8 is not yet published | allow bounded development against a named candidate, but block final upgrade evidence and release until rerun against the verified PyPI artifact |

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
