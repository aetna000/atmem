---
pretty_name: AtMem Code — Click GPU Pruning Evidence (2026-10-20)
language:
- en
license: other
license_name: mixed-evidence-and-upstream-source
license_link: https://huggingface.co/datasets/atmem/code-pruner-click-evidence-20261020/blob/main/README.md#licensing
size_categories:
- n<1K
tags:
- code-memory
- software-engineering
- benchmark-evidence
- context-compression
configs:
- config_name: trials
  default: true
  data_files:
  - split: test
    path: data/trials.jsonl
- config_name: events
  data_files:
  - split: test
    path: data/events.jsonl
---

# Click: native, Cognee, AtMem, and GPU source pruning

Six recorded coding attempts on one historical Click issue, `b67832c`. This
dataset makes the successful and failed attempts inspectable: measurements,
tool calls, model CLI streams, proposed source changes, test output, protocols,
GPU qualification and original encrypted archives. It is **evaluation evidence,
not memory-model training data or a SWE-bench leaderboard submission**.

## Results at a glance

### Optional reader: four configurations, one attempt each

| Configuration | Task passed | Selected tests passed | Input tokens including cache | Agent seconds |
|---|---:|---:|---:|---:|
| Native | Yes | 1,868 | 76,994 | 72.275 |
| Cognee | Yes | 1,868 | 57,724 | 49.544 |
| AtMem curated | Yes | 1,868 | 56,795 | 49.964 |
| AtMem, pruning enabled | Yes | 1,868 | 53,864 | 69.841 |

No arm called the graph. The pruning-enabled agent did not invoke the reader.
The ranking therefore does not demonstrate graph or neural-pruning savings.

### Controlled reader: two separate new attempts

| Configuration | Task passed | Selected tests passed | Input tokens including cache | Agent seconds |
|---|---:|---:|---:|---:|
| AtMem full source | No | 1,867/1,868 | 75,178 | 57.365 |
| AtMem + GPU SWE-Pruner | Yes | 1,868/1,868 | 88,552 | 76.306 |

Both agents had to read source before workspace commands were enabled. Pruning
actually ran twice: 3,456 source bytes became 1,174 (66.0% reduction), in 1.155
GPU seconds combined. The agent subsequently reread 3,002 unpruned bytes through
the shell. Total input increased 17.8% and agent time 33.0%. Source compression
did not become end-to-end token savings. The full-source patch missed a custom
help-option collision case. One pair cannot establish a causal quality benefit.

## Browse and use

The default dataset viewer shows all six trial summaries. Select `events` for
decoded, privacy-redacted event payloads. Nested payloads use JSON strings to
keep heterogeneous events readable without forcing a misleading common schema.

```python
from datasets import load_dataset

trials = load_dataset("atmem/code-pruner-click-evidence-20261020", "trials", split="test")
events = load_dataset("atmem/code-pruner-click-evidence-20261020", "events", split="test")
print(trials.to_pandas())
```

Use an immutable dataset revision when reproducing an analysis; the publication
receipt in the [AtMem repository](https://github.com/aetna000/atmem/tree/feature/atmem-code-2.3.9/RandD)
records the uploaded revision and checksums.

| Directory/file | Contents |
|---|---|
| `data/trials.jsonl` | Six summary rows; tokens, tests, latency and actual tool usage |
| `data/events.jsonl` | Readable event payloads, prompts and complete attempt/grade records |
| `trials/` | Per-attempt source changes, decoded CLI stream, tool audit and grader output |
| `protocols/` | Separate fixed four-way and controlled-reader protocols |
| `gpu/` | Seven recovered runtime/qualification/audit/source artifacts |
| `harness/` | Privacy-redacted source snapshots retained by the original archive |
| `reports/` | Detailed interpretation, machine-readable results and rental-cost record |
| `archives/` | Byte-identical signed, recipient-encrypted originals; keys remain with the owner |
| `manifest.json` | SHA256 and byte size of every other publication file |
| `verification.json` | Decryption verification, original event digests and redaction counts |

Readable exports replace credentials, local home paths and IP addresses. They
are derivatives, not the original signed bytes. Encrypted originals provide
owner-recoverable preservation; public readers can analyze the readable files
without private keys. Environment files, SSH keys, archive secret keys, runtime
databases and owner configuration are not uploaded. No solver was rerun for
publication. No new labels or conversation examples were generated.

## Experimental scope

Claude Opus 5.5 medium, one fixed-order attempt per arm, one previously inspected
public task. Cached tokens are included in input; GPU skimmer tokens are not
Claude tokens. The two protocols must not be pooled. Frozen grading also skipped
25 tests, deselected 31,001 and xfailed one. No experience memory was used.
These are workflow diagnostics, not an untouched confirmation set or evidence
of general superiority. Full method/runtime details are in `reports/`.

RTX A4000 16 GB; torch 2.8.0+cu128; transformers 4.57.1; flash-attn 2.8.3.post2;
swe-pruner 0.1.1; unmodified upstream wrapper, threshold 0.5. Model revision
`863cee3198c715c9df1faa422a3490e0832bb734`. Loaded parameters were float32;
the upstream wrapper controls inference autocast. All rentals were destroyed;
observed credit decrease approximately $0.05, not a final settled invoice.

## Licensing

AtMem-authored harness/report material is Apache-2.0 (`LICENSE-ATMEM`).
Incorporated Cognee material remains under its upstream license and notices
(`LICENSE-COGNEE`, `NOTICE-COGNEE.md`). Click source excerpts and source-derived
patches remain under BSD-3-Clause (`LICENSE-CLICK`, copied from the pinned parent
commit rather than a changing default branch).
Upstream license terms are not replaced by this evidence publication. Model
weights are referenced, not redistributed. The archive does not claim ownership
of upstream software or confer a new blanket license over its contents.
