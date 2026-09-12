# Implementation Plan: Encrypted Evidence and Privileged Access

**Date**: 2026-09-13
**Status**: Initial vertical slice implemented; convergence and release gates remain open
**Specification**: [spec.md](spec.md)

## Technical context

Python 3.10–3.13, SQLite, `cryptography` AES-256-GCM, optional `pqcrypto` 1.x
ML-KEM-768/ML-DSA-65, the existing application service and loopback HTTP API,
and the OpenClaw TypeScript bridge. No model dependency is introduced.

The existing control database is a legacy content-minimizing index and remains
readable. New exact evidence is written to a separate encrypted vault whose
SQLite rows contain only opaque object identifiers, ordering fields, nonces and
ciphertext. The vault key is supplied outside the vault through a restrictive
local key reference for the development profile; production key sources remain
an explicit capability boundary. Exact data is never copied into the legacy
`evidence.body_json` column.

## Design decisions

1. **Capture modes**: `full` is the default and retains encrypted data plus
   metadata. `metadata` is the state produced when the compact Data switch is
   off; it retains encrypted structural metadata and marks the run
   `not_reconstructable`. `off` disables the recorder and stores nothing.
2. **One encrypted object boundary**: Event identity, scope, timestamps,
   content, multimodal parts and access audit are serialized canonically and
   encrypted together with AES-256-GCM. Associated data contains only the
   container version and opaque object ID.
3. **Privileges**: `viewer`, `investigator` and `evidence_collector` are exact,
   ordered evidence roles. Viewer can inspect in AtMem. Investigator can inspect,
   reconstruct and produce recipient-encrypted bundles. Only Evidence Collector
   can produce plaintext export, after an explicit confirmation token. Evidence
   submission is a separate capability and never grants read access.
4. **Test identities**: An explicit development-only command creates random-token
   `atmem-viewer`, `atmem-investigator` and `atmem-evidence-collector` credentials.
   It is never created automatically, is labelled non-production and stores only
   encrypted account records and one-way token verifiers.
5. **Post-quantum export**: Recipient-encrypted bundles use ML-KEM-768 to derive
   an AES wrapping key and ML-DSA-65 for the canonical manifest. If the optional
   provider is unavailable, encrypted export fails closed and does not advertise
   quantum-resistant protection.
6. **Host capture**: OpenClaw sends exact prompt/system/history/context/model/tool
   values in a reserved full-fidelity field while retaining legacy digests for
   compatibility. Its durable spool uses AES-256-GCM so the reserved content is
   never persisted as plaintext. Inbound text/image/audio/video/file artifacts
   use ordered typed parts and bounded exact bytes.
7. **Application-only plaintext**: Decryption lives in `atmem.evidence.service`.
   Dashboard, HTTP, CLI and MCP consume authorized service projections; adapters
   receive append-only capture operations and no key/decrypt API.
8. **Envelope keys**: Each run or independently deletable partition receives a
   random AES-256 data key. The vault contains only an opaque key-slot identifier
   and AES-GCM-wrapped data key; the active wrapping key remains outside the vault.
   Rotation rewraps slots transactionally and retains no plaintext intermediate.
9. **Locked behavior**: A missing external key beside an existing vault is a locked
   store, never a request to generate a replacement. Status remains available but
   capture, search, reconstruction and export fail before evidence decryption.
10. **Legacy migration**: Existing content-minimizing tables are inventoried and
   reported honestly. The protected source slice does not claim product-wide
   metadata secrecy until an atomic encrypted-control-store migration and verified
   plaintext cleanup exist; that migration is a separate release-blocking task.
11. **Exports**: Plaintext export is an iterator/stream owned by the application
   boundary. CLI output writes directly to its final mode-0600 destination and
   removes a partial destination on failure. HTTP/MCP profiles must not advertise
   streaming until their transport implements it.

## Architecture and file ownership

- `atmem/evidence/models.py`: capture modes, roles, scope and operation matrix.
- `atmem/evidence/crypto.py`: AES-GCM sealed objects, external key reference and
  optional ML-KEM/ML-DSA primitives, wrapped data keys and key rotation.
- `atmem/evidence/store.py`: opaque encrypted SQLite vault and encrypted audit.
- `atmem/evidence/service.py`: authorization-before-decryption, capture,
  reconstruction and export.
- `atmem/control/manager.py`: dual-write exact evidence to the vault and legacy
  digest projections without plaintext leakage.
- `atmem/service/application.py`, `atmem/control/web.py`, `atmem/control/server.py`
  and `atmem/cli.py`: authorized application surfaces and demo identities.
- `integrations/openclaw/index.ts` and `src/execution-spool.ts`: exact host values,
  multimodal bytes and encrypted spool.
- `atmem/control/assets/app.js` and `app.css`: one compact Evidence protection row
  and focused drawer consuming a server view model.
- `tests/test_evidence_protection.py`, `tests/test_http_api.py` and OpenClaw hook/
  spool tests: role matrix, stolen-store scan, defaults, degraded modes, exports
  and compatibility.

## Delivery sequence

1. Freeze role, capture-mode, encrypted-object and API contracts.
2. Implement crypto and vault storage, then authorization and access auditing.
3. Integrate manager and application surfaces before host full-content capture.
4. Encrypt the host spool and add exact text/tool/multimodal producer fields.
5. Add the compact UI and three explicit demo identities.
6. Add key lifecycle, complete role operations and streaming export.
7. Add legacy inventory/migration state and encrypted disaster recovery.
8. Run unit, HTTP, CLI, OpenClaw build/typecheck/hooks, planted-secret scans and
   consumer-hardware capacity measurements.

## Compatibility and migration

Existing hash-only rows are unchanged and labelled legacy. New runs can carry a
legacy projection plus an encrypted exact object linked by opaque ID. Upgrade
does not invent absent historical content. Storizon HMAC/Ed25519 request/result
contracts are untouched; their exact bytes can be captured inside the encrypted
object. An unsupported or missing key produces `encrypted_locked`, never a
plaintext fallback.

Until the legacy encrypted-control migration switches and verifies cleanup, status
must report `plaintext_source_exists`; this preview may demonstrate a protected
new-write boundary but cannot advertise complete metadata-at-rest protection.

## Verification strategy

Tests plant unique prompt, URL, tool argument/result/error, filename, image,
audio and video byte signatures. Raw SQLite, WAL, spool and settings scans must
find none of them. Authorized reads must reproduce them byte-for-byte. The same
fixture is exercised as each of the three roles plus submitter and unaffiliated
principal. Viewer and Investigator plaintext export must fail; Evidence
Collector export must fail without confirmation and succeed with it. Metadata
mode must retain no planted content and report `not_reconstructable`; recorder
off must add no object.
