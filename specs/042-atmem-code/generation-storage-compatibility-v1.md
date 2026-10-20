# Bounded rich-generation storage — prospective preview correction

Source-preview follow-up, 2026-10-19: the new bounded graph correction raises
only the logical generation envelope to 256 MB and permits a versioned bounded
XZ fallback when zlib cannot fit the unchanged physical row. See
`swebench-preparation-corrections-20261019.md`. The protocol below and its frozen
historical runs retain their original parameters and outcomes.

2026-10-18. T085; FR-019/026, SC-012. The frozen nineteen-task staging
candidate remains unchanged and its two PyVista-4853 failures remain failures.
No solver output, score or token result informed this correction.

## Problem and proposed boundary

The rich generation retains original source, original extractor artifacts and
typed projections in one canonical JSON document. That complete representation
can exceed the physical Code document limit of 16,000,000 bytes even when
capture and extraction respect their existing independent limits. Removing
artifacts or retaining hashes instead of originals is unacceptable.

Add an explicit versioned, lossless storage envelope for large
`knowledge-generation` documents only, inside the existing authorized encrypted
Code document store. Keep the physical row limit at 16,000,000 bytes and all
existing source/worker/graph/query/output limits unchanged. Ordinary documents
and ordinary-size generation rows keep their existing JSON representation.
Use standard-library compression with strict bounds: logical canonical JSON
at most 64,000,000 bytes; encoded envelope within the unchanged physical limit;
bounded decompression verifies exact declared size, SHA-256, EOF and no trailing
or concatenated stream before parsing. An incompressible or oversized document
is rejected, not truncated or partially published. No filesystem blob backend,
plaintext cache, fallback encryption or benchmark-only storage bypass.

Bind the envelope to subject, project, kind and document identity. Only the
normal Code store methods encode/decode it; all callers receive the complete
original logical object, including list/item/export paths. Do not accept this
envelope for another document kind. Canonical authorization and encryption stay
outside and before content access. Compression does not provide confidentiality
or authenticity; the existing protected storage boundary still does.

## Publication, portability and compatibility

Generation publication and job completion stay in their existing transaction.
Reconstruction failure withholds the projection; it must not break ordinary
deterministic memory or return an empty graph as a successful result. No mixed
generation or partial logical document is visible. Scoped deletion removes the
same physical row; no auxiliary artifacts survive. Encrypted project export
contains complete logical generation data and import repacks under the target
store's validated policy. Existing 128 MB whole-bundle limit remains.

Actual large-bundle testing also exposes the installed signing binding's
message-size limit. Keep existing encryption/signature primitives unchanged;
for larger project exports adapt the already exercised benchmark archive's
authenticated-chunk framing into a product-owned transport. Use a separately
named Code-project outer format, 196,608-byte plaintext pieces, at most 400,000
encoded bytes per signed/encrypted piece, and the unchanged 128 MB total
logical bound. Each protected inner piece binds ordinal, count, total size and
the full original plaintext digest. Verify the trusted signer on every piece,
reject reordering/truncation/mixing/oversized framing, and retain original
small-format reads and writes. Project identity and semantic metadata stay
inside ciphertext, not in the outer transport. Do not prehash a message and
call it the old signature format, weaken verification, or truncate evidence.

Legacy JSON documents remain readable without rewrite or schema migration.
New compressed generations are an additive persisted preview format, not data
that an older preview is expected to understand. Document downgrade behavior:
the older preview must not be represented as supporting those derived rows;
use a supported reader/export or explicitly rebuild derived projections. Do
not silently replace a compressed record with a lossy legacy representation.
No existing public release or frozen benchmark environment is upgraded here.

## Required verification

- Exact logical round-trip above 16 MB, unchanged small/legacy records and no
  format collision with an ordinary application dictionary.
- Wrong subject/project/kind/identity, malformed header/base64, non-dict JSON,
  incorrect size/hash, truncated/concatenated/trailing streams, decompression
  bombs and incompressible/over-budget writes are rejected.
- Single/list/item reads, updates, transaction rollback/publication crash,
  foreign-scope isolation and scoped deletion preserve their existing behavior.
- Real encrypted-store and encrypted project-bundle round-trip retain exact
  source/artifact bytes; malformed source still fails the source policy.
  Chunked exports additionally reject missing/reordered/duplicate/mixed pieces,
  wrong signers, corrupt ciphertext, malformed authenticated framing and total
  size violations; legacy small exports still round-trip unchanged.
- A separately pinned installed preview replays the actual failed PyVista
  indexing case without changing source, extractor, model policy or tests.
  Full selected-cohort readiness and explicit prospective evaluation treatment
  remain necessary before any scored confirmation or goal-completion claim.

This correction does not promise arbitrary repository size, solve the separate
encoding qualification task or establish a token-saving result.
