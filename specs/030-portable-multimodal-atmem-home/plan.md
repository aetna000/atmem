# Implementation Plan: Portable Multimodal AtMem Home

**Date**: 2026-09-13
**Status**: Implemented and verified for AtMem 2.3.0
**Specification**: [spec.md](spec.md)

## Summary

Introduce a single versioned AtMem Home resolver, encrypted content-addressed
artifact vault, portable manifest, standalone verification/restore CLI and an
authenticated adopt/migration workflow. Fix the OpenClaw media boundary so both
host attachment facts and the exact multimodal model input are durably captured.
Keep black-box capture independent from the separately governed memory lifecycle.

## Technical context

- Python 3.10–3.13, SQLite, the existing AES-256-GCM protected-evidence container,
  `hashlib`, `pathlib`, atomic replace and fsync; no new mandatory network service.
- TypeScript OpenClaw bridge targeting the recorded 2026.7–2026.9 hook contracts.
- Existing installations keep working. Canonical layout conversion is opt-in and
  copy-first; no command deletes the legacy source.
- `ATMEM_HOME` becomes the shared process-level root. Explicit CLI `--home` wins,
  then the environment, then `~/.atmem`.

## Constitution check

| Principle | Result | Gate |
| --- | --- | --- |
| Authority before intelligence | Pass | Artifacts are evidence, not automatically admitted memory. |
| Full-fidelity evidence and replay | Pass | Exact ordered bytes survive deletion of the host and agent. |
| Safe defaults and reversibility | Pass | Restore is read-only; migration is copy/verify/commit and keeps its source. |
| Scoped transparency | Pass | Authentication and role authorization precede decryption or export. |
| Host neutrality | Pass | Home and artifact contracts are core; OpenClaw handling stays in its adapter. |
| Executable claims | Pass | Dead-agent copy, tamper, role and exact-byte tests are required. |
| Local-first | Pass | Restore and inspection work offline with only AtMem and the copied home. |

## Architecture

### Home authority

Add `atmem/home/` with a pure resolver and a service layer. `HomeLayout` owns every
canonical relative path and rejects escapes. `HomeManifest` is content-free and
contains a layout version, instance ID, compatibility bounds, capture profile and
inventory counts/digests only. `HomeService` initializes, inventories, verifies,
snapshots, opens, adopts and migrates homes.

Existing constructors continue accepting explicit paths. CLI/application entry
points resolve defaults from `HomeLayout`, allowing compatibility while persistent
components move behind one root. New installs create the full canonical directory
tree. No module may place a new durable file beside the selected home.

### Exact encrypted artifact vault

Add an artifact vault beneath `artifacts/sha256/`. Plaintext SHA-256 provides the
stable content address; the file contains a versioned AES-256-GCM envelope with a
random nonce, authenticated header and ciphertext. MIME type, filenames and source
paths remain inside protected evidence, not filenames or the public manifest.

Artifact writes stream/hash to a private runtime spool, encrypt to a same-directory
temporary file, fsync, atomically publish, then commit the referencing evidence
event. Duplicate plaintext digests reuse the verified blob. Reads require an
authenticated application principal and verify both AEAD and plaintext digest.
The protected evidence event retains ordered part metadata and the relative artifact
reference; inline base64 remains readable for legacy events.

### Capture boundaries

The OpenClaw adapter captures two independently labelled representations when
available:

1. host attachment bytes from current `event.media`, safe local `originalMedia`
   facts and supported legacy aliases; and
2. exact image/audio/video/file content present in `llm_input`, proving what was
   delivered to the model even if the host original is unavailable or transformed.

Managed-path validation remains mandatory for host paths. No directory recency scan
is allowed. A sparse later hook cannot replace a non-empty turn binding. Attachment
capture automatically creates black-box evidence in full mode; `atmem_observe`
still controls whether derived content enters searchable memory.

### Restore, adoption and migration state machines

`atmem restore HOME` performs structural and compatibility preflight without opening
encrypted content, starts the dashboard against that exact home in read-only restore
mode and requires an account stored in the copied home. After Administrator login,
normal AtMem authorization unlocks reconstruction.

Adoption is a distinct authenticated transition:

`restored_read_only -> verified -> administrator_confirmed -> sessions_rotated -> adopted`

Only runtime bindings and an append-only adoption receipt change. Historical
evidence and artifact bytes do not.

Legacy migration mode is a restartable journal:

`discover -> preflight -> copy -> verify -> switch -> commit`

Each completed phase is fsynced and idempotent. The source remains untouched. A
failed or killed process resumes from the journal, while `rollback` removes only an
uncommitted destination generation. Migration and restore are deliberately separate:
restore proves the copied home is usable; migration changes a layout or schema.

## Contracts

- `manifest.json`: `atmem-home-manifest-v1`, layout version, instance ID,
  compatibility range, timestamps, capture mode and content-free inventory.
- Artifact blob: `ATMEMART1` magic plus canonical authenticated header, nonce and
  AES-GCM ciphertext. Evidence references use `artifacts/sha256/aa/<digest>.blob`.
- Migration journal: `atmem-home-migration-v1`, source/destination instance IDs,
  phase, source inventory, verified mappings and commit receipt.
- Runtime state: selected home, restore/read-only/adopted status and writer lease;
  disposable and excluded from historical evidence.

## Files

- `atmem/home/{layout,manifest,artifacts,migration,service}.py`: root resolution,
  encrypted blobs, verification and state machines.
- `atmem/evidence/service.py`, `store.py`: externalized artifact references,
  authorized materialization and standalone reconstruction.
- `atmem/cli.py`, `atmem/dashboard_daemon.py`, `atmem/control/web.py`: `--home`,
  home commands, restore server state and Administrator-only adoption/migration.
- Dashboard assets: captured-artifact rendering, Home health and compact restore
  controls with memory status kept distinct.
- `integrations/openclaw/index.ts`, `src/types.ts`: current/original/staged media and
  exact model-input part capture.
- `tests/test_home.py`, evidence/HTTP/dashboard tests and OpenClaw hook tests.

## Verification strategy

1. Unit-test path precedence, symlink/relative escapes, manifest secrecy, encrypted
   artifact deduplication, AEAD/digest tamper rejection and bounded reads.
2. Run exact Event 943 adapter tests for `media`, `originalMedia`, staging, sparse
   writes, text-only turns and model-input media.
3. Capture text, page, file, image, audio and video; snapshot/copy the home, delete
   agent/log/media/workspace/network fixtures, then authenticate and compare bytes.
4. Exercise Viewer, Investigator, Evidence Collector and Administrator after restore;
   only Administrator can adopt/migrate and only authorized export emits plaintext.
5. Kill migration at every phase, resume/rollback, verify source preservation and
   unchanged historical identities/hashes.
6. Run existing evidence, identity, dashboard, CLI, OpenClaw, delegated provider,
   Pydantic AI and LangGraph suites plus installed-wheel/packed-bridge gates.

## Rollout and compatibility

New homes are canonical immediately. Existing 2.3 prerelease layouts are discovered
but never rearranged on startup. The UI/CLI offers `atmem home migrate`; users may
continue in compatibility mode until they opt in. A missing manifest on `restore`
starts guided discovery, not an inferred destructive conversion. Wire request/result
contracts and delegated HMAC/Ed25519 profiles remain unchanged.

## Honest limitations

This is portable single-writer local storage, not synchronization or multi-primary
replication. A copied home requires its copied key material and a valid local account;
lost keys cannot be reconstructed. Post-quantum algorithms protect supported export
and key-exchange/signature profiles, while at-rest bulk encryption remains the
explicit AES-256-GCM profile and is not described as a post-quantum bulk cipher.
