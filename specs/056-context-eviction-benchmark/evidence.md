# Exact duplicate-read replay

Four synthetic sessions supplied 28 cumulative request snapshots. The
benchmark used zero model calls. It counts `o200k_base` tokens in canonical
request JSON with tiktoken 0.12.0. The same tokenizer and serialization
apply to both arms, including the cost of reference text.

| Subsequent tool batches before eligibility | Baseline request tokens | Projected request tokens | Net reduction | Candidate share of final messages |
| --- | ---: | ---: | ---: | ---: |
| 2 (default) | 153,446 | 131,151 | 22,295 (14.53%) | 19.10% |
| 0 (sensitivity check) | 153,446 | 115,226 | 38,220 (24.91%) | 28.65% |

With grace 2, the repeat-heavy session went from 66,930 to 44,635
estimated tokens. The late-repeat, changed/partial/failed, and read-light
sessions saved zero. A duplicate that first appears in the final request
has fewer opportunities to save tokens. Final candidate share sums the
encoded body estimates marked in each final snapshot and divides by the
encoded final message arrays. Net reduction re-encodes entire requests,
so it includes reference overhead and token-boundary effects.

This deliberately constructed corpus exercises the mechanics. Its family
mix does not estimate OpenClaw workloads. Provider chat templates,
provider cache usage, task success, recovery calls and latency still need
live measurement. The 64% in Contexture is a final-history candidate
measurement on a different corpus using broader supersession rules.
[Contexture §4.1](https://arxiv.org/html/2611.26980v1#S4.SS1)

## Reproduce

```sh
uv run --no-project --with tiktoken==0.12.0 python -m tools.benchmark_context_eviction --grace 2
uv run --no-project --with tiktoken==0.12.0 python -m tools.benchmark_context_eviction --grace 0
```

Pass `--trace FILE` to compare authorized request snapshots. The fixture
generator in the comparator provides a complete example. Each JSON input
contains `format: "atmem-context-eviction-trace-v1"`, a `corpus` label,
and `sessions` with distinct `id` values. Each session has ordered
`requests`. Each entry contains a `request` object with OpenAI-style
`messages` plus `successful_read_ids` from the host's correlated tool
results. The producer is responsible for supplying one scoped session and
identifying successful, complete reads within the requested range. The CLI
reads the file locally and reports counts, the hash of the canonical JSON,
and the supplied corpus and session labels. Use non-identifying labels in
reports intended for sharing. A live pilot needs a host-specific capture
adapter with verified model input, scope, and tool-call correlation.

- [Default grace report](synthetic-grace-2.json)
- [Zero grace report](synthetic-grace-0.json)

## Prefix changes

The two-batch projection shortened the shared message prefix on two
requests. Immediate replacement did so on three. These counts compare
adjacent request snapshots with their native message prefix lengths.
They describe where a rewrite occurred. Provider cache hits and re-prefill
cost depend on the serving runtime. Across the four last observed
requests, the net full-request reduction was 19.00% with the grace
window and 28.51% without it. Later native compaction may shorten a
trace's final request relative to earlier requests.
When a newer copy matures, earlier references can point to a different tool
result and shorten the shared prefix again. A live projection must keep
each reference and its retained target together through native compaction.

On first use, tiktoken can fetch its public encoder vocabulary. Version
0.12.0 verifies the `o200k_base` vocabulary SHA-256
`446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`.
Once the vocabulary is cached, the benchmark can run without network
access.

## Read-only review

Claude Code Sonnet reviewed the benchmark source, tests, and synthetic
results with tools disabled. The first review found no blocking rewrite
defects and flagged short-result inflation, prefix changes, ambiguous
counter names, missing final-request net results, and insufficient controls.
The comparator now skips costlier references and projections, records
where prefixes shorten, labels repeated replacement instances, and reports
net reductions on the final requests. Regression tests cover the grace
boundary, tiny results, same-batch reads, unmatched results, and incomplete
batches. The second review found no request-preservation blockers and
requested the label disclosure, producer-verification wording, and
compaction constraint above. Both saved reports reproduced byte-for-byte,
including a rerun through `--trace`.

## Python SDK preview

Pass a policy as `read_deduplication=` to `PydanticAIAtMemAdapter` or
`create_langgraph_middleware`. Omitting the argument leaves the current
model request path in use. Custom LangGraph model nodes can call
`project_langchain_messages(messages, runtime, policy)` before invoking
their model.

```python
from atmem.context_engine.read_deduplication import ReadDeduplication, VerifiedRead

policy = ReadDeduplication(
    verified_reads=verified_reads_for_current_run,
    count_tokens=count_model_tokens,
    grace=2,
)
```

The two callables are supplied by the application. The verifier receives the
framework runtime and a tuple of native messages. Create a receipt with
`VerifiedRead.from_result(call_id, arguments, text)` from the actual tool
execution. The call ID, argument hash, and exact result hash must match the
request. Supply only receipts from successful `read` calls in the same
authorized run and workspace, with stable path resolution and exact,
complete text for the requested range. Both callbacks run inline and should
use local, non-blocking work.
Return an empty iterable when there is no verified evidence. Use the chosen
model's tokenizer for the counter. This estimate applies to the normalized
message projection and excludes provider-specific framing and cache pricing.

The Pydantic AI hook and LangChain model middleware project a copy. The host's
native tool results remain available for audit and subsequent requests.

The SDK checks used Pydantic AI 2.0.0 and 2.61.0, LangGraph 1.2.7, and
LangChain 1.3.11. Local stand-in models received one reference and one full
result when enabled. Native histories retained both full results. With no
matching receipt or after a verifier or counter failure, the SDK preserved
the original messages. Claude Code's read-only review led to the argument
and result hash checks and the fallback behavior.
