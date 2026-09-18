# Review and validation record

## Claude CLI review — 2026-09-18

Mode: supplied-document-only, read-only, no tools, no MCP servers, no session
persistence. No code execution or repository inspection was attributed to the
reviewer. First response included a proposed plan-file heading; no such write was
requested or executed by this tool-disabled invocation.

First verdict: revise before P0a. Dispositions:

| Finding | Resolution |
|---|---|
| Completion conflated with authorized delivery | Separate nullable authorization, evidence and output-parity flags; unknown is not true. |
| Outcome precedence undefined | First authoritative terminal event wins; rejected retroactive precedence because it rewrites history. |
| Expired versus censored ambiguity | Keep observed censoring plus derived missed-deadline status; never invent expiry evidence. |
| Generator lag biases latency | Report both scheduled and admitted latency; real runs need a frozen lag-validity budget. |
| Survivor percentiles reward drops | Include all outcome denominators and a labeled all-offered success bound. |
| Isolation and report version unspecified | Pure no-I/O research module, closed synthetic schema and isolation tests. |
| Unequal tuning / held-out protocol | Equal maximum tuning trials, unseen mixtures and frozen primary comparison; final precision study still pending. |

Second verdict after revised protocol: **ready for the bounded P0a library, not
production**. Implementation refinements: explicit unknown caller-supplied
provenance; no arbitrary event-history payload in P0a; per-lane unknown counts and
known-success lower bounds; distinguish empty from unattainable quantiles; reject
invalid observation states. These are included in P0a implementation scope.

## Spec Kit analyze — before implementation

Prerequisite checker resolved `specs/033-memory-fabric`; no extension hooks.
Read spec, plan, tasks and current constitution. No identified critical/high
conflict in the bounded first milestone. This is not an all-repository audit.

| Requirements | Task coverage |
|---|---|
| FR-001 | T001, T004, T006–009, T017 |
| FR-002–003 | T004–006, T009, T015 |
| FR-004 | T008–010 |
| FR-005–006 | T011–012, T016 |
| FR-007 | T009, T012–013, T016 |
| FR-008 | T013–014, T016 |
| FR-009 | T005–006, T011–012, T014, T016–017 |
| FR-010 | T008, T011–012, T016–017 |
| FR-011–012 | T005, T009, T013, T015, T019 |
| FR-013 | T001–002, T007, T010, T015, T018–019 |
| SC-001 | T004–006 |
| SC-002 | T008–010 |
| SC-003 | T012, T014, T016 |
| SC-004 | T013–015, T018 |
| SC-005 | T016–018 |

18 requirements/success criteria, 19 tasks, 100% planned coverage; no unmapped
tasks (T003 is the cross-artifact gate). Deferred scientific thresholds and real
authority linearization are explicit gates, not completed guarantees. No
remediation needed to begin P0a; do not proceed to production integration from
this finding alone.

## Validation

P0a protocol and P0b exploratory local runner. No scheduling result yet.

- `python -m pytest -q tests/test_memory_fabric_protocol.py`: **45 passed**.
- Focused combined run (protocol, retrieval benchmark, evidence role matrix,
  AES-GCM/tamper and default full-capture exact encryption): **50 passed**.
- Python 3.10 AST syntax and new-file trailing-whitespace checks passed. This is
  not an executed Python 3.10–3.13 runtime matrix; execution used Python 3.12.2.
- A broader run of retrieval benchmark, benchmark runner, evidence protection
  and delegated control was **interrupted after 355.47 seconds**, with **27
  passed, 2 skipped**. It was waiting in `socket.py:707`; the precise test/cause
  was not established. It is incomplete, not a passing regression suite, and
  must not support release readiness. No production code was changed.

## Implementation review dispositions

Claude reviewed the supplied Python without executing it. Incorporated:

- mutually exclusive verification buckets (known failure dominates unknown);
- aggregate deadline-miss counts without converting censoring into fake expiry;
- separate observation/horizon digest, keeping workload digest policy-independent;
- exact rational nearest-rank arithmetic and bounded integer fields, with tests.

Not adopted unchanged:

- Censoring does not invalidate the exact count of observed completions within a
  fixed measurement window. Goodput explicitly names that window; eventual
  completion probability is not estimated. Unknown verification remains null.
- A revocation may predate arrival. Its metadata is retained uninterpreted in
  raw observations, not discarded or treated as proof of enforcement.

One response claimed a plan file was written despite disabled tools. The named
path was checked and did not exist. Treat this as unsupported reviewer narration,
not an action or evidence. Review findings are assessed against the code/tests.

Final Claude review after corrections: **ready within the stated synthetic
protocol scope; no remaining correctness blocker found in that read**. It did
not execute tests or approve a production scheduler. Equal timestamps are allowed
to represent zero-duration synthetic stages; neither generation metadata nor
reviewer agreement proves actual authority enforcement.

Next required work: complete T009 real-baseline profiling; P1 authority/resource
model and P2 scheduler work remain unimplemented. Do not write paper results yet.

P0b update (2026-09-18): T008 and exploratory T010 completed. The focused
protocol + local-runner test suite passes 46 tests. Four paired Poisson trials
at 80 rps found queueing headroom but also nine write close/vector-sync errors
under two-worker concurrency. See `research.md` and raw `results/` reports.
T009 is not complete: cold/warm isolation, final manifests and full stage
attribution remain pending. This pilot is not release or scheduler evidence.

Write-isolation follow-up: local in-process serialization and an isolated
single-writer lane each removed observed write/vector-sync exceptions in four
trials, but caused higher tail latency and admission refusals. These negative
results rule out calling either a proven improvement. Focused protocol/runner
tests passed 48/48. No production storage code was changed.

Direct comparison follow-up: a research-only one-worker deadline/estimated-size
dispatcher was run against unchanged one-worker FIFO AtMem in five paired,
interleaved real local trials. Workload/source digests match within every pair;
all 600 combined offered requests completed with no errors/refusals. Interactive
p95 improved in four pairs, but bulk and overall p95 worsened. The initial
paired run had an incorrect lane label for writes and is explicitly excluded;
corrected `paired-lanefix-*` files support the table in `research.md`. No P1
authority proof or P2 held-out gate is implied. Focused tests pass 50/50.

Subsequent Homa/DRR review supersedes those small pilot comparisons: see
[homa-review.md](homa-review.md). It corrects the phrase-only output check and
different dispatcher confound, uses service-time debt and common execution,
and records three read-only Claude review rounds. Seventy frozen measured
trials (11,200 offered operations) accepted neither candidate. A reproducible
shared-corpus BM25 effect invalidates the static oracle in write-heavy trials;
four generator-lag failures and wide A/A noise are retained. The corrected
protocol/runner/scheduler suite passes 61 tests. P1/P3 remain open.
