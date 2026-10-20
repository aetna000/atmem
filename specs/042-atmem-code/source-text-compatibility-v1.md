# Source text compatibility correction — new preview, not frozen-wheel repair

2026-10-18. Governs T084 under FR-018/019/023 and SC-008/010/012.
The nineteen-task staging manifest and wheel
`9900aa70371a1ec911b7215532711cbdc83da726198ca0eacf85bbf6054146c8`
remain unchanged, including their failures. No confirmation solver has run.

## Evidence and bounded correction

Pylint's real source contains a Python file declaring ISO-8859-1 and text
fixtures with UTF-16/UTF-32 byte-order marks. They are legitimate original
repository bytes, not a reason to drop files or change grading. Rich capture,
worker secret screening, source-backed packing, portable bundle validation and source presentation
currently assume UTF-8 independently. Correct these paths consistently.

Use Python's standard PEP-263 encoding detector for `.py` files; honor explicit
UTF-32, UTF-16 and UTF-8 BOMs for other admitted text; otherwise require strict
UTF-8. There is no heuristic encoding guess, replacement decoding, translation,
transcoding of retained source or execution of repository code. Unknown,
contradictory or invalid encodings fail closed. Strict execution capture rejects
the snapshot. The explicitly partial graph path may exclude such a file with a
visible `source_encoding` count; it must never decode it lossily or send it to
the worker. Validate those omission counts before publication and when serving
cached projections, alongside the existing per-file-budget omissions.
Secret screening sees the fully
decoded text before the unchanged original bytes enter extraction. Native
source hashes, source archives and snapshot identities remain over original
bytes, not UTF-8 re-encodings. Lines in returned excerpts refer to decoded
original source lines; provenance remains bound to original file bytes.

This is a new versioned rich source policy. Old generations are not silently
relabelled. Existing graph-only oversized-file policy remains, and strict
experience capture does not acquire partial identities. Do not modify the
frozen installed environment.
The limited legacy AST graph can retain its existing rejection behavior; this
correction targets the rich structural path used by the efficiency loop.

## Required gates

1. Strict UTF-8 and UTF-8 BOM, declared Latin-1 Python, UTF-16/32 BOM text,
   conflicting Python BOM/cookie, unknown codec and malformed bytes.
2. Secrets encoded in every supported representation are rejected before worker
   dispatch; source archives retain exact original bytes and hashes.
3. Packing and `knowledge-source` return consistent decoded source lines under
   unchanged byte budgets, scope, freshness, disclosure and transport checks.
   Encrypted project bundles preserve exact original encoded source bytes and
   screen decoded text during validation rather than assuming UTF-8 on restore.
   Invalid-encoding graph exclusions are visible and cannot conceal a stale
   omission count or a race during extraction; strict capture still rejects.
4. Existing strict/graph capture omissions, worker isolation, source changes,
   encrypted storage, ordinary UTF-8 behavior and legacy-generation reads.
5. New installed candidate, real failed-source replay and explicit prospective
   evaluation treatment before any scored comparison. Local fixtures alone do
   not close T084. Generation-row size remains a separate unresolved blocker;
   no artifact removal, raised row cap or new confirmation claim is authorized
   by this encoding correction.
