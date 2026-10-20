# Discovery-routing benchmark results — 2026-10-20

Eighteen completed coding attempts: twelve on one historical Click issue in two
separate conditions, and six on one SWE-bench Verified qualification task.
**The current integration does not demonstrate a reliable AtMem benefit.**
These are diagnostic results, not completion of the five-task Click matrix or
the 500-task Verified campaign. No package release, `main` change or Laya work.

## What was compared

Within each host, all three arms received the same two MCP tools: bounded
`repository_discover` and offline original-source read/search/edit/test commands.
Only the discovery backend changed. `native` is an AST-backed lexical locator,
**not an untouched stock-native CLI**. Cognee used its actual CODE extraction
and query SDK, source revision `f154b32a9e544dac73e7ddf2010327cf9988edcd`,
with no embeddings or LLM graph extraction. Relevant installed upstream module
bytes were checked against that source checkout. This is not a comparison of
every Cognee configuration or its full product capabilities.

Agents ran locally on macOS using native subscription sign-in: Claude Code
2.1.281 / Opus 5.5, medium effort, and Codex 0.163.0 / GPT-6 Luna, low effort.
No OAuth files were copied or tokens extracted. Copilot 1.0.98's actual account
policy rejected third-party MCP servers and access; no scored Copilot cells
were dispatched and no policy bypass was attempted.

AtMem used the installed source-preview wheel
`77a67773e33adcfe2c8a60d5a1da29326f0bc2dfe27663fc5f14297d0e272d92`.
Metadata remains 2.3.8, not a newly published release. Experience, automatic
recall/source injection and learned pruning were off. Each scored cell had one
attempt, a 240-second wall cap and a 30-call MCP cap. Failed attempts were kept.
There was no declared 500,000-token cap for this study; large cached-token totals
are reported rather than discarded or silently converted to uncached totals.

## Click: optional lookup

Task `b67832c`, parent `8c1a0a7abbc1c36f70d1f65f3604acc46c5ce6ab`.
All six attempts made **zero discovery calls**. Claude passed all three arms;
Codex passed native/Cognee and failed the AtMem-configured attempt. The failure
cannot be attributed to AtMem evidence because none was delivered. Do not claim
that Cognee's lower tokens here resulted from retrieval either.

[Full six-row table](discovery-044-click-optional-20261020/table.md) ·
[Machine-readable results](discovery-044-click-optional-20261020/results.json)

## Click: separately requested consultation

After observing non-use, a separate engineering condition asked every arm to
begin with a self-selected discovery query. The prompt change was recorded
before dispatch. No command was blocked until a lookup succeeded. Do not pool
this post-hoc condition with optional usage or claim spontaneous adoption.

Claude passed all three arms and received nonempty locations in all three.
Its total inputs / agent times were native **82,935 / 61.55 s**, Cognee
**57,230 / 39.50 s**, AtMem **98,706 / 87.27 s**. This one task does not show
an AtMem advantage over either comparator.

Codex passed the Cognee- and AtMem-configured attempts and failed native, but
none received nonempty locations: native/Cognee issued malformed requests,
while AtMem returned an empty response under the model-selected byte budget.
Its lower AtMem-configured token count is therefore not proof of a memory gain.

[Full six-row table](discovery-044-click-requested-20261020/table.md) ·
[Machine-readable results](discovery-044-click-requested-20261020/results.json)

## SWE-bench Verified qualification

Pinned official dataset: `SWE-bench/SWE-bench_Verified`, revision
`78f471bf655a3137b2e8a75af1501690ec009ec3`, 500 test identities / 4,500 planned
host/backend cells. The generated partition is a candidate exposure accounting,
not an independently audited untouched-test claim. This run used only the
predeclared qualification task `psf__requests-6028` and requested consultation.

The Windows WSL host had 12 CPUs, about 31 GB available RAM and 769 GB free
Linux disk. Official x86_64 task containers ran offline with 4 CPUs / 6 GB limits.
Fresh grader controls produced `RESOLVED_NO` on the base and `RESOLVED_FULL`
with the reference patch; grading took approximately 1.8–2.3 seconds per run.
Solvers received no reference patch, hidden test script or future Git history.
All six solver attempts terminated before their patches were graded.

Claude passed all three configurations; Codex failed all three. Native/Cognee
delivered locations to Claude, but AtMem did not. All Codex discovery requests
were rejected before backend lookup. Codex also changed forbidden test files in
two arms; the official grader independently reported unresolved in all three.

[Full six-row table](discovery-044-verified-qualification-20261020/table.md) ·
[Machine-readable results](discovery-044-verified-qualification-20261020/results.json)

Input totals include cache without double-counting: Anthropic input + cache
creation + cache read; Codex's reported input already includes cached input.
All 18 completed diagnostic attempts have terminal usage receipts. Agent time
excludes preparation and grading; setup includes graph indexing, so do not add
index time to setup again. Native transient AST preparation is included in
setup/agent timing, not separately counted as persistent graph construction.
There is one observation per task/host/backend/condition: no significance,
confidence interval, broad superiority or production-savings claim is made.
Ordering/cache and sampling variation remain confounders. Shell commands are
retained exactly; unobserved read ranges or duplicate-read savings are not inferred.

## Concrete issues exposed

1. Tool availability alone did not replace exploration on the optional Click
   task. An explicit instruction increased attempted consultation, not necessarily
   useful evidence delivery or task quality.
2. The model-facing request exposes bookkeeping and a byte budget. Examples
   include a budget of `3`, rejected correctly, and `1000`, accepted but yielding
   no locations. The next adapter should bind IDs/budgets on the host and give
   safe, field-specific validation feedback. Do not relax authority validation.
3. AtMem's source policy excluded `requests/sessions.py` during indexing; the
   common `Session` canary was therefore unsuitable. An admitted-file API canary
   passed without changing the secret policy. This coverage cost is real and
   must be inspected alongside indexing time, not hidden behind a speed claim.

## Setup failures and evidence coverage

All failed setup roots are retained, not used as replacement scored wins:

- First Click preflight: the launcher's denied TMPDIR accidentally covered its
  scratch directory. Zero model dispatches; corrected launcher/child separation.
- Native-host preflight: preserving USER/LOGNAME fixed Claude native keychain
  discovery; explicit MCP command approval fixed Codex. Copilot policy remained
  blocked. No credential copying or permission-policy bypass.
- First SWE solver preparation: excluded-file canary failure, zero solver starts;
  all owned containers removed.
- Next SWE set: an adapter initialization-reply bug. Two CLI attempts were
  captured; a third launch was interrupted before its output buffer returned.
  That interrupted stream is missing and is **not fully reconstructable**.
  This is harness-failure evidence, not valid model-quality comparison. A new
  regression test and real initialize/list/ping probes preceded the corrected
  six-cell set. No score-guided retry or hidden grader feedback was used.

Original signed/encrypted Click exports and readable redacted derivatives are
published in [the AtMem evidence dataset](https://huggingface.co/datasets/atmem/code-discovery-benchmark-evidence-20261020/tree/9baad0c281cd2eb7a4cbfb1488a45099ce6d80f1), with 23 run exports independently
recovered while original-vault access was disabled. Twenty private SWE run
exports, including evaluator material and setup failures, passed the same
independent recovery gate under `owner-only-swe` on MEM. Recovery keys stay on
the Mac, outside both export directories. Public SWE publication is metrics-only;
the dataset card did not declare a data license, so raw evaluator redistribution
is not assumed authorized. Publication revision:
`9baad0c281cd2eb7a4cbfb1488a45099ce6d80f1`; all 34 uploaded files were downloaded
at that immutable revision and matched local hashes. Private keys and macOS
sidecars were excluded. The first YAML validation rejected a relative license
link; it was corrected and validated before any public publication.

Final source regression subset: **147 passed in 59.47s**; it includes three
installed-host loopback checks, prior Code compatibility/portability tests and
new comparator/receipt/handshake/publication regression cases. These test counts
are separate from the 18 real coding attempts. Dashboard JavaScript syntax,
diff whitespace and the 56-page website-doc inventory checks passed; no website
was deployed. Product code is byte-identical to the earlier verified wheel.
The public files/card and interactive dataset viewer are available. Both
`trials` and `traces` test splits finished building with no pending/failed jobs;
the live trials endpoint returned all 18 rows as its total.

## Remaining scope and money

The full 45-cell Click matrix and 4,500-cell Verified campaign were **not run**.
Copilot's account policy blocks its cells; complete subscription capacity and
held-out/exposure gates have not been established. The lookup-adoption and
request-shaping failures make a full-scale benefit claim premature. No paid API
fallback or cloud rental was used: **USD 0 of the USD 6 rental cap**. Temporary
campaign-owned Docker containers were removed; retained evidence preserves their
captured source, patches, tool activity and grading outcomes. No owner repository
or unrelated Windows workspace was deleted.

Code and small evidence belong on `feature/atmem-code-2.3.9`; no release tag,
PyPI/npm publication, website deployment or `main` update is part of this run.
