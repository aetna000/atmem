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
recorded an actor but did not enforce issued principal authority. AtMem 2.3.6b1
addresses those boundaries. Its comparison table remains pending until the
tagged wheel—not this source checkout—completes the same 700 trials.

## Benchmark identity

- Upstream project: `iluxu/memory-integrity-benchmark`
- Frozen upstream commit: `ca8b430736f08c5dc66938b6e3b5319cea53ec8b`
- AtMem adapter/evidence branch:
  [`aetna000/memory-integrity-benchmark`](https://github.com/aetna000/memory-integrity-benchmark/tree/adapters/atmem-2.3.5)
- AtMem 2.3.5 wheel SHA-256:
  `16e6fc5cf7a7f6964ce40ceffb124c7b386c08472ae5b027b8635a378ec62269`
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

## Changes made for 2.3.6b1

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
`NOT_REPRESENTABLE` in the 2.3.6b1 run. The product correction is exercised by
AtMem's own authority regression suite, while the benchmark reports only what
its public contract can honestly express.

## Controlled before/after protocol

The 2.3.6b1 comparison will use the same seven attack YAML files, 100 trials per
category, seed, report code, publication validator, Python line, and local
provider-free configuration. The adapter may change only where it maps the new
native APIs. Publication is refused for editable imports, dirty run commits,
changed attack/config digests, missing/duplicate trials, mixed package identity,
plaintext synthetic secrets in published artifacts, absolute local paths, or
checksum drift.

The comparison will be added only after the released wheel SHA-256 and matching
bridge version are known and all raw evidence validates. A source-tree run is a
development gate, not the release result.

## Scope and limitations

This evaluates seven memory-integrity attack contracts. It does not measure
general answer quality, retrieval MRR, latency, throughput, broad prompt-
injection resistance, complete application security, or compliance. Source
evidence retention is not semantic-memory retention, encryption is not
non-retention, and a hash does not replace retained evidence.

AtMem 2.3.6b1 does not retroactively delete records created by 2.3.5. Taint
propagation covers explicit direct parents rather than inferred graph-wide data
flow. Purpose-scoped recall remains unsupported and undeclared. Any stable
2.3.6 conclusion depends on the prerelease rerun and normal release gates.
