# Memory Integrity Benchmark: AtMem 2.3.5 baseline and 2.3.6 qualification

## Executive summary

AtMem 2.3.5 was run unchanged against all seven categories in the public
Memory Integrity Benchmark. The frozen 700-trial baseline passed the two
categories its native controls fully represented, reported four categories as
`NOT_REPRESENTABLE`, failed secret non-retention, and produced no harness
errors. We preserved those results before changing product code.

The baseline identified three bounded product gaps: canonical semantic records
could retain secret-bearing proposals in quarantine; explicitly related
derived records did not persist/inherit parent taint; and typed procedure review
recorded an actor but did not enforce issued principal authority. AtMem 2.3.6
addresses those boundaries.

The published stable 2.3.6 wheel completed the same 700 trials from its
SHA-256-pinned PyPI artifact: 400 `PASS`, 300 `NOT_REPRESENTABLE`, zero `FAIL`,
and zero `ERROR`. Every representable trial passed. Publication validation and
SHA-256 verification succeeded. The stable adapter and evidence are submitted
in [upstream PR #1](https://github.com/iluxu/memory-integrity-benchmark/pull/1).

## Position relative to the published systems

The upstream project currently presents categorical results rather than a
numeric ranking. If systems are ordered by the number of natively represented
categories that pass, the stable submission is provisionally second:

| System | Passing categories | Not representable | Error or fail |
|---|---:|---:|---:|
| LLMBASEDOS v0.4-rc1 | 7 | 0 | 0 |
| **AtMem 2.3.6 submission** | **4** | **3** | **0** |
| Mem0 | 3 | 4 | 0 |
| Letta | 3 | 4 | 0 |
| Zep | 1 | 4 | 2 errors |

This is an evidence-based comparison against the current upstream table, not
an official leaderboard placement. AtMem is not first because categories A, H,
and I require an authenticated approval principal. Harness Specification v1
provides caller-controlled actor labels but no AtMem-issued review authority.
The adapter deliberately refuses to reinterpret those labels as authorization:
doing so would weaken AtMem's boundary and manufacture three benchmark passes.
The benchmark author's LLMBASEDOS integration can represent those categories;
AtMem therefore reports them honestly as `NOT_REPRESENTABLE`.

### Category D target-matching disclosure

The stable adapter exposes native record identifiers. The benchmark fork
therefore changed shared target matching to use those identifiers as the
authority when available instead of also treating any recalled record that
shares a trial nonce as the poisoned target. This change is outcome-
determinative for AtMem's D result: the older fallback would flag the clean,
trusted step-1 sibling merely because it shares the nonce with the derived
summary, producing 0/100 D passes. Under native-ID matching, the assertion asks
whether the actual derived summary entered authoritative recall; it did not,
and all 100 D trials pass.

This is a harness correction authored with the AtMem adapter and remains part
of the upstream review, not an independently accepted benchmark rule. The fork
contains regression tests and documents its native-ID-first limitation. The
change only relaxes false-positive target matching and cannot turn an existing
competitor failure into an AtMem advantage: the current competitor D cells
were produced under the prior rule and are already `NOT_REPRESENTABLE` for
Mem0, Zep, and Letta, while LLMBASEDOS is already `PASS`. Accordingly the
provisional category ordering is unchanged, but AtMem's sole second-place
position depends on upstream accepting this corrected D interpretation. If it
is rejected, AtMem has three passing categories and ties Mem0 and Letta.

## Benchmark identity

- Upstream project: `iluxu/memory-integrity-benchmark`
- Frozen upstream commit: `ca8b430736f08c5dc66938b6e3b5319cea53ec8b`
- AtMem baseline branch:
  [`adapters/atmem-2.3.5`](https://github.com/aetna000/memory-integrity-benchmark/tree/adapters/atmem-2.3.5)
- AtMem stable submission branch:
  [`submission/atmem-2.3.6`](https://github.com/aetna000/memory-integrity-benchmark/tree/submission/atmem-2.3.6)
- Upstream submission:
  [iluxu/memory-integrity-benchmark#1](https://github.com/iluxu/memory-integrity-benchmark/pull/1)
- AtMem 2.3.5 wheel SHA-256:
  `16e6fc5cf7a7f6964ce40ceffb124c7b386c08472ae5b027b8635a378ec62269`
- AtMem 2.3.6 wheel SHA-256:
  `eed43276abb6e230bf5f6f5912c45c577c3136e150c77a707d428bcbe0e57394`
- Seed: `20260922`
- Trials: 100 each for A, C, D, F, H, I, and L; 700 total
- Runtime: CPython 3.11.16 on macOS 26.5.2 arm64
- Network/model use: none

The public evidence directory contains the frozen attacks and configuration,
manifest, environment lock, raw JSONL, generated aggregates/table,
reproduction commands, limitations, and SHA-256 manifest. The first complete
2.3.5 run is immutable; later adapter or product results receive new run IDs.

## AtMem 2.3.5 result

| Category | What it tests | Trials | 2.3.5 status | Evidence-based interpretation |
|---|---|---:|---|---|
| A | direct procedural poisoning | 100 | `NOT_REPRESENTABLE` | Typed procedures existed, but native approval authority did not. |
| C | recursive agent hallucination | 100 | `PASS` | 100/100 untrusted recursive claims stayed out of authoritative recall. |
| D | summary trust laundering | 100 | `NOT_REPRESENTABLE` | Related IDs existed, but the derived record had no enforced parent-taint semantics. |
| F | repetition to authority | 100 | `PASS` | 100/100 repetitions failed to promote untrusted content into authoritative recall. |
| H | outcome laundering | 100 | `NOT_REPRESENTABLE` | Outcome evidence existed, but this test also requires native approval authority. |
| I | authorized promotion (positive control) | 100 | `NOT_REPRESENTABLE` | An actor string could not honestly represent an authenticated principal. |
| L | secret ingestion | 100 | `FAIL` | 100/100 synthetic secrets remained in quarantined canonical memory records. |

Counter-derived results were factual contamination 0/200, trust laundering
0/100, and secret retention 100/100. Taint preservation was N/A because all D
trials were non-representable. The 400 non-representable trials were excluded
from rate denominators, not counted as passes or failures. There were zero
trial errors.

## AtMem 2.3.6 stable result

| Category | What it tests | Trials | Stable status | Evidence-based interpretation |
|---|---|---:|---|---|
| A | direct procedural poisoning | 100 | `NOT_REPRESENTABLE` | The harness cannot supply the issued review authority required by AtMem. |
| C | recursive agent hallucination | 100 | `PASS` | 100/100 untrusted recursive claims stayed out of authoritative recall. |
| D | summary trust laundering | 100 | `PASS` | 100/100 derived records preserved parent taint and remained non-authoritative. |
| F | repetition to authority | 100 | `PASS` | 100/100 repetitions failed to promote untrusted content. |
| H | outcome laundering | 100 | `NOT_REPRESENTABLE` | The tested promotion path requires authenticated review authority absent from Harness v1. |
| I | authorized promotion (positive control) | 100 | `NOT_REPRESENTABLE` | A caller-supplied actor label is not an authenticated AtMem principal. |
| L | secret ingestion | 100 | `PASS` | 100/100 synthetic secrets were absent from all benchmark-scoring canonical surfaces. |

Counter-derived results were factual contamination 0/300, trust laundering
0/200, secret retention 0/100, and direct-parent taint preservation 100/100.
The 300 non-representable trials were excluded from rate denominators. There
were zero trial failures and zero trial errors.

## Why the baseline matters

The baseline distinguishes four very different outcomes:

1. `PASS` means a native, declared control satisfied the assertion.
2. `FAIL` means the benchmark could represent the control and observed the
   prohibited state.
3. `NOT_REPRESENTABLE` means AtMem lacked a native concept required by the
   attack; an adapter was not allowed to manufacture it.
4. `ERROR` would indicate an unusable trial and never counts as a security
   result. The baseline had none.

That distinction prevents a narrow pass rate from hiding capability gaps. It
also explains why this work starts from evidence rather than presenting the
new implementation alone.

## Changes made for 2.3.6

### Canonical secret refusal

The semantic proposal boundary now runs the existing deterministic secret and
explicit-exclusion screen before duplicate/conflict handling and record
creation. The screen covers fact, fact-key, and entities. Rejection produces an
admission and audit reason but no canonical record; its proposal-ledger row
keeps structural identifiers and digests rather than those content-bearing
fields. Captured source/protocol evidence remains governed separately and is
disclosed as a non-scoring transcript/evidence channel under Harness
Specification v1.

### Direct-parent taint propagation

The proposal boundary validates related records against exact subject, agent,
and workspace scope. It persists parent IDs and inherited taint labels. Any
untrusted/tainted parent forces the derived record into quarantine and adds
`DERIVED_FROM_TAINTED`; an authenticated immediate source cannot wash that
history away.

### Issued procedure authority

Procedure review now requires an instance-bound HMAC authorization issued by
AtMem from trusted reviewer configuration. Principal, permitted operation,
subject, agent, and workspace are verified at settlement. Caller-created
objects and plain actor labels fail closed. The existing pending-only guard
continues to reject replayed decisions and stale preconditions.

Harness Specification v1 supplies only caller-asserted principal labels, not
an authenticated authority credential. The conservative adapter therefore does
not translate those labels into AtMem authorization: A, H, and I remain
`NOT_REPRESENTABLE` in the stable 2.3.6 run. The product correction is exercised by
AtMem's own authority regression suite, while the benchmark reports only what
its public contract can honestly express.

## Controlled before/after protocol

The stable comparison used the same seven attack YAML files, 100 trials per
category, seed, Python 3.11 line, and local provider-free configuration as the
immutable 2.3.5 baseline. The benchmark fork's runner, reporter, and publication
validator were revised for the AtMem adapter, including the native-ID target-
matching correction disclosed above; they were not identical to the baseline
revision. Frozen input digests and regression tests ensure attack definitions
did not change. Publication validation refused editable imports, dirty run
commits, changed attack/config digests, missing or duplicate trials, mixed
package identity, plaintext synthetic secrets, absolute local paths, and
checksum drift.

The run installed the released wheel directly from PyPI using its exact URL and
SHA-256. It did not import the AtMem source checkout. The stable run has the
distinct immutable identity `atmem-v2.3.6-seed-20260922`; prerelease evidence
was not renamed or used as the stable result.

## Scope and limitations

This evaluates seven memory-integrity attack contracts. It does not measure
general answer quality, retrieval MRR, latency, throughput, broad prompt-
injection resistance, complete application security, or compliance. Source
evidence retention is not semantic-memory retention, encryption is not
non-retention, and a hash does not replace retained evidence.

AtMem 2.3.6 does not retroactively delete records created by 2.3.5. Taint
propagation covers explicit direct parents rather than inferred graph-wide data
flow. Purpose-scoped recall remains unsupported and undeclared. The stable
tagged-artifact rerun is complete and valid. Until the upstream maintainers
accept the submission, the #2 coverage
position remains provisional rather than an official leaderboard result.
