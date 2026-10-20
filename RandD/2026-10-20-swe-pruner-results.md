# GPU SWE-Pruner and Click comparison — 2026-10-20

## Outcome

The supported GPU implementation passed qualification. Actual source reads were
compressed, but end-to-end token savings were **not demonstrated**. In the
controlled check, the coding model immediately reread the original source through
the shell. This supports the integration diagnosis: compressed context must
replace work, rather than precede the same work.

All Vast.ai rentals were destroyed. The observed account-credit decrease was
$0.049352 against the $3 authorization; this is not a settled invoice.
The final instance listing contained zero account instances.

## Optional four-way comparison

One attempt per arm on the same previously inspected public Click issue
`b67832c`, using Claude Opus 5.5 medium and a common optional source-reader tool.
Native, Cognee, AtMem, and pruning-enabled order was fixed.

| Configuration | Task solved | Selected tests passed | Input tokens including cache | Output tokens | Agent seconds | Cold index seconds | Preparation seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| Native | 1/1 | 1,868 | 76,994 | 4,621 | 72.275 | 0 | 1.763 |
| Cognee | 1/1 | 1,868 | 57,724 | 3,980 | 49.544 | 11.293 | 16.783 |
| AtMem curated | 1/1 | 1,868 | 56,795 | 3,707 | 49.964 | 2.869 | 6.694 |
| AtMem, pruning enabled | 1/1 | 1,868 | 53,864 | 3,176 | 69.841 | 2.795 | 14.565 |

**All four arms made zero graph calls. The pruning-enabled arm made zero source
reader calls and zero scored pruning calls.** Native and Cognee made one and two
ordinary reader calls respectively; AtMem made none. Shell reads remained
available. The lower token counts therefore cannot establish graph or pruning
benefit. Provider/model variability, different trajectories and cache state are
not controlled by a single attempt. Preparation and agent time are separate
reported measurements; cold-index time is a preparation component, not another
additive stage.

## Controlled source-reader follow-up

Two new attempts used a separately frozen condition: both AtMem arms had to make
a successful relevant source-reader call before workspace commands were enabled.
Graph discovery remained available. The gate opened after the first read; it did
not prohibit later shell source reads. Full-source then pruned order was fixed.
No checkpoint, threshold or patch was tuned between attempts.

| Configuration | Task solved | Selected tests passed | Input tokens including cache | Output tokens | Agent seconds | Graph calls | Source reads |
|---|---:|---:|---:|---:|---:|---:|---:|
| AtMem, full source | 0/1 | 1,867/1,868 | 75,178 | 3,919 | 57.365 | 1 | 1 |
| AtMem + GPU SWE-Pruner | 1/1 | 1,868/1,868 | 88,552 | 4,791 | 76.306 | 1 | 2 |

Pruning used **17.8% more input tokens and 33.0% more agent time** in this check.
Both arms remained under time/token caps. The control's `budget_pass: false`
includes its functional failure; it does not mean it exceeded resource caps.
Cold-index times were 2.721/2.718 seconds; preparation was 6.554/15.724 seconds.
Tool counts were 9/11. All usage receipts were complete, with no read-schema
errors or patch-boundary violations.

The full-source patch failed `test_reported_help_collision[custom]`: it handled
the default help name but not a custom `--man` option. The value `sample` was
incorrectly parsed as a boolean. This is one incomplete generated patch, not
evidence that AtMem generally cannot solve the task. Likewise, one passing
pruned attempt does not establish a causal quality improvement.

### Actual scored pruning

| Source window | Original bytes | Returned bytes | Skimmer tokens before/after | GPU seconds | Whole-tool seconds |
|---|---:|---:|---:|---:|---:|
| `src/click/core.py:1130–1185` | 2,142 | 661 | 444 / 145 | 0.665 | 1.032 |
| `src/click/decorators.py:590–660` | 1,314 | 513 | 318 / 135 | 0.491 | 0.847 |

Combined source bytes fell from 3,456 to 1,174 (**66.0%**). Skimmer tokens fell
from 762 to 280; these are not Claude token counts. GPU inference totaled
1.155 seconds and whole-tool time 1.879 seconds.

Immediately afterward the agent ran:

```sh
sed -n 1125,1170p src/click/core.py; sed -n 595,640p src/click/decorators.py
```

This returned another **3,002 bytes of unpruned source**. The full-source control
also read additional source through `grep`. The experiment exposes duplicate
work, but does not attribute the entire token/time difference to that alone:
the models selected different windows, tests and subsequent actions.

## Runtime and scope

Successful backend: RTX A4000 16 GB, torch 2.8.0+cu128, transformers 4.57.1,
flash-attn 2.8.3.post2 with `flash_attention_2`, swe-pruner 0.1.1, einops 0.8.1.
Loaded model parameters were float32; the upstream wrapper controls inference
autocast. Threshold was 0.5, with no padding-removal modification or weight edits.
Model revision: `863cee3198c715c9df1faa422a3490e0832bb734`.
Backbone configuration revision: `e61197ed45024b0ed8a2d74b80b4d909f1255473`.
Two authentic pre-change qualification windows took 0.651/0.477 seconds.
Cold model loading took 32.375 seconds, separate from per-read latency.

Three rentals were used: two were destroyed during slow provisioning without
coding trials; the third qualified and completed both protocols. Claude and its
credentials stayed on the Mac. Only public source/goals went to the GPU.
No PyTorch dependency or pruning default was added to normal AtMem installation.
The implementation changes here are benchmark tooling, not a released feature.

The installed private candidate wheel retained version 2.3.8 metadata and SHA256
`0b94af55cf202c4624f47859c122af8dc51491af7b172c0344912aa001d93533`;
these measurements must not be attributed to the published 2.3.8 package.
Cognee used the pinned upstream SDK CODE route, not an independently authored
approximation; this deterministic route did not use embeddings or an LLM.
No experience memory or automatic source pack was enabled.

## Interpretation and next implementation boundary

This is one reused task, not a SWE-bench score, untouched confirmation set,
significance claim or production-native integration result. Frozen test
selection also skipped 25, deselected 31,001, and xfailed one test. Keep both
protocols and earlier October 19 experiments separate; do not pool attempts or
select only the winning trajectory. Confidence cannot honestly come from these
sample sizes.

The next integration should offer compact discovery followed by explicit
targeted expansion, preserve the source/evidence identity between reads, and
measure repeated source reads. It must make a useful read replace redundant
exploration without hiding necessary source or preventing correctness checks.
That needs a new preregistered comparison; no further trials were run here.

## Evidence and retention

Machine-readable results are adjacent:

- `2026-10-20-swe-pruner-fourway-results.json`
- `2026-10-20-swe-pruner-controlled-results.json`
- `2026-10-20-swe-pruner-vast-cost.json`

Encrypted benchmark archives on MEM:

- `/Volumes/MEM/AtMem-SWEbench-Threeway-20261019/click-pruner-fourway-20261020-gpu-complete/`
- `/Volumes/MEM/AtMem-SWEbench-Threeway-20261019/click-pruner-controlled-20261020-gpu-complete/`

Both complete exports include all seven recovered GPU artifacts, model audit,
agent/tool traces, patches, graders and installed wheel. Round-trip decryption
was verified. Keys remain in local benchmark directories, not MEM. Earlier
exports made before bulk GPU retrieval finished are retained; the `gpu-complete`
exports extend artifact coverage only, without rerunning coding attempts.
Six GPU audit calls include qualification/transport probes; only two were
scored agent pruning calls. Benchmark source-reader and rental safety tests:
16 passed at run completion. No package release is claimed.

## Public evidence publication

The readable trial records, decoded model/tool traces, source changes, graders,
protocols, retained harness snapshots, GPU artifacts and byte-identical encrypted
originals are published in the AtMem organisation:

[Hugging Face evidence dataset — immutable revision](https://huggingface.co/datasets/atmem/code-pruner-click-evidence-20261020/tree/ef51972e4efa11d5c7c58f2e5720e1a9bfb16edc).

All 374 uploaded files were downloaded and hash-checked before public visibility
was enabled. Anonymous access to the six trial summary records was then checked.
Private archive keys remain local. The readable copies remove credentials,
local home paths and IP addresses, and do not retain original event signatures;
the encrypted originals retain their original bytes. The manifest SHA256 is
`de6e00ca746051d8f19a69badbfaf6110b993495f7959b902750e21596e55e60`.

Publication tooling and card source are `tools/publish_pruner_evidence.py` and
`docs/evidence/swe-pruner-20261020-dataset-card.md`. The publication does not
repeat a solver, alter run results or expose owner keys. Source changes belong
on `feature/atmem-code-2.3.9`; `main` and package release tags are not changed.
