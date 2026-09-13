# Feature Specification: Portable Multimodal AtMem Home

**Feature directory**: `specs/030-portable-multimodal-atmem-home`
**Created**: 2026-09-13
**Status**: Implemented and verified for AtMem 2.3.0
**Input**: Make AtMem a clean, independent and portable evidence/memory home. A
user can copy one AtMem folder to another computer, start AtMem against it, sign
in, recover the original database and exact multimodal evidence, then optionally
adopt it as the writable home. No original agent, OpenClaw folder or host logs may
be required.

## Overview

AtMem currently keeps product state beneath `~/.atmem` by convention, but its
layout is fragmented across root files, migration-specific databases, adjacent key
directories, transient bridge bindings and host-owned media references. In the
observed OpenClaw failure, the model received an image stored under
`~/.openclaw/media/inbound`, while AtMem retained only an empty attachment binding.
Copying `~/.atmem` would therefore not reproduce what the agent saw.

This feature introduces one versioned **AtMem Home**. Every durable AtMem-owned
database, encryption key, identity record, audit chain, exact captured artifact,
configuration snapshot and recovery manifest lives under that root. Runtime caches,
locks and logs may also live there but are explicitly disposable. External agents
remain host-owned; AtMem copies exact boundary content into its encrypted,
content-addressed artifact vault before acknowledging capture.

Portable restore mode is distinct from schema migration:

- **Restore/open** validates and opens a copied home without modifying original
  evidence. The user signs in with an Administrator account from that home.
- **Adopt** rebinds machine-local runtime paths and makes the copied home writable
  after authenticated confirmation. It never rewrites historical evidence.
- **Migration mode** transactionally changes an older AtMem layout/schema through
  discover, preflight, copy, verify and commit phases. It records an append-only
  journal, remains restartable, preserves the source, and permits rollback of the
  uncommitted destination generation.
- **Host reconnect** is optional and happens only after standalone recovery works.

## Canonical home layout

```text
<atmem-home>/
  manifest.json               public, content-free layout/inventory metadata
  config/                     portable AtMem configuration and path bindings
  identity/                   encrypted users, sessions and identity keys
  memory/                     canonical memory databases
  evidence/                   encrypted event databases and audit material
  artifacts/sha256/           encrypted exact image/audio/video/file/page blobs
  indexes/                    disposable rebuildable search/vector indexes
  migrations/                 journals and append-only migration receipts
  runtime/                    disposable locks, spools and logs
  backups/                    user-requested AtMem-owned backups
```

Internal durable references are relative to the home or content-addressed. Absolute
paths are historical source metadata only and never required for recovery.

## User scenarios and acceptance

### US1 — Capture exact multimodal input (P1)

A user sends an image, audio clip, video or file through an agent. AtMem records
the textual request and a separate ordered artifact part containing the exact bytes,
MIME type, digest, source adapter, session, run and timing.

**Acceptance**: Capture succeeds for OpenClaw's current `event.media`, persisted
`__openclaw.media[].url = media://inbound/<id>` and staging contracts, plus supported
legacy aliases. A later sparse transcript hook cannot erase
the binding. AtMem does not acknowledge the attachment event until the encrypted
artifact blob and referencing evidence event are durable. The dashboard renders the
original artifact rather than `[User sent media without caption]` alone.

### US2 — Copy and open on another computer (P1)

The owner stops or snapshots AtMem, copies the one AtMem Home to another computer,
installs a compatible AtMem version and runs `atmem restore <copied-home>`.

**Acceptance**: AtMem performs a content-free preflight, opens a loopback dashboard
in read-only restore mode and asks for a local account from the copied home. Before
login it reveals no usernames or evidence. After Administrator login it verifies
the inventory, decrypts the stores and reconstructs sessions, memories, tool calls,
decisions and exact multimodal artifacts without the source agent, source home path,
network, OpenClaw or its media folder.

### US3 — Adopt a restored home (P1)

After inspection, the Administrator chooses **Use this as my AtMem Home**.

**Acceptance**: AtMem confirms the destination and source instance, verifies no
other writer owns the home, writes new machine-local runtime bindings, rotates
sessions and creates an adoption receipt. Historical event IDs, hashes, timestamps,
subjects, users, memories and artifact bytes remain unchanged. Rebuildable indexes
are recreated. Host reconnect is a separate optional step.

### US4 — Migrate the old layout safely (P1)

An existing 2.3 prerelease installation starts with root files and migration-scoped
stores. AtMem offers a guided migration into the canonical layout.

**Acceptance**: Migration inventories source files, checks free space, copies and
verifies before switching, uses a durable journal, is restartable and leaves the
old layout untouched until commit. Failure resumes or rolls back. A successful
receipt maps every old path to a new relative path and proves database/artifact
hashes or logical SQLite equivalence as appropriate.

### US5 — Understand memory versus black-box evidence (P1)

An uploaded image is always retained as exact evidence when full capture is on. It
becomes searchable agent memory only when the user asks to remember it or approves
the derived observation.

**Acceptance**: The UI shows **Captured evidence** immediately and separately shows
**Memory status: not requested / awaiting approval / approved / rejected**. It never
implies that a placeholder string is the image or that capture automatically grants
memory injection.

## Functional requirements

- **FR-001**: Resolve every durable AtMem path from one explicit home root. Default
  to `~/.atmem`; support `--home` and `ATMEM_HOME`. Precedence is CLI, environment,
  default. Reject symlink escapes and durable paths outside the selected home.
- **FR-002**: Create `manifest.json` with layout version, AtMem compatibility range,
  stable instance ID, creation/update time, capture mode, and content-free inventory
  entries. It MUST contain no usernames, prompts, tool arguments, URLs, filenames,
  MIME-derived private labels, encryption secrets or plaintext evidence.
- **FR-003**: Store all durable account, memory, evidence, audit, configuration,
  key, artifact and migration state in the canonical layout. Store only disposable
  locks, caches, generated indexes, sessions and service logs under `runtime/` or
  `indexes/`; their deletion cannot prevent evidence recovery.
- **FR-004**: On full capture, copy each agent-bound image/audio/video/file/page into
  `artifacts/sha256/<prefix>/<digest>.blob` using authenticated encryption before
  acknowledging its evidence event. Deduplicate by plaintext SHA-256 without
  exposing plaintext bytes or private metadata in filenames or the manifest.
- **FR-005**: Bind every artifact transactionally to ordered evidence containing
  modality, MIME type, byte count, plaintext digest, ciphertext integrity data,
  host adapter, run/session/turn and source timing. Failure to store bytes records a
  visible capture failure and MUST NOT claim exact artifact capture.
- **FR-006**: OpenClaw capture MUST consume current `event.media`, safe locally
  usable `originalMedia` paths, exact managed `media://inbound/<id>` transcript
  references, staging state and beta legacy aliases. It MUST NOT
  infer the newest file by scanning a host directory. Sparse later hooks cannot
  erase a valid same-turn binding; text-only new turns cannot reuse an old binding.
- **FR-007**: A copied home opens in read-only restore mode first. Pre-authentication
  operations are limited to structural validation, compatibility and corruption
  status. Decryption, reconstruction, export, upgrade commit and adoption require an
  authenticated Administrator from that copied home.
- **FR-008**: `atmem restore <home>` starts/opens the loopback dashboard against that
  exact home. It does not copy into or overwrite the default home. A missing
  manifest invokes guided legacy discovery; ambiguous candidates stop with a clear
  choice rather than guessing.
- **FR-009**: Adoption requires a simple confirmation showing source and destination,
  rejects an active writer, rotates sessions, writes only machine-local bindings and
  an adoption receipt, and never mutates historical evidence content or hashes.
- **FR-010**: Schema/layout upgrade uses an fsync-backed journal with discover,
  preflight, copy, verify, switch and commit phases. Every phase is idempotent.
  Interruption at every boundary resumes safely; rollback remains possible until
  commit and never deletes the source automatically.
- **FR-011**: All durable internal references use home-relative paths, stable logical
  IDs or content digests. Absolute source-machine paths may remain encrypted as
  historical evidence but are never dereferenced during restore.
- **FR-012**: Rebuild derived search/vector indexes on the target from canonical
  encrypted/decrypted application records after authorization. Index absence,
  platform mismatch or corruption cannot block exact evidence browsing.
- **FR-013**: Standalone recovery MUST work with the copied home and installed AtMem
  package only. Tests remove the source agent, OpenClaw, host media, logs, caches,
  original absolute paths and network access before reconstruction.
- **FR-014**: Keep black-box evidence and memory lifecycle distinct. Full capture
  records exact media automatically; recallable memory requires explicit user intent
  or approval and remains governed by scope, lifecycle and revocation.
- **FR-015**: Provide compact UI states for Home health, Restore read-only, migration
  progress, adoption and artifact/memory status. Viewer remains content-free and
  sees only metadata, hashes and integrity. Investigator and higher roles render
  images and play audio/video inline. A per-artifact plaintext download is
  shown only to Evidence Collector and Administrator roles. Every run summary MUST
  describe the complete observed input modalities and MUST NOT present a text
  caption as though it were the entire request when media was also attached. Do not
  expose internal path sprawl or require users to manually move individual databases
  or keys.
- **FR-016**: Provide `atmem home status`, `atmem home verify`, `atmem restore`,
  `atmem home adopt` and `atmem home migrate` with JSON forms. Passwords remain UI
  or non-echoing input; commands never accept password arguments.
- **FR-017**: Copy/snapshot guidance MUST require quiescence or use an AtMem-created
  consistent snapshot. A live raw copy is detected as unclean and opened only for
  recovery diagnostics until integrity succeeds.
- **FR-018**: Preserve Spec 028 encryption, authorization-before-decryption and
  plaintext-export rules. Copying a home does not make its data visible without an
  AtMem authenticated role; only Administrator may restore/adopt/upgrade.
- **FR-019**: Existing delegated providers, Pydantic AI and LangChain/LangGraph
  adapters resolve the same selected AtMem Home without changing their wire JSON.
  Provider-owned stores remain external; exact content that crosses into an AtMem
  flight is captured into the portable evidence vault according to capture mode.
- **FR-020**: Never claim an external action occurred based only on agent events.
  Portability preserves AtMem's observed-session boundary and evidence qualifiers.

## Success criteria

- **SC-001**: A fixture captures text, URL/fetched page, file, image, audio and video;
  after copying only the AtMem Home and deleting every source dependency, the target
  reproduces all ordered parts byte-for-byte and verifies every evidence chain.
- **SC-002**: The OpenClaw regression matching Event 943 produces a durable image
  artifact and rendered `turn.attachment` event when current media facts are present,
  even when the later transcript message is sparse.
- **SC-003**: Raw scans of the copied home reveal none of ten planted prompts,
  usernames, URLs, filenames, tool arguments, image signatures, audio signatures or
  video signatures; authorized restore reproduces all ten exactly.
- **SC-004**: Kill tests at every migration phase resume or roll back with no missing,
  duplicated or partially switched canonical record.
- **SC-005**: Copying a multi-chunk home adds no duplicate artifact for an already
  known digest, and target verification reads at most 1 MiB per chunk rather than
  loading the home into RAM. Physical 10 GiB allocation is not a release gate.
- **SC-006**: Viewer/Investigator/Evidence Collector retain their defined evidence
  permissions after restore; only Administrator can adopt or upgrade.
- **SC-007**: A new user can recover a copied home through one CLI command, login and
  one adoption confirmation without editing JSON, moving keys or locating databases.
- **SC-008**: Existing OpenClaw delegated-context, Pydantic AI and LangGraph contract
  tests remain unchanged and pass against a non-default selected home.

## Edge cases

- Copy is incomplete, still changing, read-only or on a case-insensitive filesystem.
- Destination already contains another AtMem instance.
- Source and clone run concurrently with the same instance ID.
- Artifact ciphertext exists without a committed reference, or reference exists
  without ciphertext.
- Encryption key is missing, locked or corrupted.
- Copied home comes from a newer incompatible AtMem layout.
- Original absolute paths contain secrets or no longer exist.
- Same exact media arrived from multiple agents or under different filenames.
- Restore succeeds but an optional host reconnect fails.

## Out of scope

Concurrent multi-primary replication, cloud synchronization, automatic conflict
merging, remote account recovery, cross-tenant export and claiming that host-side or
external actions occurred beyond what AtMem observed.

## Invariant attestation

Touches INV-006 human-readable provenance/history, INV-008 honest Agent Black Box
boundaries and INV-010 local operation. Required destructive acceptance removes the
agent, host media, logs, caches and network, then restores from only the copied AtMem
Home. Hash-only, placeholder-only or external-path-dependent results fail.
