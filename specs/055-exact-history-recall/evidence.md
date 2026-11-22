# Exact-history retrieval diagnostic

This pilot used two disjoint synthetic splits, each with 168 history lines and
24 questions. Sixteen questions ask for available evidence and eight test
missing or foreign-scope evidence. The native arm used encrypted history import
and the default V3 `context-fast` engine. The literal arm searched only
authorized fixture lines using a substring visible in the question. The scope
controls test the native authority boundary. The literal arm models the same
scope filter and does not implement an authorization system.

| Split and byte ceiling | Native before | Native after packing fix | Literal comparator |
| --- | ---: | ---: | ---: |
| Development, 4,096 | 24/24 | — | 24/24 |
| Development, 512 | 16/24 | 24/24 | 24/24 |
| Holdout, 512 | 16/24 | 24/24 | 24/24 |

Every arm returned all 16 available targets on each run. The eight native
failures at 512 bytes were missing and foreign-scope cases. AtMem attempted to
cite ranges the packer had excluded and the governance boundary rejected the
package. The fix recomputes or withholds sufficiency after packing. An omitted
side of a conflict cannot become a sufficient answer. All eight cases returned
empty context without error on the holdout. No checked foreign target was
returned. In each arm the older value accompanied the current value in all
four temporal cases. This pilot therefore establishes current-value delivery,
with temporal answer selection still unmeasured.

At 4,096 bytes, unmodified AtMem returned 12,164 total context bytes and the
literal comparator returned 1,292. On the 512-byte holdout they returned 3,252
and 1,292 bytes, respectively. These counts reflect the representations
returned by each arm. The literal arm omits AtMem's provenance and context
formatting. Latency is recorded per case and is diagnostic only, since the
native arm uses an encrypted store and durable auditing, while the comparator
scans fixture text in memory. The benchmark made zero model calls.

## Reproduce

Use Python 3.12 and install the encrypted-storage dependency from the repository
root with `python -m pip install -e '.[code,dev]'`.

```sh
python -m atmem.benchmark.exact_history --output /tmp/atmem-dev-4096.json
python -m atmem.benchmark.exact_history --output-bytes 512 --output /tmp/atmem-dev-512.json
python -m atmem.benchmark.exact_history --split holdout --output-bytes 512 --output /tmp/atmem-holdout-512.json
```

Baseline source is `f8639c9`. Before changing retrieval, the development
reports were saved from the source checkout. The holdout baseline ran the same
harness against an isolated installed package whose native service hash matches
that commit. The held-out reports include engine hashes and the shared fixture
digest. Use new output paths when rerunning the benchmark.

- [Development baseline, 4,096 bytes](evidence/development-baseline-4096.json)
- [Development baseline, 512 bytes](evidence/development-baseline-512.json)
- [Development with packing fix, 512 bytes](evidence/development-packing-fix-512.json)
- [Holdout baseline, 512 bytes](evidence/holdout-baseline-512.json)
- [Holdout with packing fix, 512 bytes](evidence/holdout-packing-fix-512.json)

## Direct comparison with upstream GrepMem

We ran the published GrepMem `grep_history` function at commit
`b7e3744c2f7489feac4060b379be6936960dc7bd` on the same 512-byte holdout. The
harness supplied the literal anchor visible in each question, escaped to form
a regex. The history contained only the authorized lines. The byte counts
include GrepMem's headings, pagination text, and no-match messages.
[Pinned GrepMem source](https://github.com/limenlp/GrepMem/tree/b7e3744c2f7489feac4060b379be6936960dc7bd)

| Arm | Evidence cases passed | Total returned bytes | Bytes on 16 answerable cases |
| --- | ---: | ---: | ---: |
| AtMem with packing fix | 24/24 | 3,252 | 3,252 |
| Upstream GrepMem lookup | 24/24 | 3,648 | 3,372 |
| Minimal literal comparator | 24/24 | 1,292 | 1,292 |

Both upstream GrepMem and AtMem returned the current and earlier values in all
four temporal cases. The original byte advantage belongs to the minimal
comparator. Actual GrepMem lookup had similar output size on the answerable
cases. This comparison supplies the search term and uses zero model calls.
It does not measure compaction, model-generated queries, answer accuracy, or
tokens. The excluded history only tests AtMem's authorization boundary, since
the GrepMem arm received a prefiltered fixture.

To reproduce, extract the pinned GrepMem source into a temporary directory and
use a Python environment with both evaluation clients installed. Follow
GrepMem's CPU client and pinned rLLM setup, then install AtMem into the same
environment. Run from the AtMem repository root, with `GREPMEM_SOURCE` set to
the extracted directory.

```sh
PYTHONPATH="$GREPMEM_SOURCE:$PWD" python -m tools.benchmark_grepmem_lookup \
  specs/055-exact-history-recall/evidence/holdout-packing-fix-512.json \
  --output /tmp/atmem-grepmem-lookup.json
```

[Machine-readable GrepMem results](evidence/holdout-upstream-grepmem-512.json)

## Temporal answer selection

On the four development routing-code questions, the on-device Apple Foundation
Models reader chose the current code in both presentations on every question.
Native V3 delivered both source spans in every case, with the 09:00 update
first. Each span already gives the time alongside its value. Sorting the
delivered spans by that time changed only their order. Each pair used exactly
139 UTF-8 evidence bytes per presentation under the same 512-byte ceiling.

| Presentation | Current answers | Stale answers on retrieval passes | Other answers |
| --- | ---: | ---: | ---: |
| Native order | 4/4 | 0/4 | 0/4 |
| Newest first | 4/4 | 0/4 | 0/4 |

Each presentation used a fresh session, the same question and instruction,
greedy decoding, and a 48-token response limit. The grader compared the
trimmed reply to the exact current and stale codes. Replies containing both
codes count as other. The control already reached 4/4 on this fixture, leaving
no room to measure an accuracy gain. The pilot stopped after eight model calls.
[Paired contexts, replies, and scores](evidence/development-temporal-presentation-512.json)

To reproduce with the encrypted-storage environment above and an available
Apple Intelligence system model on macOS 26, run from the repository root.
The reader takes one prompt on standard input and writes one answer on standard
output. The system model can vary with the installed OS and model assets.

```sh
pilot_dir=$(mktemp -d)
swiftc tools/temporal_foundation_reader.swift -o "$pilot_dir/reader"
python -m tools.benchmark_temporal_presentation --split development --output-bytes 512 \
  --reader "$pilot_dir/reader" \
  --model "Apple SystemLanguageModel.default, greedy, max 48 response tokens, macOS $(sw_vers -productVersion) ($(sw_vers -buildVersion))" \
  --output "$pilot_dir/results.json"
```

## Follow-on benchmark

Use a pinned revision of [GrepMem's ContextBench generator and grader](https://github.com/limenlp/GrepMem)
with answer-blind query formulation, actual host compaction, and a fixed model.
Use KV Store and Log Triage first. Include realistic paraphrase, correction and
scope controls. Compare the current native route, summary plus bounded grep,
and an opt-in AtMem exact-history route if baseline results justify it. Match
the input stream, model settings and total tool and token ceilings. Record
exact-answer accuracy, stale-answer rate, context bytes, total tokens, search
calls and per-case time. Use a small development subset to qualify the harness
before opening a disjoint held-out set. Evaluate token savings at matched
accuracy as well as new recovered answers. This pilot alone does not measure
live compaction, model accuracy, or production performance.
