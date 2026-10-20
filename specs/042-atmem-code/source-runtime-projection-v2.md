# Source/runtime projection v2 — benchmark qualification

Prospective qualification correction, 2026-10-18; T082. This is not a product
change, a passed confirmation, or permission to change the frozen candidate,
task pool, solver prompts, tests, grade denominators or primary endpoints.
All previous source-boundary failures remain retained. No model run may use
this projection until its controls pass and its exact implementation is locked.

## Two separately verified roles

Both arms receive the identical regular-file source projection. Existing
1,000,000-byte source-file and 40,000,000-byte source-snapshot budgets remain.
Editable implementation roots and protected test roots remain as registered.
An operator-frozen, versioned manifest separately describes immutable runtime
fixtures already present in the pinned evaluator image. It is not supplied by
a model and cannot be widened through a model request.

Recognized binary image/font assets outside editable Python implementation may
remain in the runtime image rather than be copied into model-visible source.
Use a closed suffix/signature policy, streamed Git-blob/SHA-256 verification,
and explicit separate limits of 32,000,000 bytes per immutable asset and
256,000,000 aggregate immutable regular-file bytes. These are runtime-inventory
limits, not larger source/context limits. Unsupported or ambiguous files fail
qualification rather than silently disappearing. Report each omission and
its reason; never claim the source projection is a whole-repository snapshot.

Only Git-tracked symlinks inside protected test roots may be represented as
opaque immutable fixtures. Verify lstat mode, literal readlink bytes and Git
blob identity without following the link. Reject absolute/escaping targets,
implementation links, special files and unknown modes. A link's presence in a
test directory is necessary, not by itself sufficient, for acceptance.

The base tree must equal the disjoint union of verified projected source and
the frozen runtime manifest. Neither missing nor extra tracked paths qualify.
Before and after candidate assembly, verify all runtime fixtures unchanged.
Candidates cannot modify, replace, delete or introduce omitted paths, and
cannot alter protected tests. Runtime fixtures must survive source assembly;
they are not treated as the existing untracked `.eggs` cache exception.

Gold/reference changes requiring unsupported paths remain unqualified. Keep
network-disabled grading, all declared target/regression checks, skip handling
and strict parent-fail/reference-pass rules unchanged. Do not use score or
token outcomes to select omissions or tasks.

## Lossless bounded result transport

Repeated original/candidate source maps can exceed the unchanged 8,000,000-byte
controller output cap even when each source snapshot is valid. New controls
may explicitly wrap their single JSON result in a versioned zlib/base64
envelope with exact uncompressed length and SHA-256. Limit decoded JSON to
128,000,000 bytes and the complete encoded envelope to 8,000,000 bytes. Decode
with a bounded decompressor; reject non-finite JSON, duplicate keys, malformed
base64, trailing/concatenated compression streams, oversized expansion,
length/hash mismatch and unknown envelope versions. Never truncate, fabricate
or discard result fields. Old transport/profile behavior remains unchanged.

Retain envelope bytes and verified decoded result identity in protected
evidence. Compression is transport only: it cannot change grading or make a
previous incomplete record complete retroactively.

## Required controls and handoff

Test positive binary/link fixtures plus tampering, scope escapes, missing or
extra members, overlap, source-limit violations, special files and race checks.
Test transport round-trip above the old raw-response limit and every malformed
envelope class. Run installed Windows controls against actual pinned image
trees, preserving the old controls under their old run IDs. Freeze projection,
manifest, bootstrap and codec hashes before any solver receives their output.

Apply one declared qualification policy to the original forty-candidate pool.
Do not shrink/expand the eligibility pool or substitute repositories. The owner
subsequently authorized three PyVista model tasks, keeping four in each other
repository (nineteen total); see windows-confirmation-v2.md. Fewer than the
amended quota still means confirmation is incomplete. Registry or
network-dependent test failures are not fixed by this projection; any derived
image construction needs its own explicit provenance protocol before use.

## Registry representation correction

The original registry verifier accepted only a single Docker schema-v2 object.
Some retained verbose responses instead contain a list with one native OCI
image and an unknown-platform attestation. Reinterpret all forty original
responses using a separately tested verifier before making any further image
requests: require exactly one linux/amd64 descriptor, verify its raw-manifest
length/SHA-256, decoded representation, configuration digest and all layer
identities. Reject ambiguous/no-native lists. Pin the selected child digest,
not a mutable tag or attestation. Preserve the complete original response and
all original failures; this is a parser correction, not task replacement or
permission to choose another environment. Reuse the thirty exact existing
runtime proofs after digest equality checks; execute the same guarded native
runtime check only for newly resolved original candidates. No derived image
construction is needed if those original image bytes qualify.

## Explicit lossless response repair before inference

PyVista-4853 passed parent/reference tests but both source-assembly workers
failed while emitting their complete results: `encoded result budget exceeded`.
The failure is reporting, not a grade. Preserve the original receipts.

An explicit `lzma-v2` response envelope may encode the identical full JSON
using XZ/LZMA preset 7, with the same 8,000,000-byte wire limit, 128,000,000-byte
decoded limit, exact length/SHA-256 and strict JSON validation. Decoder memory
is capped at 128,000,000 bytes; incomplete, trailing, concatenated, oversized,
unknown-version and digest-mismatched streams are rejected. Legacy zlib remains
the default. No source, context, test, grade, timeout or network cap changes.

Verify the new worker program differs only in the embedded codec and print
sink. Reuse all four complete successful phase records for 4311/4329. Only the
two proved emission failures for 4853 may execute again, under a new explicit
run ID; no known negative grade or solver attempt is retried. If the new result
still does not fit or fails any gate, retain that failure rather than truncating.
