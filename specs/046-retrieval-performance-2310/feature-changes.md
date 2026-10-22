# User-visible feature change register

2026-10-21: **No existing feature removed or disabled; existing defaults remain
unchanged.** No release version or user installation was changed. Development
source and isolated benchmark stores have changed as described below.

- Added opt-in experimental semantic engines and a trusted Python engine
  parameter through the existing governed V3 boundary. No existing profile
  selects these engines. No model-generated sufficiency or authority override.
- Added optional Ollama truncation control; omitted control retains the existing
  request behavior. The experiment explicitly rejects oversized embedding input.
- Added a subscription transport retry bound, preserving the previous default.
  Development reader runs select one transport attempt and no paid fallback.
- Added optional semantic metadata to the scoped Hermes checkpoint and authorized
  export. Semantic stores use explicit V2 identities; stores without that metadata
  retain the existing V1 bytes/behavior. Tests detect metadata tampering and an
  incomplete schema. Earlier experiment checkpoints remain preserved and are not
  silently upgraded. Migration/deletion and cross-platform qualification remain
  outstanding. The exact-vector diagnostic
  scans derived vectors and does **not** satisfy FR-003's production no-scan rule.
  Neither prototype is accepted for promotion or release.
- No additional Torch/CUDA dependency or default provider/model download.

- Added an opt-in in-process investigative discovery session and read-only MCP
  exposure. Independent semantic/lexical nominations precede evidence inspection;
  renewed authorization and canonical reload remain mandatory. Results explicitly
  do not claim sufficiency. Shared operation/time/serialized-response byte bounds
  and mandatory application audit are tested. An explicitly selected Hermes
  workflow can now provision encrypted administrator-issued discovery leases and
  expose separate stdio MCP tools over authenticated loopback RPC. Reservations
  persist across restarts. Existing defaults remain unchanged; release/install
  qualification is still outstanding. Semantic uncertainty may start investigation,
  never policy denial or stale authority. Optional fixed application-completion
  guidance does not remove native tools or alter memory data; its effect must be
  measured separately from retrieval improvements.
- Added an explicit, default-off MCP root-argument guard. Undeclared parameters
  are rejected before execution unless the tool explicitly permits arbitrary
  properties. It preserves the underlying app, values and grading evidence.
  This is a stricter host contract, not a rewrite of JSON Schema defaults.
- Added an optional source-state assessment contract in AtBot and a separate
  AtMem quote/identifier validator. Activation is explicit; remote egress requires
  an administrator-created permission and named provider. It labels source quotes
  without generating memory facts or authorizing actions. Existing defaults and
  package versions are unchanged. Read-only source-state proposals are not a
  replacement for canonical temporal formation or complete release qualification.
- Added separately selectable, default-off computed date-interval frames. These
  preserve original quoted ranges and establish only their arithmetic relation
  to the question's explicit date. They do not establish source truth, inclusive
  boundary rules, acceptance or authority. Unsupported forms stay unparsed.
  No hosted call or mutation is introduced by this option; task-quality and
  cross-platform installation qualification remain separate outstanding gates.
- Source-bundle presentation is a new default-off experiment: authorized ranges
  from the same original part stay together, in source order, within the same
  read budget. No generated summaries, invented speaker identities or source
  rewriting. Oversized groups are visibly omitted rather than partially packed.
  Existing fragment presentation and deterministic defaults remain available.
- New reference-host benchmark conditions use the official shared identity
  template and public user-name registry, with pre-forwarding model-input checks.
  This repairs fresh benchmark profile setup; it does not add answer facts or
  alter canonical memory. Normal user profiles and existing SOUL files are not
  changed. Historical conditions keep their original host configuration/results.

Grader qualification correction: the first six-control suite incorrectly treated
two published answer keys as verified positives. Its failed result and USD
0.767767 charge are retained. Three explicit original utterances now ground six
separate calibration probes. All six passed before any scored reader grading.
These probes are not training examples or claimed benchmark performance. The
original 30 scored questions, 90 predictions, strict rubric and denominator are
unchanged; bad reference findings remain visible and count as non-passes.

Before any future removal/default change record: feature and affected users;
owning spec/contracts; alternatives considered; expected performance mechanism;
user notification reference; migration/rollback; matched measured benefit and
regression evidence. Constitutional safeguards cannot be removed for score gains.

Additional opt-in presentation experiments: initial source-state annotation and
source dossiers are separately named profiles, not changed defaults or released
features. The dossier replaces only the initial presentation with original quoted
evidence and model-proposed information needs; complete original records remain
retained and inspectable. Rollback selects the original source-state or deterministic
profile. No data migration, pruning, canonical-state mutation or new action authority
is introduced. Quality, total token use and latency are measured before promotion;
added labels or a smaller first packet are not themselves accepted improvements.

Source-local SQL correction (T045): source neighbor and query-head lookups now
seek the nominated source before joining generation members, using the existing
source/range indexes. This changes access order, not selected evidence, ordering,
ranking, lifecycle, authority, timeout, schema or profile defaults. Differential
row and bounded SQL-work fixtures qualify the correction; installed task-quality
and systems measurements remain separate. No feature is removed, no migration
is required, and no release has been published from this research artifact.

Release qualification correction: optional source-part caches now register with
canonical lifecycle ownership. Source/generation deletion and subject reset
verify their derived-row cleanup; stale generation handles cannot serve vectors.
Unverifiable missing caches stop verified deletion. Known older research caches
are adopted only when explicitly reopened; unknown paths cannot be discovered.

Windows integration qualification: generated Python MCP fixtures now use native
console launchers rather than POSIX shebang execution. The origin-metadata-absent
OpenClaw local-operator exception explicitly refuses Windows, whose POSIX mode
bits cannot prove ACL isolation. Standard authenticated-owner operation remains
supported; no ordinary memory/Code feature or default was removed. This is not a
performance optimization or a change to retained historical benchmark results.
