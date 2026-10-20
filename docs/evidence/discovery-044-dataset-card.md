---
language:
- en
license: other
license_name: mixed-benchmark-evidence-apache-2.0-and-bsd-3-clause
license_link: https://huggingface.co/datasets/atmem/code-discovery-benchmark-evidence-20261020/blob/main/LICENSE-ATMEM
task_categories:
- other
tags:
- code
- agent-memory
- evaluation
- tool-use
configs:
- config_name: trials
  default: true
  data_files:
  - split: test
    path: trials.jsonl
- config_name: traces
  data_files:
  - split: test
    path: traces.jsonl
---

# Repository discovery: native lexical, Cognee CODE and AtMem

Twelve real subscription-backed coding attempts on a historical Click issue,
with executable grading, complete token receipts, tool traces and recoverable
encrypted evidence. Two distinct conditions are provided: optional discovery
and an explicit request to begin with a self-selected discovery query.
Six metric rows from one SWE-bench Verified qualification task are also provided,
separately identified in the same table. Its raw evaluator evidence stays private.

## Explore the data

Select **trials** in the dataset viewer for the comparison table. Each row shows
the condition, agent, backend, task outcome, total input including cache, output,
agent/index/setup time, lookup attempts and nonempty lookup responses. Select
**traces** to inspect readable event payloads and exact tool requests/results.
The traces configuration covers Click and its qualification launches, not the
private SWE evaluator. The native locator's transient AST preparation is included
in setup/agent timing; the index column measures persistent graph construction.

| Field | Meaning |
|---|---|
| `protocol` | Optional or requested-consultation condition; do not pool them |
| `host`, `backend` | Coding CLI and configured discovery backend |
| `task_passed` | Entire frozen executable grader passed |
| `input_tokens_including_cache` | Full session input, not just retrieved text |
| `agent_seconds` | Coding session wall time, excluding preparation/grading |
| `index_seconds` | Separately measured graph construction |
| `discovery_attempts` | Calls attempted, including malformed requests |
| `nonempty_discovery_responses` | Successful responses containing locations |

All backends use the same navigation schema and offline source read/edit/test
tool. The native comparator is an AST-backed lexical locator, **not an untouched
native CLI**. Cognee uses its actual pinned deterministic CODE extraction/query
path, not AtMem's incorporated implementation or its other search modes.

## Evidence and interpretation

This is one previously inspected task, one attempt per cell per condition: a
diagnostic, not a full coding-benchmark score. The optional condition had zero
navigation use. An error or empty lookup is not treated as use of code evidence;
token differences alone cannot establish a backend benefit.

`archives/` contains original signed/encrypted event exports. Recovery keys stay
with the owner and are not uploaded. Readable traces are decoded, privacy-redacted
derivatives with separate hashes; original signatures do not apply to them.
Independent recovery is checked with access to the original vault disabled.
All qualification failures are retained separately from scored task attempts.

If present, `swe-pilot-metrics.json` contains only the metric projection of one
SWE-bench Verified qualification task. It is not the full 500-task benchmark.
SWE evaluator/reference material is excluded from this public export.

## Versions and licenses

AtMem source-preview wheel SHA256:
`77a67773e33adcfe2c8a60d5a1da29326f0bc2dfe27663fc5f14297d0e272d92`.
The exact wheel is retained under `artifacts/` for reproduction. It is a private
source-preview build with 2.3.8 metadata, not a new public package release.
Cognee source revision: `f154b32a9e544dac73e7ddf2010327cf9988edcd`.
Click parent: `8c1a0a7abbc1c36f70d1f65f3604acc46c5ce6ab`.
Coding agents: Claude Code/Opus 5.5 and Codex/GPT-6 Luna; host/model identities
are retained in traces. Copilot's native account policy blocked third-party MCP,
so it has no scored cells. No policy bypass or paid API fallback was used.

AtMem/Cognee code is Apache-2.0; Click code is BSD-3-Clause. See the included
license files. These are evaluation records, not a memory-training corpus.
