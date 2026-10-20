# Structural efficiency improvement loop

Active work under the owner's 50%-saving target, with 20% fallback and no
functional task-pass loss. Scope: AtMem Code structural context only; no Laya,
training, experience, main-branch mutation or release.

Protocol: `specs/043-click-historical-replay/structure-improvement-loop.md`.
At most three candidate cohorts and one new-task confirmation cohort, ten
matched native/structural attempts each, subscription Luna only. Every attempt
is retained, including failures. No best-of-task aggregation or discarded runs.

## Tuning record

| Candidate | Native input tokens | Structural input tokens | Reduction | Native functional/policy passes | Structure functional/policy passes | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1: source-backed packing | 1,207,522 | 697,390 | 42.25% | 4/5 | 3/5 | Reject: quality/policy gate failed |
| 2: local-name weighting | 893,407 | 826,964 | 7.44% | 3/5 | 4/5 | Reject: below token target and five-task quality floor |

Candidate 1 supplied current source snippets, readable locations, deduplication,
byte limits, verified hashes and explicit omissions. It reduced tool calls from
56 to 35, but did not pass the quality gate. Its pager context was dominated by
six wrapper methods because the fully qualified owner-class vocabulary counted
as each method's name. The pager patch repeated the exceptional-cleanup error.
The editor patch passed the grader but generated symlinks in an extra `.tmp`
tree, violating the frozen patch policy. That attempt remains failed; it is not
silently reclassified as a pass. Native task 1 also failed three assertions and
exceeded the token audit ceiling.

Candidate 2 lowers inherited owner-name weight, prioritizes local symbol names,
does not let an outline hide child implementations, and removes non-actionable
`declares`/`contains` edges from the pack. Both arms receive the same explicit
reminder to respect the existing configured scratch directory; this prompt
revision is frozen and is a cohort difference, not claimed as an isolated
product-only effect. Its tuning acceptance requires 5/5 structural functional/
policy passes, not just matching a weaker stochastic native run.

Candidate 2's source packs still missed compact compound identifiers and used
too much space for navigation instead of the implementation. Candidate 3 matches
multiple query words inside compact identifiers, limits packs to four ranked
fragments and adds bounded static finally-block call-site annotations for
generators/context managers. These annotations identify source locations, not
observed execution, correctness or a proposed patch. Non-AST anchors are labelled
as anchors, not complete definitions. No task-ID conditions or target patches
are used by the product.

## Separate transfer tasks

Five earlier Click changes were qualified before any confirmation solver run:
`fc6c7c4`, `c943271`, `fe3ad76`, `8a4ce84`, `8c1a0a7`. Each parent fails the
frozen default suite and each accepted reference passes it twice. The package
digest is `d5014252bf04109e306465ed4c1424e69220dd5f8ad572365be5420ede943431`.
They are selected new tasks, not a random sample, unseen public code, or a
repository-disjoint benchmark. A proposed `0039359` task was excluded because
its upstream grader passed the parent; this qualification failure is retained.
No confirmation agent result may be used to tune another candidate.

## Evidence and measurement

Candidate 1 manifest: `/Volumes/MEM/AtMem-Code-Replay-20261017/efficiency-c1-frozen.json`;
protocol digest `05352ce79c9c519bb174f15a110b256dc935ab7d12d737c48edda8931bc8d81d`.
Eleven exact-event archives round-trip at `protected-efficiency-c1` on the same
MEM benchmark directory. A fresh process recovers all ten terminal trials
using archives and internal private keys, without the vault. Candidate-1 RAM
homes/workspaces were then removed; other active sessions were preserved.

Input tokens include cached input. Output tokens, uncached input and measured
latency are reported separately; no billing saving is inferred from token
counts. Subscription billing/quota are unknown. Functional pass includes the
frozen applicable default suite and patch policy; all-budget passes are separate.
The inherited upstream stress deselection and one literal-/tmp exclusion stay
unchanged. No tests are removed after observing solver failures.

## Completed first loop: no accepted candidate

Forty real solver sessions completed: three tuning cohorts and one separate
new-task cohort, each with five fresh native/structural pairs. No solver retries,
replaced failures, API/GPU spending, target-specific product rules or training.
The 50% target and 20% fallback have **not** been established. No candidate
passes the declared full acceptance gate.

| Cohort | Native task passes | Structural task passes | Input-token saving | Native median measured path | Structural median measured path |
| --- | ---: | ---: | ---: | ---: | ---: |
| c1 | 4/5 | 3/5 | 42.25% | 26.80s | 26.67s |
| c2 | 3/5 | 4/5 | 7.44% | 24.93s | 26.40s |
| c3 | 4/5 | 4/5 | 32.28% | 27.23s | 22.36s |
| confirm | 2/5 | 3/5 | -3.61% | 26.77s | 28.68s |

Functional task passes include the frozen default tests and patch policy.
They are not all-budget passes. The tuning floor additionally requires 5/5;
Candidate 3 matches its contemporaneous native count but fails that stronger
floor. Do not replace its actual 4/5 with successful task patches from C1/C2.
Tuning and transfer rows are separate; no pooled superiority claim.

### Final candidate details

| Task | Cohort | Native | Structure | Native input | Structure input |
| --- | --- | --- | --- | ---: | ---: |
| b67832c | c3 | pass | checks_failed | 496567 | 326908 |
| 9c4dfda | c3 | pass | pass | 207191 | 124993 |
| 150d107 | c3 | checks_failed | pass | 206366 | 179398 |
| fc5c7f4 | c3 | pass | pass | 145087 | 131213 |
| e1fd594 | c3 | pass | pass | 206100 | 91653 |
| fc6c7c4 | confirm | pass | pass | 274831 | 226689 |
| c943271 | confirm | checks_failed | checks_failed | 154028 | 210796 |
| fe3ad76 | confirm | checks_failed | pass | 366097 | 436211 |
| 8a4ce84 | confirm | checks_failed | checks_failed | 141502 | 139862 |
| 8c1a0a7 | confirm | pass | pass | 174185 | 137219 |

### What the transfer trace reveals

The `c943271` pack contained four Markdown headings instead of the `prompt`
implementation. The `8a4ce84` pack contained a heading, an example import,
an unrelated example validation function and another heading instead of `style`.
A current rich index and a nonempty context pack therefore did **not** establish
that useful implementation evidence was delivered. This is a product ranking/
coverage defect, not evidence of general token savings. Candidate-3's original
help-collision attempt also failed one graded test while the native attempt
passed; the native progress attempt failed while structure passed. Equal counts
do not mean no per-task regressions.

The first loop cannot be rescued by changing grades after seeing this result.
Preserve these targets/results. A subsequent protocol must first require a
positive implementation-localization diagnostic (not just a rich snapshot ID),
prefer executable symbol bodies over heading/import matches, resolve explicit
code identifiers, and choose a genuinely new transfer set. The first failed
transfer remains a failure; these five tasks cannot be relabelled untouched in
a later loop.

### Evidence and final verification

All 45 recipient-encrypted bundles (44 cohort bundles plus the separate
qualification history) round-trip exact events. After ejecting the task-owned
RAM volume, a fresh process recovered **142 events and all 40 terminal trials**
from archives and internal keys alone, without opening the vault or solver files.
The extraction VM was stopped; MEM remains mounted. Temporary solver homes and
workspaces were disposed of; retained prompts, contexts, patches, tool records
and grades are recoverable. Private keys were never placed on MEM.

Frozen packages and protected exports are in
`/Volumes/MEM/AtMem-Code-Replay-20261017/`, using `efficiency-{c1,c2,c3,confirm}-frozen.json`
and `protected-efficiency-{c1,c2,c3,confirm}`. The confirmation package digest is
`5fc93c1ae41beb23ddba045c13a6f239218648aacea824a579ca82ebeebfb395`.
Original package and source artifacts remain immutable; no published 2.3.8
artifact, main branch, owner installation or release was changed.

131 targeted regression/spec checks pass, installed preview tests pass and six
changed modules parse under Python 3.10 grammar (not a runtime/platform claim).
CI definitions include the new no-inference checks; no remote CI or broader
host/platform qualification is claimed. Complete CLI/system/model capture and
production-level savings remain unclaimed.

## Follow-up in progress: implementation localization

After freezing and reporting the failed transfer, the working source received
a bounded follow-up: executable declarations rank ahead of headings/import
anchors, and named callable identifiers receive direct localization priority.
A regression recreating heading crowding now passes; eleven focused checks pass.
This follow-up is **not** the C3 wheel measured above and has no solver result
yet. It must be built/qualified separately before another cohort. Namespace
disambiguation, a disjoint positive implementation-localization diagnostic and
a newly frozen task set remain next gates. First-loop transfer results stay
unchanged; they cannot serve as untouched confirmation for this follow-up.
The tracked goal remains active because neither required token target has been
confirmed. Do not mark the model/structure improvement accepted or release-ready.

## Second loop completed: localization alone did not meet quality

Ten new paired attempts, Luna low, same five familiar tasks and limits, no
experience or retries. Native: 4/5 functional/policy passes and 1,405,326 input
tokens. Structure: 3/5 and 1,118,093 input tokens (20.44% reduction). All-cap
passes were 3/5 each; measured setup/index/context/solver median was 31.258s
native versus 33.270s structure. All ten input-token records were known; no
infrastructure-invalid trials. The strict quality gate failed, so no transfer
solver calls were dispatched. This result cannot establish user savings.

Inspection found the help pack omitted the actual decorator implementation and
the progress pack omitted finish/update bodies. Both are retrieval assembly
defects even though named-source localization passed its earlier diagnostic.

## Third loop completed: call-path assembly still loses quality

Protocol: Spec 043 `call-path-loop-v3.md`. Frozen manifest SHA-256:
`567ffe9b1df07462f8724d2e6d653ec883e21a1650f8a6bffb66bdcef7ed8527`.
Installed local preview wheel SHA-256:
`eb05005cab32bbacf7b125a706ab5d797f26692c2446a49f8b0adb6c3809787e`.
No published package or stable 2.3.8 behavior claim.

Pre-dispatch inspection now finds the help decorator and progress finish/update
implementations. Actual disjoint CPython logging extraction qualified three
named queries plus the error-to-_log callee, and changed source both withheld
context and rejected stale submission (zero model calls). These are boundary
checks, not task-success or token-saving evidence. The artifact remained
unchanged during all ten new familiar-task attempts.

| Metric | Fresh native | Structure |
|---|---:|---:|
| Functional/policy passes | 5/5 | 3/5 |
| All-cap passes | 5/5 | 3/5 |
| Total input tokens | 1,120,266 | 957,228 |
| Output tokens | 10,037 | 6,536 |
| Cached input tokens | 1,030,016 | 834,688 |
| Median solver seconds | 24.792 | 26.644 |
| Median measured setup/index/context/solver seconds | 26.120 | 34.118 |
| Tool calls | 54 | 52 |

Input saving 14.55%; quality gate fails and neither token threshold passes.
All ten usage records known, no infrastructure-invalid trials. No confirmation
solver runs dispatched for this failed candidate. Eleven exact-event encrypted
bundles round-trip verified under `protected-efficiency-p3c1` on MEM; private
keys remain internal. All prior negative results remain separate.

Failures: help collision left one existing help-hint regression; progress left
three explicit-update final-position regressions. Supplying the missing
implementations did not ensure the solver used their full behavioral contract.
The help solver explicitly acknowledged an unresolved local regression; the
progress solver passed its own narrower tests but missed hidden transition cases.
Do not infer that the context alone caused these failures from single trials.

Next experiment should change the information contract rather than repeat
small ranking tweaks: source-bound current tests/call examples and progressive
detail are candidates. Any such change requires its own qualification/freeze;
no result is claimed yet. Research notes distinguish papers' mechanisms from
our measured evidence.

New transfer eligibility (no solver scores): original selection excluded
`7c99ebe` because no pre-solution report could be recovered. Retained under
`efficiency-p3confirm-qualification`. Replacement set `c8da1fc`, `b03f211`,
`0cd28d6`, `b7cf069`, `3bb230d` passed parent-fail/reference-pass-twice gates,
retained under `efficiency-p3confirm-qualification-v2`; package SHA-256
`986b717f6930dd2654ebc14cfedf83778fa6ef233ca1b87e7b05188059b7fdb5`.
It remains unscored and is not a claimed successful confirmation set.

After fresh-process recovery of P2 archives, its ten disposable RAM session
directories were removed. Encrypted retained observations remain recoverable;
no owner project memory or installed configuration was touched.

## Fourth loop completed: quality recovered, efficiency not established

Investigation found zero test objects in the extracted graph despite 42–44
test source files in the authorized snapshots. Two source files were withheld
by the existing secret screen, including the terminal tests needed by the
progress case. P4 does not bypass that screen: it considers only retained,
hash-validated test/example source, excludes typing-only examples, and prefers
demonstrated calls to the localized API over generic keyword overlap.

One usage excerpt receives at most a quarter of the byte ceiling, capped at
2048 bytes. It is labeled unexecuted source, not a new graph fact or expected
decision. Existing tests cover the help/pager contexts; eligible repository
examples cover progress/edit. Pre-dispatch inspection preserves the help
decorator and progress finish/update bodies. Preliminary preflight builds that
selected unrelated/typing-only examples were corrected before solver dispatch;
they are not extra scored candidates or retries.

Actual disjoint qualification includes CPython v3.12.12 logging plus public
`Lib/test/test_logging.py`, pinned Git blob
`5112c2e7d60f0baadabe21686fa5392d32391c3b`, under the retained PSF license.
Three source/usage queries, the _log callee and stale-source controls pass with
zero model calls. Thirty-seven focused checks pass; no broader parity claim.

Installed preview SHA-256:
`f769e0b2e572cd4c6623c682fb832e0beeef46b75bfacbffb88b690a72aaf6d5`.
Frozen manifest SHA-256:
`2d890dda3b1f396d31858dfd09525c3b652c9a1b6ce4b8aae3170afede611adc`.
Protocol: Spec 043 `source-usage-loop-v4.md`. All ten new matched attempts
completed without retries or changes to the frozen candidate.

| Metric | Fresh native | Structure + source usage |
|---|---:|---:|
| Functional/policy passes | 5/5 | 5/5 |
| All-cap passes | 5/5 | 4/5 |
| Total input tokens | 931,316 | unknown |
| Known input subtotal | 931,316 (5/5 receipts) | 651,263 (4/5 receipts) |
| Output tokens | 6,448 | unknown; 5,234 known subtotal |
| Median solver seconds | 25.231 | 23.672 |
| Median measured setup/index/context/solver seconds | 26.584 | 30.615 |
| Tool calls | 45 | 58 |

The first structure help case exceeded the unchanged 24-tool limit (25th
call started), so the harness killed that turn before its usage receipt. Its
patch passed grading; all-cap result remains failed and missing tokens remain
unknown. No zero imputation or excluded-row savings calculation is permitted.
Quality passes, token acceptance does not. No transfer solver calls dispatched.
Eleven cohort/protocol archives plus the localization archive were exact-event
round-trip verified; fresh-process recovery reproduces quality=true, saving=null,
fallback_20=false. Private keys internal; no release/user-savings claim.

Prior complete traces show repeated source exploration remains substantial even
with supplied excerpts. Progressive, scoped queries are the next architectural
experiment—not another claim that a smaller initial pack alone solves token use.

## Fifth loop: progressive read-only retrieval, frozen and running

Reuses AtMem's MCP stdio transport and existing authorized/current source and
incorporated traversal services. Only code_search, code_explore and code_source
are exposed. Root, subject, project, profile and agent are operator-bound;
unknown arguments, inherited mutation tools and unavailable source are refused.
Responses are compact and bounded; delivery rechecks source currentness. Edits
withhold the old index instead of silently refreshing or claiming current facts.

Actual installed CPython logging/public-test localization and independent MCP
stdio subprocesses pass current-source and stale-source controls. An actual Luna
host diagnostic then returned search/explore/source results and a scope refusal.
Semantic audit verifies exact returned implementation bytes/source SHA-256 and
the search-to-explore ID link on one unchanged snapshot. Its four observed MCP
calls used 140,114 input/517 output tokens (126,080 cached input); this diagnostic
is not a task comparison or savings evidence. The model's claimed native canary
attempt is not visible in retained CLI events and is not asserted verified;
the separate actual native sandbox read barrier passed. Complete hidden/model
input capture is unclaimed. Two encrypted diagnostic/qualification bundles
round-trip and fresh-process recover; host-prefreeze harness bytes are retained.

The [official MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
was checked alongside the pinned CLI. All configuration is disposable benchmark
configuration, not an owner installation. No API key/provider billing was used.
Thirty-three combined focused checks and 17 subsequent harness checks pass;
CI includes those checks but no remote CI/platform qualification is claimed.

P5 initial delivery is a small capability notice, separately receipted from the
unused full runtime pack (which stays prepared-only). Actual MCP source responses
are verified against the frozen pre-state and recorded separately from grade
accuracy. All C trials must expose eligible source evidence before acceptance;
a native-only outcome cannot establish structural savings. Every model-turn
usage receipt is required, including dynamic tool content. Unknowns stay unknown.

Artifact SHA-256:
`aecce2d4ea8a91ed073d261a512d17723cdeb53a26942d264952db18761ac9d9`.
Frozen manifest SHA-256:
`42d351aaedf492a9015a5b2c6560a876a569de25ad4d73f5216d9f55db2c3c93`.
Protocol: Spec 043 `progressive-retrieval-loop-v5.md`. The first invocation
stopped in native task 1: the harness attempted a group signal after waiting
for the parent, and macOS returned PermissionError. No terminal trial result or
structure attempt exists for that invocation. Its raw CLI stream was lost
because cleanup raised before the return; benchmark-local ephemeral state/log
tables were empty, so no replacement observation was recovered. Partial
workspace changes were retained without grading; sanitized source baseline was
verified against the frozen parent. Exact prefreeze harness/manifest and the
interruption are in two encrypted bundles under
`protected-efficiency-p5c1-interrupted`. Do not score or silently discard it.

Fix: skip the late group signal after the parent is reaped. A regression with
denied late signals and the existing descendant-pipe timeout check both pass.
The repaired launcher was requalified by a fresh actual host diagnostic
`progressive-host-p5r1`, with exact source-response/scope-refusal audit again
passing. Native model-claimed read remains unverified in partial CLI events;
the independent native sandbox barrier is the asserted control.

One infrastructure restart is registered before new dispatch, not a retry of
observed task scores: same candidate artifact/tasks/thresholds, fresh paired
controls, new manifest SHA-256
`7c4c557cbef7013b8b1973df7401417d3b67578083e17cb5920bcc3d9dec8c57`,
cohort `efficiency-p5c1r1-20261017`. It completed. No further automatic restart
is authorized by this protocol. The qualified transfer five remains unscored
and conditional on both gates; no accepted token-saving result exists yet.

### P5 replacement cohort results

| Metric | Fresh native | Progressive structure |
|---|---:|---:|
| Functional/policy passes | 4/5 | 4/5 |
| All-cap passes | 4/5 | 4/5 |
| Input tokens | 1,451,307 | unknown |
| Known input subtotal | 1,451,307 (5/5) | 997,246 (4/5) |
| Output tokens | 9,847 | unknown; 7,908 subtotal |
| Verified MCP implementation responses | not applicable | 3/5 trials |
| Median solver seconds | 29.058 | 42.119 |
| Median measured setup/index/context/solver seconds | 30.452 | 49.507 |
| Observed tool calls | 61 | 74 |

No infrastructure-invalid terminal trials in the replacement cohort. The first
structure help case exceeded the tool limit, has unknown usage and failed three
help-collision regressions. It made three symbol searches, requested 130 source
lines (the allowed maximum was 100), received a refusal, explored a neighborhood,
then made eighteen native command calls without a verified implementation-source
response. The progress case had no observed MCP calls at all; its lower tokens
cannot establish an AtMem benefit. Do not relax the source gate or retrospectively
accept the equal 4/5 outcome: the fixed 5/5 tuning floor also fails.

All eleven replacement-cohort/protocol encrypted bundles round-trip verified.
No transfer solver calls dispatched. The next interface hypothesis is a single
focused source-context request using the existing packer, actionable parameter
errors, and a bounded proactive source pack rather than a capability-only notice.
This is unmeasured, not an accepted optimization.

## P6 implementation and scoring completed: not accepted

The working source now adds `code_context` to the read-only MCP surface, backed
directly by existing CodeKnowledge.context/packer. The operator still binds
scope/root, output is bounded/hash-identified and stale-source delivery is
withheld. Known numeric-limit errors now identify the field/range without
echoing private source or caller-supplied values. Thirty-nine focused checks
pass, including exact product-pack equivalence and stale-source refusal.
This is not the previously measured three-tool P5 wheel.

Installed artifact SHA-256:
`648c1a8a9595cbcbf46cc6aa6e5680daa8012c9db4dba2001cc8a56acc1910ba`.
Actual disjoint CPython logging/public-test extraction and independent stdio
processes pass, including exact focused pack output, actionable numeric-bound
feedback and changed-source refusal. A new actual Luna host diagnostic exercised
all four tools; semantic audit verifies both exact file excerpts and focused
pack bytes on the unchanged source generation, with scope refusal intact.
The model-claimed native canary read remains unverified in partial CLI events;
the independent actual native-read barrier is the asserted control. Two encrypted
diagnostic archives round-trip verified under `protected-progressive-p6`.

All five familiar pre-state packs at 4096 bytes contain implementation evidence
and fit: 4073, 4041, 4095, 4071, 4082 bytes. Three independent processes produced
identical hashes on those five packs; this limited check is not a global
determinism guarantee or task-success result. Fifty focused checks pass.

P6 uses the actual product runtime's requested 4096-byte initial ceiling, not
a capability-only notice, with ordinary receipt validation before stdin delivery.
Both arms receive identical generic source-use/test guidance. On-demand tool
traffic is separately bounded and fully contributes to completed-turn tokens.
The first unexecuted draft manifest was superseded before any solver dispatch
to align the existing hard initial-context guard with the declared 4096 bytes;
that draft is retained in `preflight.freeze_superseded`, not silently overwritten.

Qualified manifest SHA-256:
`4cf2644050b2bc5f31e52305f92b960ef7653b030c8af8bea602ec246421abb4`,
`efficiency-p6c1-frozen-qualified.json`. All ten matched attempts completed under
Spec 043 `focused-context-loop-v6.md`. Native and structure each passed 4/5
functional/policy checks and 4/5 all-cap checks, below the fixed 5/5 tuning floor.
Native input is unknown (four receipts; known subtotal 912,987); structure input
is 1,368,286 (five receipts). No paired total token-saving percentage is valid.
Native/structure median solver seconds: 31.864/28.437; measured path seconds:
33.172/36.003. Observed tool calls: 71/62. The first native trial exceeded the
tool cap; the first structure trial exceeded the post-turn token cap and failed
three help-collision regressions. All five initial source submissions are
verified, but no on-demand MCP source response was observed. No grading
infrastructure-invalid trials; no transfer dispatched. Eleven encrypted bundles
were recovered in a fresh archive-only process; both acceptance gates are false.
P5 scratch sessions were removed only after archive-only
recovery of all ten retained terminal rows; encrypted evidence remains on MEM.

After archive-only fresh-process recovery, twenty P3/P4 disposable RAM session
directories were removed; encrypted retained results remain recoverable on MEM.
No owner project memory, normal agent configuration, main branch or release
was changed by this continuation.

## Missing usage receipt investigation

Read-only inspection of all 90 completed efficiency trials (c1/c2/c3/confirm,
P2/P3/P4/P5 replacement/P6) found 87 known receipts and three missing receipts:

| Trial | Harness stop | Exit | Tools | Retained stdout bytes |
|---|---|---:|---:|---:|
| P4 structure, task 1 | tool_budget | -9 | 25 | 56,160 |
| P5 replacement structure, task 1 | tool_budget | -9 | 25 | 81,645 |
| P6 native, task 1 | tool_budget | -9 | 25 | 91,292 |

Each retained stream has a started turn, no completed turn, no top-level usage
event and no invalid JSON lines. The harness enforces the 24-tool limit by
SIGKILL on observing tool 25; the CLI terminal usage event therefore never
arrives. This is not evidence of a provider omission or a lost parser receipt.
Unknown is not zero and known-row subtotals cannot establish paired savings.

Separately, the original P5 operational interruption lost its raw stream when
launcher cleanup raised after parent reaping. It is not one of the 90 completed
trials; the prior cleanup fix and retained ungraded partial workspace remain
documented above. No alternate terminal receipt was recovered.

`benchmarks/code_replay/usage_audit.py` adds a read-only, hash-bound diagnosis of
retained streams, distinguishing hard stops, malformed streams, completed turns
needing schema review and unresolved exits. It does not modify old metrics,
impute usage, relax limits, or require new model calls. Future protocol changes
must retain these diagnoses explicitly. Hard-stopped turns can still lack usage;
requesting a graceful final answer would change the stopping protocol and cannot
be silently substituted into these cohorts.

## P7 compact navigation and call-path priority: completed, not accepted

P6 initial-source and ranking inspection identified three generic mechanisms:
property-to-getter inferred identity, a 24-entry repeated-path class inventory,
and a fixed imported-helper priority above its own nominating caller. Independent
fixtures reproduce both reference conflation and helper-before-caller ordering;
the repaired packer removes inferred exact getter matches, uses eight task-ranked
navigation entries without repeated paths, and keeps import helpers below their
caller. No Click-specific symbol, grader hint or requirement change was added.

Fifty focused product/harness checks pass, with further overlapping harness
checks; these are not task-success evidence. Installed actual CPython extraction
localizes 3/3 targets and passes call-context, public-test-source, stale-context,
stale-submission and focused stdio/error controls. A real Luna host diagnostic
completed five MCP calls; semantic audit verifies source/pack bytes, scope refusal,
unchanged source and the independent native-read barrier. As before, the model's
claimed native canary attempt is not independently visible in the partial stream.

Wheel SHA-256: `2478493224a97c07ce153f11a992674f59bebf421500c9569882e01e24cf818a`.
Frozen manifest SHA-256:
`5d18142541eaa424a5b0730f62baed90fa77ece1f0875cfd62b770515fc0d723`.
`efficiency-p7c1-frozen.json`, under `compact-navigation-loop-v7.md`.
The same proactive 4096-byte source ceiling, focused four-tool interface, common
prompt, solver and budgets apply. Each new terminal trial includes a hash-bound
usage diagnosis; old rows/unknowns are unchanged. All ten fixed attempts completed.

| Measure | Native A | Structure C |
|---|---:|---:|
| Functional/policy passes | 4/5 | 4/5 |
| All-cap passes | 4/5 | 4/5 |
| Usage receipts | 4/5 | 5/5 |
| Total input tokens | unknown | 748,655 |
| Known input subtotal (not a paired comparison) | 537,809 | 748,655 |
| Total output tokens | unknown | 6,676 |
| Cached input tokens | unknown | 678,656 |
| Median solver seconds | 26.896 | 21.319 |
| Median measured setup/index/context/solver seconds | 28.237 | 29.329 |
| Observed tool calls | 54 | 38 |

No grading infrastructure-invalid trials. Native task 1 hit tool 25 and was
killed before terminal usage, confirmed by its new hash-bound diagnostic.
Structure task 1 completed with 204,535 input tokens and 10 tools, but its patch
hard-coded the collision name and failed the custom-help regression: 1 failed,
1,867 passed, 25 skipped, 31,001 deselected, 1 xfailed. This is an improvement
in that particular inspected failure trace, not a passed task or evidence of
generalized quality. All remaining pairs passed. All five C initial-source
submissions are verified. Neither fixed quality/token gate passes; no valid
total input-saving percentage, no transfer dispatched.

All eleven protocol/trial archives under `protected-efficiency-p7c1` round-trip
verified; a fresh archive-only process recovered ten unique terminal trials,
including nine recorded usage receipts and one explicit hard-stop diagnosis.
Two qualification archives separately recovered source/localization proofs.
No current solver process remains. Across the original 90 plus these ten scored
trials, four missing receipts all have the same verified hard-stop cause; the
separate interrupted original P5 attempt remains outside that denominator.

Qualification archive orchestration initially omitted the helper's required
wheel metadata and failed after creating keys but before writing any archive.
Those keys were retained and used for the two exact-event qualification exports,
not replaced. This did not restart inference or alter qualification evidence.

Next decision: investigate whether source-backed parameter/field references can
provide the missing state-flow context, rather than assuming more call-neighbor
source will solve semantic generalization. Do not insert a custom-help solution
hint, change the sealed grader, relax the 5/5 floor, drop the hard-stopped native
row or dispatch another stochastic retry of this unchanged candidate.

## P8 budgeted behavioral source: completed, not accepted

The remaining P7 custom-help check was audited against the retained pre-solution
report and frozen requirement to respect configured aliases; neither grader nor
prompt was altered. The field-flow hypothesis remains unimplemented. Direct
ranking inspection found a narrower real defect: the top existing usage test was
1,361 bytes versus a 1,024-byte allowance, so the packer supplied a lower-ranked
635-byte test instead. This is a source-selection defect, not evidence that the
model's remaining semantic error can be fixed by retrieval alone.

Unrelated fixtures reproduced shorter-noise substitution and empty excerpts at
small budgets. The fix fits the highest-ranked source with exact numbered
signature/assertion/relevant lines and explicit gap markers. UTF-8 source,
headers/newlines and every omission marker count against the original allowance.
Excerpts remain partial, not-executed source, not generated examples or measured
test outcomes. The familiar task's pack now contains its top-ranked existing
usage test within 4,085 total bytes; this observation is tuning only.

164 combined boundary/product/harness checks pass; 21 subsequent overlapping
harness checks also pass (not 185 unique tests). Installed actual CPython
extraction localizes 3/3 implementations and passes call-context, public-test,
focused stdio, safe numeric error and stale-source/submission controls. The new
real Luna diagnostic completed five MCP calls and passed exact returned source/
pack byte audit, scope refusal and the independent native-read barrier. The
model-claimed native canary attempt remains unverified in partial CLI events.
Two encrypted qualification archives recovered in a fresh archive-only process.

Wheel SHA-256: `d3e4ea872086d48111e24c45c24fba472a90df6fa027cfd8d9e1d225d4b36de5`.
Manifest SHA-256: `9fb791ef2e7223998beef669397ea8e10dcb2f8425a121a275fa7e195b5fd8a5`,
`efficiency-p8c1-frozen.json`, under `budgeted-usage-loop-v8.md`.
All ten matched attempts completed with unchanged task, solver, prompt,
source/total-token/tool/wall limits and acceptance floor.

| Measure | Native A | Structure C |
|---|---:|---:|
| Functional/policy passes | 3/5 | 3/5 |
| All-cap passes | 3/5 | 3/5 |
| Usage receipts | 5/5 | 4/5 |
| Total input tokens | 1,201,877 | unknown |
| Known input subtotal (not a paired saving) | 1,201,877 | 893,700 |
| Total output tokens | 9,549 | unknown (6,662 known) |
| Cached input tokens | 1,076,992 | unknown (830,336 known) |
| Median solver seconds | 25.215 | 32.213 |
| Median measured setup/index/context/solver seconds | 26.534 | 39.746 |
| Observed tool calls | 59 | 69 |

Native tasks 1 and 4 failed checks; structure task 1 hit the hard tool cap and
task 3 failed checks. No grading infrastructure-invalid trials. All five initial
C source submissions are verified. Full-cohort token saving is unknown; neither
fixed acceptance gate passes and no transfer was dispatched. Do not compare the
four known C rows to five native rows or pool native results across candidates.

All eleven protocol/trial archives round-trip verified under
`protected-efficiency-p8c1`; a fresh archive-only process recovered ten unique
terminal trials, nine usage receipts and one hard-stop diagnosis. No current
solver process remains. Alongside the prior 100 complete trials, five of 110
receipts are now missing, all with the verified hard-stop cause. The separately
interrupted original P5 attempt remains outside that denominator.

Post-run source-budget audit: task 3's P7 pack contained ProgressBar.finish;
P8's larger, higher-ranked usage example displaced that implementation while a
README heading remained. This is a deterministic packing interaction, not proof
that it caused the stochastic solver failure. It demonstrates why fitting a
better example alone is insufficient: implementation and behavioral source need
joint priority-aware budgeting. Add an unrelated regression for mandatory
implementation retention before another artifact; no custom-help solution hint,
grader change, unchanged-candidate retry or relaxed gate is justified.

Before qualification, fresh archive-only recovery reconfirmed ten P6 and ten P7
terminal trials. Only their twenty completed disposable solver session directories
were removed from the RAM disk, freeing space from 155 MiB to about 2.4 GiB.
Protected cohort archives, database state and the separately retained interrupted
P5 workspace remain; no owner memory or configuration was removed.

Official documentation and the pinned CLI's generated schemas identify a possible
incremental usage observation route, recorded in the research-clues note. It is
not implemented or qualified, does not repair historical missing usage, and did
not change this cohort. No source-budget or usage-observation improvement is
accepted on this evidence.

## P9 joint source budget: completed, 19.55% tuning saving, not accepted

An unrelated regression reproduced example preallocation displacing a connected
implementation. Selection now admits priority-nominated root/connected bodies
and compact navigation first with a small behavioral preview allowance, fits
usage into the actual remaining budget, and considers incidental lexical matches
only afterward. The byte ceiling, rank/traversal, five-body bound, exact source,
scope/secret/currentness and execution-assurance labels remain. No field-flow
inference or extra model was introduced. Familiar task-3 pack inspection now
retains both finish and the usage preview within 4,095 bytes; this is tuning
source-coverage evidence, not a task-success or causal benefit claim.

165 combined regression checks pass; 21 later overlapping harness checks also
pass (not 186 unique tests). Installed real CPython extraction localizes 3/3
implementations with call-context, public-test, safe-error, focused stdio and
stale-context/submission controls. The actual Luna client completed five MCP
calls; audit verified exact source/pack responses, scope refusal and independent
native-read isolation. The model's own canary-read claim remains unverified.
Two qualification archives recovered in a fresh archive-only process.

Wheel SHA-256: `51966f80bed96ee05accd53f170fe281606fc3806177d43dbbf223ff7c46c202`.
Manifest SHA-256: `2491042c943ba247109a1dda8e4a20f39dc829edaa0125c8e345e28ee3c58c2f`,
`efficiency-p9c1-frozen.json`, under `joint-source-budget-loop-v9.md`.
All ten fixed attempts completed; all usage receipts are known and all five C
initial-source submissions are verified. No grading infrastructure-invalid trials.

| Measure | Native A | Structure C |
|---|---:|---:|
| Functional/policy passes | 5/5 | 5/5 |
| All-cap passes | 4/5 | 5/5 |
| Usage receipts | 5/5 | 5/5 |
| Total input tokens | 1,126,556 | 906,298 |
| Total output tokens | 8,639 | 7,019 |
| Cached input tokens | 987,904 | 820,224 |
| Median solver seconds | 22.408 | 26.097 |
| Median measured setup/index/context/solver seconds | 23.755 | 33.670 |
| Observed tool calls | 54 | 45 |

The complete paired input saving is 19.5514470652%, below the fixed 20% fallback.
Do not round it up, weaken the threshold or dispatch transfer. Native task 1
passed functional checks but exceeded the post-turn 500k token limit (509,128
input plus 3,543 output). All C trials passed their budgets. Measured path includes
cold indexing/context and is slower for C; this is not a speedup claim. Quality
and capability gates pass, but both token acceptance gates remain false.

Eleven protocol/trial archives round-trip verified under `protected-efficiency-p9c1`;
a fresh archive-only process recovered all ten terminal trials and ten receipts.
No transfer dispatched. Incremental usage transport remains unimplemented and
did not change this cohort. All prior outcomes and missing usage remain intact.

The next bounded hypothesis is lossless metadata reduction: inline graph notes
which point to already included complete implementations can be redundant. First
verify that removing such notes leaves the exact numbered source lines, source
anchors, usage evidence, selection/order, omissions and unknown-target navigation
unchanged. No fixed task hint, code-body reduction, outcome retry or selected-row
comparison is justified by being close to the numerical threshold.

## P10 covered-target navigation: completed, quality passes, usage incomplete

Only inline graph notes targeting complete included implementations are removed.
Missing/partial targets and class-navigation-only targets retain their notes.
Allocation is charged conservatively using original metadata sizes; freed space
is not refilled. The unrelated joint-allocation test now freezes its original
1,202-byte scenario instead of deriving a moving limit from rendered output.
Pre-change golden tests preserve exact numbered source, headers, usage/order and
assurance labels; no code bodies or source locations are shortened.

On all five retained P9 pre-states, source lines and headers match exactly.
Old/new bytes: 4086/3938, 4096/4018, 4095/3867, 4089/3876, 4082/4007.
These are familiar-task rendering checks, not measured total-token savings.
The actual delivered P10 contexts must be compared again after scoring under
the separately retained policy; an unexpected source difference invalidates the
metadata-only intervention claim, even if a numerical gate were to pass.

169 combined regression checks pass, plus 21 overlapping harness checks (not
190 unique tests). Installed actual CPython/public-test extraction localizes
3/3 targets and passes call-context, focused stdio, safe-error and stale-context/
submission checks. Real Luna host/response audit verifies five MCP calls, exact
source/pack bytes, scope refusal and independent native-read isolation. The
model-claimed native canary attempt remains unverified in partial CLI events.
Two qualification archives recovered independently.

Wheel SHA-256: `b40840ddde144f3eb1cea1a3b15283fb7c659376d06cafa140a6078c09097464`.
Manifest SHA-256: `a77202b242f21247f5d9db086742648117452ac7f721c9c56bccc964406232e1`,
`efficiency-p10c1-frozen.json`, under `covered-navigation-loop-v10.md`.
All ten fixed attempts completed. The actual delivered source/header audit
passed all five counterparts against P9 and is retained in
`experiment.source_equivalence`. The protected protocol text was retained with
zero terminal trials at capture; no outcome-driven policy replacement occurred.

| Measure | Native A | Structure C |
|---|---:|---:|
| Functional/policy passes | 5/5 | 5/5 |
| All-cap passes | 3/5 | 5/5 |
| Usage receipts | 4/5 | 5/5 |
| Total input tokens | unknown | 1,022,080 |
| Known input subtotal (not a paired saving) | 1,126,510 | 1,022,080 |
| Total output tokens | unknown (7,801 known) | 7,804 |
| Cached input tokens | unknown (1,051,520 known) | 948,224 |
| Median solver seconds | 30.392 | 27.638 |
| Median measured setup/index/context/solver seconds | 31.720 | 35.074 |
| Observed tool calls | 74 | 54 |

No grading infrastructure-invalid trials. Native task 1 exceeded the post-turn
token cap; native task 3 reached tool 25 and was killed before final usage,
although its retained patch passed checks. All C attempts passed all budgets.
Quality, capability and delivered-source fidelity gates pass; total input saving
is unknown and both token gates remain false. No confirmation dispatched.

All eleven protocol/trial archives round-trip verified under
`protected-efficiency-p10c1`; fresh archive-only recovery retained ten unique
terminal trials and nine usage receipts. No result accepted, no favorable-control
selection or unchanged-candidate retry. All prior measurements remain intact.

The recurring measurement gap now obstructs a quality-passing comparison. Next
is a separately bounded, disjoint CLI incremental-usage/cancellation diagnostic,
not another product heuristic or relaxed cap. Partial counters must not become
complete by assumption; a transport change needs its own source/schema/sandbox/
event-order qualification and new frozen matched protocol before scoring.

Before qualification, only twenty completed P8/P9 disposable RAM sessions were
removed after archive-only recovery of both cohorts. Encrypted archives, retained
database state and the interrupted original P5 workspace remain. RAM space rose
from 293 MiB to about 2.3 GiB; no owner memory/configuration was changed.

## Usage transport diagnostic: bounded evidence, not a scored replacement

The zero-inference `usage-rpc-config-p1-20261017` probe passed under pinned
CLI 0.162.1 with a fresh subscription-only RAM home. Initialization and effective
named permissions passed; an actual public source read succeeded and an actual
out-of-scope canary read failed. No model turn was started. This qualifies the
operator command route only, not model tool enforcement or complete accounting.

The separately bounded `usage-rpc-interrupt-p1-20261017` made exactly one
Luna-low turn on disjoint public CPython source. One command completed with
exit 0. The server emitted a cumulative usage update at event 38 (11,672 input,
9,216 cached input, 67 output, 11,739 total), followed by an interrupted terminal
at event 42 after the requested cancellation. No later usage update appeared in
the two-second terminal drain. No file-change item was observed.

This proves incremental counters survive this cancellation route. It does not
prove full accounting for an interrupted in-flight request or qualify this
transport for scored work. Counters remain partial/unverified for completeness;
they are not summed across snapshots, and none of the six historical missing
receipts is backfilled. P9 remains 19.551447%, P10 total saving remains unknown,
and the confirmation tasks remain unrun. No cap, score or pass floor changed.

Twenty local no-inference transport/accounting/runner checks pass. The tests
caught and corrected an exit/cleanup race in the new helper before real probes;
cleanup failure now cannot suppress evidence capture. This is measurement-path
progress, not an additional token-efficiency result. Future experiments must
retain complete-total gates unless a separately specified accounting method
actually proves the required full-scope comparison.

Both diagnostic bundles round-trip verified on MEM under
`protected-usage-rpc-p1`; a fresh process recovered one configuration event and
three cancellation/source-retention events without access to the vault.
An initial glob-based recovery command encountered a macOS sidecar rather than
an archive; explicit declared run filenames recovered successfully. Neither
the archives nor the private internal keys were changed by that read failure.

## P11 producer-linked usage: completed, failed quality gate

P10 task 1's retained partial test excerpt included result assertions without
the producing invocation. A generic same-block source-group fitter now keeps
the call-producing assignment and its assertions together atomically, including
multiline arguments. This is syntactic evidence, not inferred runtime behavior
or a new authority-bearing relationship. Unrelated control-flow/nested scopes
are not joined. Original numbered source, visible gaps, byte limits and all
governance/scoring gates remain unchanged.

Four new regressions cover source identity/UTF-8 bounds, multiline atomicity,
oversized group omission, and block/scope/reassignment handling. The expanded
local benchmark/packing suite passes 157 checks; 12 additional overlapping
progressive/inventory checks pass (not 169 unique checks). On the retained public
P10 test source, a 205-byte window now includes `runner.invoke(cmd, [arg])`
together with all three result assertions. That is an excerpt-quality check,
not a solve, benchmark pass or measured token reduction.

Fresh wheel SHA-256:
`e0953ba632bfe0f29a36d66e67f769361cafab9d3ab98baa122aec09cee6b9e6`.
The first installed qualification failed before extraction because the operator
supplied a malformed image ID. That failed record remains. The corrected
command, fresh paths and `implementation-localization-p11r1-logging` passed all
three disjoint public CPython localization, caller/usage, focused-MCP and stale
source/submission controls with zero model calls. The separate actual Luna host
diagnostic `progressive-host-p11` returned five MCP calls; its retained response
audit checks exact returned source/pack bytes, scope refusal and the independent
native read barrier. This is not full CLI/system capture or proof that the model
itself attempted the canary read.

All ten P11 attempts completed under frozen manifest
`eb6ba7979b432617955a4671304c28c45afb59f6bfb577e9c46597b3159cc359`.
No confirmation ran. The unchanged exec scorer and complete usage/5-of-5/exact-20%
gates remain; the partial-usage app-server route is not promoted.

| Measure | Native A | Structure C |
|---|---:|---:|
| Functional/policy passes | 5/5 | 2/5 |
| All-cap passes | 4/5 | 2/5 |
| Usage receipts | 5/5 | 4/5 |
| Total input tokens | 1,170,061 | unknown (552,917 known subtotal) |
| Output tokens | 9,488 | unknown (5,622 known subtotal) |
| Cached input tokens | 1,046,528 | unknown (489,216 known subtotal) |
| Median solver seconds | 26.483 | 24.984 |
| Median measured setup/index/context/solver seconds | 27.792 | 33.037 |
| Observed tool calls | 50 | 52 |

Capability gate passes; quality and token gates fail. C task 2 reaches tool 25
before terminal usage and leaves a logic error: candidate help names enter the
same set later used to exclude them, so every name is filtered out. C task 3
leaves invalid Python syntax. C task 4 fails four pager temporary-file checks.
These observations do not establish that the partial-example change caused the
failures. The grader's task-3 `infra_invalid=true` flag conflates collection
errors with environment failures; a read-only compile/output audit corroborates
candidate syntax failure. The original flag/score remains retained and the row
is not excused, excluded or retried. Eleven cohort archives round-trip and
fresh archive-only recovery verify all ten terminal trials.

Three P11 qualification bundles (including the failed command) are retained
under `protected-progressive-p11` on MEM. Round-trip and fresh archive-only
recovery verify the failed/qualified localization records and actual host
response audit. Private keys remain internal.

## Progressive uptake audit: initial packs did not become active retrieval

Read-only audit `efficiency-tool-use-audit-p6-p11-20261017` covers all sixty
declared terminal attempts in P6–P11, without inference or selected rows.
All thirty C traces contain zero completed AtMem MCP calls. Completed native
command counts A/C are P6 47/40, P7 39/25, P8 43/50, P9 41/32, P10 50/36,
P11 35/34. No invalid JSON lines were observed. Output byte volumes are retained
as bytes, not inferred token savings or complete provider/model-input capture.

Thus these focused rounds measured an initial source pack plus ordinary native
exploration, not active graph-assisted retrieval. The observed absence does not
prove tools were unavailable or explain the agent's choice; the explicit host
diagnostics did observe successful MCP calls. Tool uptake needs a separate
generic integration test rather than more small familiar-task packing tweaks.
The next diagnostic is `guided-retrieval-diagnostic.md`, using fixed trusted
server guidance and disjoint public CPython source, not hidden Click feedback.

## Requested Claude review: retire familiar-task tuning

One read-only Claude CLI subscription review returned successfully with model
metadata `claude-opus-5-5`, medium effort, all tools disabled and no model
fallback. The full review and source provenance are retained; it is model
criticism, not independent replication. The reviewer agrees that adaptive
selection over the same five tasks creates a serious overfitting risk.

The [adoption notes](2026-10-17-benchmark-review-adoption.md) record corrections:
initial pack construction does use graph traversal, although on-demand MCP
calls were not observed; cache counters must not be double-counted; the
post-turn token audit is not an upper bound for missing usage. No proposed
quality-margin change or primary imputation is accepted.

Further scored tuning on the familiar Click five is retired. The unchanged
past outcomes stay visible, including P11's negative result. The unused Click
set remains a possible same-repository check, not cross-repository proof or a
variant-selection set. Spec 042 `cross-repository-evaluation-plan.md` defines
external task/environment preflight, exposure/full-usage qualification, at most
two frozen validation candidates, and separately locked repository-disjoint
confirmation. No external repair benchmark or new guidance-model probe has run.

Fixed Code-only MCP initialize guidance is implemented and passes local
contract checks, including source/instruction separation and unchanged generic
AtMem MCP initialization. The proposed single getLogger pair is held after
review as too weak for benefit inference; it was never executed. Guidance,
tool availability and token savings remain separate unproven claims.

