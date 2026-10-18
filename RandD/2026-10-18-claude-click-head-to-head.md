# Claude on Click: AtMem, upstream Cognee and no memory

2026-10-18. Completed bounded comparison, not an optimization loop.

## Outcome

All three final patches solved the same Click task and passed the identical
frozen suite. AtMem was faster than Cognee in this observation and used slightly
less input. Neither graph saved input tokens compared with native source access.
One reused task and one final attempt per arm cannot establish general superiority
or a statistically reliable speed difference.

### Final runtime-qualified comparison

| Metric | No memory | Cognee structure | AtMem structure |
|---|---:|---:|---:|
| Task solved | Yes | Yes | Yes |
| Frozen tests passed | 1,868 | 1,868 | 1,868 |
| Frozen tests failed | 0 | 0 | 0 |
| Solver wall time | 61.905 s | 69.232 s | 58.248 s |
| Index build | 0 | 7.923 s | 1.807 s |
| Complete preparation | 0.719 s | 11.130 s | 3.756 s |
| Preparation + solve | 62.624 s | 80.362 s | 62.004 s |
| Total input tokens, including cache | 47,199 | 81,639 | 78,278 |
| Uncached input tokens | 18 | 22 | 22 |
| Cache-creation input tokens | 7,156 | 10,721 | 8,254 |
| Cache-read input tokens | 40,025 | 70,896 | 70,002 |
| Output tokens | 3,508 | 4,717 | 4,442 |
| Reported thinking tokens | 744 | 1,176 | 604 |
| Total tool calls | 8 | 10 | 10 |
| Actual graph calls | 0 | 1 | 1 |
| Observed graph-call wall time | N/A | 2.505 s | 0.938 s |
| Graph errors | 0 | 0 | 0 |
| Command timeouts | 0 | 0 | 0 |
| Patch scope violations | 0 | 0 | 0 |
| Complete usage receipt / within caps | Yes | Yes | Yes |

Preparation includes indexing and integration qualification: do not add index
time a second time. Dependencies and extraction images were already installed;
this is not a first-ever installation or cold-machine timing. Thinking tokens
are reported separately, not added to output again. Input includes cache creation
and reads once, from the terminal aggregate receipt. These are token volumes,
not equal-price billing units; subscription list-price estimates are not charges.

Observed AtMem differences:

- Versus Cognee: **4.1% less input**, **15.9% shorter solver time**.
- Versus no memory: **65.8% more input**, **5.9% shorter solver time**.
- Including preparation, AtMem and no memory were effectively similar here:
  62.004 versus 62.624 seconds. That subsecond difference is not evidence of a
  repeatable improvement.

The graph call itself was not slow in the final AtMem run. Both providers
returned a successful symbol query and Claude then used normal source and tests.
This task did not exercise deep traversal, change-impact analysis or accumulated
experience. The measured tool/schema overhead and extra turns did not buy an
accuracy improvement over the successful native baseline.

## What ran

- Actual Claude Code **2.1.281**, resolved **claude-opus-5-5**, medium effort,
  existing Claude subscription. No paid API key or GPU instance used.
- Same historical Click issue **b67832c**, parent
  `8c1a0a7abbc1c36f70d1f65f3604acc46c5ce6ab`: automatic help must not collide
  with user parameter names, including custom help flags and explicit help options.
- Same source tree and grader digests from the existing frozen replay package.
  A sanitized one-commit Git repository per attempt; no target patch or future
  tests supplied to Claude. All three models terminate before evaluator grading.
- AtMem installed private indexing-depth preview wheel, metadata 2.3.8,
  sha256 `280c3c169cfa23f42f9233fe737eb182b628242aafd2b347a4e3c561b88aa351`.
  This is **not** a claim about public stable 2.3.8 or a published release.
- Actual upstream Cognee SDK at
  `f154b32a9e544dac73e7ddf2010327cf9988edcd`, not AtMem's vendored query code.
  Post-run audit matched all **2,663 Python files** in its installed package to
  the clean pinned checkout. Minimal benchmark MCP transport forwards official
  CODE queries; this is not qualification of the complete official MCP server.
- Separate Cognee indexing input equals the permitted parent tree. Its generated
  `.enola` files never enter the candidate patch. Both arms use pre-change graphs;
  current source takes precedence. AtMem's normal stale-state checks remain.
- Structure only, no conversational experience, no answer pack. Graph arms have
  the same navigation notice, including a parent-source symbol-query example,
  and must successfully consult a graph before workspace commands. This measures
  **explicit consultation**, not automatic adoption or a normal host-hook journey.
- Claude has only declared MCP tools. All arms share the same offline command
  tool; AtMem additionally exposes its four installed structure tools and Cognee
  its typed code-search tool. Actual CLI init inventories and tool responses were
  retained, not merely assumed from configuration.
- Per attempt: 240 seconds, 30 tool calls, 500,000 audited input+output tokens.
  All final attempts finished normally and stayed within all caps.
- Same grader exclusions: 25 skipped and 31,001 deselected in each arm (31,000
  upstream stress cases plus one literal-/tmp environment-dependent case).
  Solver-added tests cannot alter the frozen evaluator suite.

## All attempts and corrections—not best-of selection

There were **nine target attempts total**, three per separately frozen protocol,
plus one unscored tools-off AUTH_OK check. No individual failing arm was retried
while retaining another arm's best result. No AtMem product code, grader, task or
model was tuned between these runs. The final protocol was designated last before
dispatch, regardless of outcome. Earlier measurements remain in the archive.

| Protocol | Arm | Frozen passed / failed | Solver time | Total input | Graph calls |
|---|---|---:|---:|---:|---:|
| 1: optional consultation | No memory | 1,868 / 0 | 62.779 s | 31,451 | 0 |
| 1: optional consultation | Cognee | 1,868 / 0 | 57.414 s | 48,366 | 0 |
| 1: optional consultation | AtMem | 1,867 / 1 | 61.800 s | 77,870 | 0 |
| 2: explicit consultation, runner faults | No memory | 1,868 / 0 | 56.017 s | 47,512 | 0 |
| 2: explicit consultation, runner faults | Cognee | 1,868 / 0 | 71.368 s | 60,450 | 1 |
| 2: explicit consultation, runner faults | AtMem | 1,868 / 0 | 105.187 s | 105,415 | 1 |

Protocol 1 exposed tools but neither provider was used. It cannot measure the
graph mechanism. Sandbox-launcher `.codex` files also produced raw patch-policy
flags in all arms; those flags are preserved, not silently deleted from results.

Protocol 2 required consultation and passed every frozen test, but trace review
found that the runner denied workspace scratch writes, replaced PATH with the
Apple Git shim, and inherited MCP stdin. An AtMem-arm `cat > /dev/null` waited
35 seconds. Its wall/token results include those interruptions; no subtraction
or adjusted synthetic score is reported.

The final host-only correction closes stdin, exports exact runtime paths inside
the sandbox, and keeps the launcher TMPDIR distinct from permitted scratch space.
Every final arm passed real scratch-write/read, stdin-EOF, native-Git, own-source
Click import, source-read and evaluator/Git-history/network-denial controls
before dispatch. No command timed out and no denied scratch write was observed
in the final traces. The harness tests pass **13 tests**.

There were also two zero-target-dispatch preflight corrections (key-home mismatch
and a missing launcher-state directory). Their failures are retained. The
requested zero-thinking environment setting was not obeyed by target runs:
actual reported thinking is above, so these are not called thinking-disabled.

## Evidence and scope

Final run: `click-claude-three-arm-20261018-v3-clean`.
Internal protected evidence and results:
`/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/click-20261017/claude-three-arm-clean-20261018`.

Recipient-encrypted MEM archive, including prior comparisons, raw CLI streams,
tool requests/responses, patches, grader output, protocols, installed wheel and
harness sources:
`/Volumes/MEM/AtMem-Code-Replay-20261017/protected-claude-three-arm-clean-20261018/click-claude-three-arm-20261018-v3-clean.encrypted.json`.

Archive sha256:
`2e2671a2fe9ed903b562d1fdc6bc5d2618b28eb6b2319df733f8731e57e3965e`.
Archive round-trip verified; private recovery/signing keys remain internal, not
on MEM. No owner installation, public package, release or remote branch changed.

This is a single reused task, fixed arm order, no repeated clean trials and no
confidence interval. It establishes working Claude/graph integration and equal
final correctness on this task. It does **not** establish token savings over no
memory, general Cognee parity, automatic adoption, or multi-task user benefit.
