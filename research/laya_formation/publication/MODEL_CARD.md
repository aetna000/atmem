---
license: apache-2.0
base_model: convaiinnovations/laya
library_name: laya
tags:
  - atmem
  - laya
  - typed-decisions
  - memory-formation
  - synthetic-data
---

# AtMem Laya Formation Model v1

This is an optional, finite-choice System One model for AtMem memory-formation
workflows. It proposes one answer for each of five bounded questions:
`operation`, `memory_class`, `evidence_support`, `target_selection`, and
`retrieval_usefulness`.

It is not an authority system. AtMem must still authenticate the actor, enforce
scope and policy, load canonical state, validate evidence and targets, handle
deletion/revocation races, and authorize any mutation. A model answer is a
proposal, never permission to store, update, supersede, disclose, or retrieve
memory.

## Intended use

Use this artifact only through the version-bound AtMem Laya formation profile.
That profile supplies the exact question and choice definitions, tokenizer-
exact input packing, calibration bundle, abstention threshold, score validation,
deterministic fallback, and optional bounded AtBot escalation.

Expected end-user benefit after the full profile and compatibility gates are
complete is lower-cost, lower-latency handling of routine memory judgments on
the user's own CPU/GPU, with deterministic AtMem fallback for invalid,
unsupported, unavailable, or abstained decisions and governed escalation for
the small set of ambiguous cases. The model does not replace retrieval, the
memory store, AtBot, or AtMem policy enforcement.

Do not use it as a general chat model, an open-ended extractor, a security
boundary, an identity/authorization oracle, or an autonomous writer. Do not
send extra provider context merely because a model asks for it.

## Exact lineage

| Component | Immutable identity |
|---|---|
| Base checkpoint | `convaiinnovations/laya@7b928d828b7b0e022f929d9bd2e44165aa270148` |
| Base model SHA-256 | `891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c` |
| Laya source | `NandhaKishorM/laya@68804629e8ccd9d616d48a40e87de9fabbeae069` |
| Laya package | `laya==0.4.2` |
| Synthetic dataset | `atmem/atmem-laya-formation-v1@4436089b38cbe3a5374aaaa92c4c77703cdbf668` |
| Dataset manifest | `d67d371c8c1d6de85a0293cded5aa5b3f7d078e92197130ce1f9edef68e863d4` |
| Selected run | `rlcd-410239-20261010T152813Z` |
| Model SHA-256 | `f2ba3dd7679da45aabab4cac30e9a079baeb2dc98229ff3b1618e6a06fc6d683` |
| Question digest | `7a3cd0e13d99db02a1e53e51a63fad921e754ac5bbc2376b8a888c1033900f0e` |
| Calibration digest | `b165d4b7d554cdbda5a889baf7059c3f43ba2774d68754e4fa3aeb63f5f0e067` |
| Portable export digest | `6f7d53c18431c27baa617ab95ebcc4cad669917a6508145fa001eb7c8e799900` |

The dataset contains 12,000 fictional scenarios and 60,000 decisions. Its
group-disjoint decision splits are 39,600 train, 6,500 validation, 6,700
calibration, and 7,200 sealed test. No production or user memory was used.

## Training

Training used full-encoder upstream RLCD/proper scoring with seed `410239`, four
epochs, micro-batch 32, gradient accumulation 2 (effective batch up to 64),
encoder learning rate `2.5e-5`, head learning rate `1e-4`, minimum learning rate
`1e-6`, weight decay `0.01`, gradient clip `1.0`, four RL samples, sigma
`0.4 → 0.1`, `w_sph=0.75`, and `w_rps=1.0`. RLCD ran in FP32 because the
upstream FP16 path skipped an initial optimizer update after overflow. Training
used PyTorch `2.11.0+cu128` on one RTX 5090 and took 4,390.91 seconds.

A soft cross-entropy control and RLCD produced an exact tie under the
predeclared validation/calibration ranking. The frozen stable objective-name
tie-break selected RLCD; sealed data was unavailable to selection.

## Calibration and abstention

Calibration was fit only on the isolated 6,700-decision calibration split, with
1,340 examples for each question. The external `calibration.json` is mandatory:
it binds the selected model and questions, installs type temperatures
`[1.0, 1.0, 1.0]`, a `choice:3-5` temperature of `1.0`, and a conservative
`choice:3-5` minimum-confidence threshold of `1.0` for target error `0.10`.
The original temperatures in `rl_agent_config.json` are base-checkpoint values;
AtMem must not silently serve this derivative without applying the bound
external calibration bundle.

## Synthetic evaluation

All figures in this table are synthetic. They do not establish production or
public-corpus performance.

| Split | Items | Accuracy | Macro-F1 | NLL | Brier | ECE |
|---|---:|---:|---:|---:|---:|---:|
| Validation | 6,500 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| Calibration | 6,700 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| Sealed test | 7,200 | 1.0 | 1.0 | `2.4447e-13` | `3.5791e-25` | `2.4447e-13` |

The sealed test had 1,440 examples for each of the five questions, zero failed
decisions, zero truncation, no missing expected class, no prediction collapse,
and class-prior L1 drift of zero. The calibrated threshold accepted all 7,200
answers at 100% accuracy. A separately sampled, blinded sealed audit was signed
by an independent `gpt-5.5` reviewer and passed 400/400 with zero critical
findings. Neither audit nor sealed metrics were used for selection or tuning.

Two clean CPU reloads and one clean Apple MPS reload agreed on 100/100 fixed
nonsealed probes. Same-backend choice agreement was 1.0 with zero normalized-
score delta. CPU/MPS choice agreement was 1.0, maximum normalized-score delta
was `7.2023e-16`, and aggregate accuracy delta was zero percentage points.

## Input and compatibility contract

The governing sequence limit is 512 tokens and the question-head limit is 192.
The question and every choice must fit intact. AtMem uses its shared tokenizer-
exact whole-range packer and disables silent truncation; overflow produces an
explicit receipt and deterministic fallback.

The artifact format is Safetensors plus Laya tokenizer/encoder configuration,
`questions.json`, `calibration.json`, `training-manifest.json`, and
`artifact-manifest.json`. The clean verification environment used Python 3.12,
Laya 0.4.2, PyTorch 2.11.0, Transformers 4.57.1, Safetensors 0.6.2,
Hugging Face Hub 0.36.0, and NumPy 2.2.3. CPU and Apple MPS clean reloads are
verified. Linux CUDA was used for training. The full Windows/macOS/Linux
installed-wheel compatibility matrix is a separate product-integration gate;
do not infer unexecuted support from framework device names.

## Escalation and failure behavior

AtMem should accept only finite, schema-valid scores bound to the exact model,
question, calibration, tokenizer and request digests. Missing artifacts,
identity mismatch, nonfinite/invalid scores, overflow, abstention, unavailable
hardware, policy denial, stale state, or provider failure must not widen access
or silently fall through to mutation.

The deterministic AtMem decision remains the offline fallback. If the optional
AtBot escalation policy is enabled, AtMem sends only the minimum already-
authorized input under explicit schema, budget and provider-egress controls.
The provider response is revalidated through the same authority boundary;
offline or invalid escalation returns fallback/review, not an unsafe guess.

## Limitations

- Training and evaluation use synthetic fictional data from one policy family;
  perfect held-out scores can reflect generator/oracle regularity.
- No LoCoMo, LongMemEval, production memory, adversarial public corpus, or
  real-user usability result is claimed here.
- No matched Jev, Qwen, deterministic AtMem, retrieval, or store-then-retrieve
  superiority result is claimed here. Those require the separate frozen Spec
  041 benchmark and safety/identity gates.
- Latency, energy, and peak memory vary substantially by backend. The full
  sealed MPS evaluation on a 16 GiB Mac was intentionally exhaustive, not a
  serving-latency benchmark.
- The model can confidently reproduce the synthetic oracle and still be wrong
  on novel, malformed, multilingual, adversarial, or out-of-distribution input.
- Public visibility does not make the model safe to invoke without AtMem's
  authority, packing, calibration, fallback, and receipt contracts.

## License

The base model, pinned Laya source, synthetic dataset, and this derivative are
Apache-2.0. See `LICENSE` in the repository. This card describes technical
constraints and is not a substitute for reviewing the license text.
