# Current curated AtMem vs upstream Cognee vs native: short Click diagnostic

One previously inspected task (`b67832c`, help-name collision), one fresh attempt
per arm. Same subscription Claude Opus 5.5, medium effort, source-only offline
workspace command tool, 240-second / 30-tool caps. Graph tools were optional;
neither provider received an automatic source pack. No experience supplied.

| Arm | Task solved | Frozen tests passed | Total input tokens (including cache) | Output tokens | Agent seconds | Cold index seconds | Preparation seconds, including index |
|---|---:|---:|---:|---:|---:|---:|---:|
| Native | 1/1 | 1,868 | 40,969 | 3,521 | 47.960 | 0 | 1.192 |
| Cognee | 1/1 | 1,868 | 62,998 | 4,531 | 69.283 | 13.553 | 22.204 |
| AtMem curated | 1/1 | 1,868 | 61,880 | 4,366 | 58.855 | 3.191 | 7.571 |

All usage receipts complete; all attempts within caps, no patch violations.
Grader also reports 25 skipped and 31,001 deselected parameterized cases under
the existing frozen exclusions; this is not every possible Click test variant.
Preparation includes qualification work, not only normal user indexing.

## Interpretation

Actual provider query calls: **zero for both Cognee and AtMem** (native command
calls: 7 / 9 / 8). The model solved the issue using native source operations.
This measures enabled-tool integrations on an easy task, not the relative
quality of retrieved evidence. There is no demonstrated memory benefit here.
Tool-list exposure was verified: native advertised `workspace_command`; Cognee
also advertised `code_search`; AtMem also advertised `code_query`. Serialized
tool inventories were 445 / 1,151 / 1,694 UTF-8 bytes respectively. These byte
counts are not model-token counts and cannot explain the entire usage delta.
AtMem used 51.0% more total input than native; Cognee used 53.8% more. AtMem was
1.8% below Cognee on input and 15.1% faster in agent time. These single-attempt
differences are descriptive, not reliable estimates or causal savings.
Fixed native/Cognee/AtMem order, cache differences, provider variability, prior
inspection and a single small task prevent generalization/significance claims.

Although the harness requested `MAX_THINKING_TOKENS=0`, actual provider receipts
report 489 / 977 / 896 thinking tokens. The request did not enforce zero
thinking; do not describe the observed trials as thinking-free. Total output
and full per-model usage remain in the underlying result file.

## Artifact identity and evidence

- AtMem: private installed acceptance wheel, SHA256
  `0b94af55cf202c4624f47859c122af8dc51491af7b172c0344912aa001d93533`;
  `curated` MCP profile, no source-pack injection. Wheel metadata 2.3.8 is
  a private candidate identifier, not a claim about published 2.3.8.
- Cognee: actual upstream 1.6.4 SDK at
  `f154b32a9e544dac73e7ddf2010327cf9988edcd`, Enola extraction + persisted
  deterministic CODE route, no embeddings or retrieval LLM. Installed 2,663
  Python files match the pinned source, manifest SHA256
  `8859aa32e5ad88ce790a9373dc3a92de1b1c6a23c43ac00dad001466df0c3656`.
  The read-only benchmark transport calls the real SDK; it is not the complete
  upstream official MCP server or a test of other Cognee routes.
- Protocol: `specs/043-click-historical-replay/curation-threeway-20261019.md`.
- Local results and encrypted raw streams/patches/grades:
  `/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/click-curation-threeway-qualified-20261019/`.
- The first `click-curation-threeway-20261019` preparation failed before model
  dispatch because product key paths were initialized before the isolated home
  was set. Retained separately. Corrected initialization before imports; no
  model trial retried and no product change made to improve this result.
- Verified encrypted archive:
  `/Volumes/MEM/AtMem-SWEbench-Threeway-20261019/click-curation-threeway/click-curation-threeway-20261019.encrypted.json`.
  Recovery keys remain in the restricted local benchmark directory, not MEM.

SWE-Pruner is a separate subsequent qualification, not a feature exercised by
these three trials. Do not attribute these results to learned pruning or
claim a 20%/50% token saving.
