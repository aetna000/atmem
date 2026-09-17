# NumPy amendment review — 2026-09-17

Scope: FR-018–FR-020 and T024–T028 only; no release authorization.

## Claude CLI round 1 (read-only)

Command: `claude -p --permission-mode plan --tools Read,Grep,Glob --output-format text`.
Verdict: REVISE. Accepted: cache float64 rather than repeatedly upcasting float32;
publish one immutable entry after finite validation; distinguish retained/peak
memory; clear before lock release; do not expose vectors in diagnostics; measure
alternating subjects; keep review and benchmark evidence separate.

Decision: retain one entry rather than a multi-subject LRU to limit residency and
complexity. Explicitly measure thrashing and disclose backend coverage. No new
thread-safety claim; no change to the existing SQLite connection contract.

## Spec Kit analysis

Amendment coverage: FR-018/019 → T025/T026/T028; FR-020 → T027/T028;
review → T024. No schema or base-dependency change; existing canonical validation
and delegated contracts remain unchanged. Broader T001–T023 remain independent
and unfinished as marked. Partial selection is explicitly deferred, not silently
claimed implemented. No unresolved constitutional conflict in this slice.

## Claude CLI round 2

Verdict APPROVE, no substantive blockers. Explicit read-only array flag,
pre-allocation retained-byte check and no zeroization claim carried forward.
Implemented the approved design and 28 targeted tests passed.

## Measurement-driven revision

SHA-256 validation dominated the synthetic workload: at 350 x 384 dimensions,
kernel median 0.235 ms uncached versus 2.510 ms reused; full plaintext search p95
3.528 ms uncached versus 4.416 ms reused. These are failed optimization results,
not a speed claim. Proposed exact tuple-of-bytes comparison instead, retaining
source blobs under the same total ceiling; sent for another read-only review
before implementing that revision.

## Claude CLI revision review and code review

Exact byte comparison revision: APPROVE, no blockers. Accepted immutable bytes
coercion, total blob/matrix accounting and realistic-width equality tests.
Separate code review: REVISE for one-shot overhead, missing purge cleanup and
unfinished benchmark evidence. Addressed with opt-in `cache_vectors=True` (native
default unchanged), local purge/discard/policy cleanup, and explicit single-use
benchmark profile. Cross-instance mutations are detected on next search; no
background erasure or zeroization claim is made.

## Final Claude CLI code review

Verdict: APPROVE as experimental, opt-in, not-release-ready implementation.
Confirmed exact byte keys, default disabled, purge/policy/discard cleanup,
realistic-width tests and honest negative measurements. No substantive blockers.
Remaining limitations: rebuild does not eagerly clear old matrices (next search
invalidates); score bit-equality is tested on the installed NumPy, not guaranteed
across every BLAS build. Codex agrees with approval under the explicit opt-in scope.

Final command:
`./.venv/bin/python -m pytest -q tests/test_benchmark_external.py tests/test_semantic_search.py tests/test_semantic_rebuild.py tests/test_retrieval_quality.py tests/test_atbot_companion.py tests/test_semantic_matrix_cache.py`

Result: **74 passed in 12.25s**. `git diff --check` passed. No commits, pushes,
version changes, installation/deployment or publication performed. Existing
untracked research and MemoryBench files were preserved untouched.
