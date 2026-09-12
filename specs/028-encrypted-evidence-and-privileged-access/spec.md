# Feature Specification: Encrypted Evidence and Privileged Access

**Product-wide requirements**: [Agent neutrality and standalone full-fidelity evidence](../product-requirements.md) (PR-001–PR-008). Applies to every evidence-bearing storage, backup, export and interface boundary.

**Feature directory**: `specs/028-encrypted-evidence-and-privileged-access`
**Created**: 2026-09-13
**Status**: Partial source implementation; release gates remain open
**Input**: Protect all AtMem evidence and metadata with application-mediated, quantum-resistant encryption and a concise privilege hierarchy.

## Overview

AtMem is the independent evidence authority, so its store contains exact prompts,
memory/context, decisions, model exchanges, tool calls/results and original
multimodal artifacts. Those bytes must remain unintelligible when somebody opens,
copies or steals the database, artifact directory, spool, backup or export without
the authorized AtMem application and its key authority.

Encryption protects retained evidence; it does not reduce transparency for an
authorized user. The AtMem application is the only supported plaintext boundary.
Its first-party dashboard, CLI, API and MCP surfaces may display or export exact
plaintext only after AtMem authenticates the principal, authorizes the scope and
operation, unlocks the required key, and records the access event.

Product moment: **At capture, investigation, export and deletion**. Spec 020 owns
the evidence envelope/artifact model, Spec 021 owns reconstruction, Spec 022 owns
the shared interface, and this feature owns encryption, privilege and key-release
policy. Existing provider protocols, including Spec 003 HMAC and Ed25519 contracts,
remain byte-compatible and are retained as encrypted evidence; they are not
misrepresented as post-quantum algorithms.

## User scenarios and acceptance

### US1 — A stolen evidence store reveals no session data (P1)

An attacker obtains the SQLite files, artifact objects, indexes, spools, temporary
files, backups and encrypted exports but not the AtMem application key authority.

**Independent test**: Capture a multimodal run, shut down AtMem, copy every storage
object and scan it using SQLite, archive, strings, media and file-carving tools.
Search for planted prompts, names, URLs, tool arguments, results, captions,
transcripts, MIME types and filenames.

**Acceptance**: Zero planted content or semantic metadata is recovered. Only the
minimal cryptographic bootstrap header and unavoidable physical filesystem facts
described by FR-006 are visible.

### US2 — Privilege determines what an authenticated user can do (P1)

An organization grants people increasing evidence privileges without giving the
agent, evidence producer or key custodian automatic read access.

**Independent test**: Exercise the same run as a submitter, Level 1 viewer, Level 2
investigator, Level 3 Evidence Collector, unrelated principal and key custodian.
Attempt view, search, reveal, reconstruction, encrypted export, plaintext export,
replay-manifest creation, grant, rotation, retention change and deletion.

**Acceptance**: Every operation matches the privilege matrix, cross-scope access
fails before decryption, and success or denial creates an encrypted audit event.

### US3 — An owner manages encryption without a giant settings panel (P1)

An owner sees one concise Evidence protection row showing protection state, key
source, lock state and last rotation, then opens a focused drawer only when action
is needed.

**Independent test**: At 375px and 1280px, use keyboard and pointer journeys to
inspect protection, lock/unlock, select an available key source, rotate, test
recovery and set plaintext-export policy.

**Acceptance**: Status is understandable from the collapsed row; each common
operation takes at most two actions; advanced algorithm/recipient details remain
collapsed; no page-size form is required for one change.

### US4 — Keys rotate without rewriting history (P1)

An Evidence Collector rotates a wrapping key or migrates to a newer approved
algorithm while evidence remains available and its historical identity unchanged.

**Independent test**: Capture before/during/after rotation, crash at every durable
checkpoint, revoke the old key, restore a backup and verify authorized reads,
denials, hashes, signatures and byte-exact exports.

**Acceptance**: Data keys are rewrapped or content is transactionally re-encrypted
as required; no plaintext intermediate reaches disk; interrupted rotation resumes;
revoked keys cannot decrypt new material; evidence IDs and canonical plaintext
digests remain stable.

### US5 — A portable export remains protected against store theft and future quantum attack (P2)

A Level 2 or Level 3 user creates an encrypted evidence bundle for an explicitly
named recipient. Only the recipient's authorized AtMem instance can decrypt it.

**Independent test**: Export with ML-KEM recipient keys, tamper with envelope,
ciphertext, manifest and recipient set, attempt classical-only downgrade, then
import on authorized and unauthorized installations.

**Acceptance**: Authorized import succeeds byte-for-byte; all tamper, recipient
substitution and downgrade cases fail before plaintext; no password-only portable
export is treated as quantum-safe.

## Privilege hierarchy

Evidence privileges are ordered within an authorized tenant/workspace/run scope.
Higher levels include lower-level evidence operations only for that same scope;
they never widen scope implicitly.

| Level | Name | Permitted evidence operations |
| --- | --- | --- |
| **Level 1** | Viewer | View exact authorized evidence inside AtMem, render original media, and search within the authorized scope. No file export, replay manifest, privilege change, retention change or deletion. |
| **Level 2** | Investigator | All Level 1 operations plus store-only reconstruction, inert replay-manifest creation and recipient-encrypted bundle export. No plaintext file, artifact or bundle export. |
| **Level 3** | Evidence Collector | All Level 2 operations plus plaintext artifact/bundle export, grant/revoke evidence privileges, configure retention, authorize verified deletion and initiate rotation/recovery for the authorized scope. “Collector” is the human evidence-control role; it is distinct from an append-only evidence submitter. |

Two capabilities are deliberately outside the hierarchy:

- **Evidence submitter** may append authenticated observations but cannot decrypt,
  search, view or export them unless separately assigned Level 1 or higher.
- **Key custodian** may make a configured key source available, rotate/revoke key
  encryption keys and perform recovery ceremonies but gains no evidence privilege
  from custody alone. Key release and evidence authorization are both required.

## Functional requirements

- **FR-001 — Application-only plaintext boundary**: Every evidence view, search,
  reconstruction, media rendering, exact download and plaintext export MUST be
  produced by an authenticated AtMem application service after authorization.
  Direct database, object-store, backup, spool or export inspection MUST yield no
  plaintext. Adapters and producers have append-only submission capability by
  default and MUST NOT receive a decryption primitive or reusable data key.
- **FR-002 — Complete encryption coverage**: Encrypt all evidence content and
  semantic metadata at rest, including envelope fields, identities, scopes,
  timestamps, event types, memory/context, decisions, prompts, model/tool I/O,
  URLs, paths, filenames, MIME types, captions, transcripts, thumbnails,
  embeddings/search indexes, audit events, original image/audio/video/file/page
  bytes, spools, temporary durable files, backups and exports. No side table,
  cache or derived representation may create a plaintext bypass.
- **FR-003 — Data encryption suite**: The initial approved content suite MUST use
  AES-256-GCM with a fresh unpredictable 96-bit nonce per key and encrypted chunk,
  a 128-bit authentication tag, and no key/nonce reuse. Large artifacts MUST use
  independently authenticated ordered chunks bound to one artifact manifest.
  Semantic metadata belongs inside ciphertext; associated data is limited to
  non-sensitive format/version and opaque cryptographic binding values.
- **FR-004 — Post-quantum key establishment and signatures**: Portable recipient
  wrapping MUST use NIST FIPS 203 ML-KEM-768 or stronger. Export and recovery
  manifests MUST use FIPS 204 ML-DSA-65 or stronger; an additive classical
  signature MAY be retained for transition but MUST NOT be the quantum-safe
  authority. SHA-512, SHAKE256 or KMAC256 MUST be used for new long-lived
  cryptographic bindings as appropriate. Algorithm identifiers are versioned and
  downgrade-protected.
- **FR-005 — Envelope key hierarchy**: Generate a random 256-bit data-encryption
  key for each run or smaller independently deletable evidence partition. Wrap
  data keys with a scoped key-encryption key held by the configured OS keychain,
  TPM/secure enclave, customer KMS/HSM or encrypted recovery mechanism. No root,
  key-encryption or recipient private key may be stored in the evidence store.
- **FR-006 — Plaintext minimization and honest leakage boundary**: The only
  permitted plaintext storage fields are a fixed format magic, format version,
  cryptographic-suite identifier, opaque random key-slot/object identifiers,
  nonce/ciphertext/tag lengths and recovery-required state. Randomized filenames
  MUST reveal no semantic name. AtMem MUST document that filesystem ownership,
  total size, object count and modification times may remain visible to an OS-level
  observer; optional padding/bucketing may reduce but cannot eliminate that leakage.
- **FR-007 — Authorization-before-decryption**: Authenticate principal, resolve
  current membership and exact tenant/workspace/agent/session/run scope, authorize
  operation and evidence privilege, and obtain key release before decrypting any
  field. Counts, search existence, thumbnails and error messages follow the same
  rule. Cross-scope joins and bulk operations authorize every included object.
- **FR-008 — Privilege enforcement**: Implement Level 1 Viewer, Level 2
  Investigator and Level 3 Evidence Collector exactly as specified above.
  Privilege assignment is explicit, revisioned, scoped, expiring when configured,
  revocable and deny-by-default. Parent/child agents, task links, provider trust,
  host ownership, administrator status and key custody MUST NOT imply evidence
  privilege.
- **FR-009 — Export controls**: Plaintext export MUST be denied to Level 1 and
  Level 2 and is available only to a Level 3 Evidence Collector after explicit
  confirmation and reauthorization. Every plaintext export states content scope,
  recipient/purpose, time, exporter and a warning that AtMem protection ends at
  the exported copy. Encrypted export is bound to named ML-KEM recipient keys.
  AtMem MUST never write plaintext export staging files; streaming output and
  failure cleanup are mandatory.
- **FR-010 — Encrypted audit**: Record successful and denied view, search, reveal,
  download, reconstruction, replay-manifest, export, grant, revoke, unlock, key
  release, rotation, recovery, retention and deletion operations. Audit content is
  encrypted like other evidence, append-only and chain/signature protected. An
  auditor needs explicit Level 1+ privilege for evidence content; possessing audit
  review capability alone reveals no session content.
- **FR-011 — Lock and capture behavior**: AtMem starts locked unless an explicitly
  configured secure key source permits unattended unlock. While keys are
  unavailable, no plaintext evidence may be spooled to disk. A controlled model or
  tool boundary MUST fail before dispatch when required full-fidelity evidence
  cannot be encrypted durably; post-boundary loss is recorded once keys return as
  an exact coverage gap without invented content.
- **FR-012 — Rotation, recovery and cryptographic deletion**: Rotation MUST be
  resumable, crash-safe and normally rewrap data keys without changing canonical
  evidence. Algorithm migration that requires re-encryption uses a transactional
  copy/verify/switch process. Recovery requires an explicit configured mechanism
  and creates an audit event. Verified deletion removes ciphertext and all known
  copies and destroys applicable data keys; backups retain declared expiry or key-
  destruction behavior without falsely claiming immediate physical erasure.
- **FR-013 — Compact settings experience**: Spec 022 Settings MUST show one
  collapsed `Evidence protection` row containing `Encrypted`, `Locked/Unlocked`,
  key-source label, last successful rotation and attention state. Selecting it
  opens a focused drawer with at most four primary actions: lock/unlock, key source,
  rotate/recover and export policy. Advanced suite/recipient/retention details are
  collapsed. Routine changes MUST NOT require navigating a massive panel or
  editing unrelated settings.
- **FR-014 — Encryption and capture setting semantics**: The default is encrypted
  full-fidelity capture of data and metadata. The compact `Data` switch controls
  content retention: `on` retains encrypted exact text, links/pages, files,
  images, audio and video plus encrypted metadata; `off` retains encrypted
  metadata only and marks every affected run `not_reconstructable`. A separately
  named `Recorder` control may disable all new evidence capture. Settings may also
  change key source, unlock policy, rotation and recovery. There is no control
  that stores plaintext evidence or labels metadata-only/disabled capture as a
  supported Black Box. Existing encrypted evidence remains encrypted when future
  data or recorder capture is disabled.
- **FR-015 — Cryptographic agility and compatibility**: Store suite/version per
  encrypted object, maintain a signed algorithm-policy registry, reject downgrade,
  and provide migration readiness for NIST revisions or algorithm replacement.
  Existing HMAC/Ed25519 delegated-provider messages remain valid signed payloads
  inside encrypted evidence; AtMem adds its post-quantum protection without
  rewriting or claiming to upgrade the provider's original signature.
- **FR-016 — Application plaintext hygiene**: Decrypt the minimum object only for
  the duration of an authorized operation, zeroize mutable key/plaintext buffers
  where the runtime permits, disable core dumps for the protected process profile,
  prevent plaintext logs/telemetry/crash reports, use secure temporary-memory
  handling, and close/lock active streams on privilege revocation or session expiry.
- **FR-017 — Backup and standalone reconstruction**: A supported AtMem evidence
  backup MUST contain encrypted envelope/artifact/audit objects and wrapped keys,
  never plaintext. With an authorized key source or recovery ceremony, a fresh
  AtMem application reconstructs the exact run. Without keys it reports only
  `encrypted_locked` and recovery requirements, revealing no evidence metadata.

## Key entities

- **EvidencePrivilegeGrant**: Principal, level, exact scope, issuer, revision,
  issued/expiry/revoked times, reason and policy generation; stored encrypted.
- **EvidenceKeySlot**: Opaque slot ID, suite, key-source type, wrapped scoped key,
  lifecycle state, cryptoperiod and rotation/recovery references.
- **EncryptedEvidenceObject**: Opaque object ID, suite/version, nonce, ciphertext,
  authentication tag and encrypted logical envelope/artifact/audit payload.
- **EncryptedArtifactManifest**: Ordered authenticated chunk bindings and encrypted
  content metadata for one original multimodal artifact.
- **EvidenceAccessEvent**: Encrypted append-only authorization decision and action
  result for view/export/key/lifecycle operations.
- **RecipientKey**: Named installation or investigator ML-KEM public key,
  fingerprint, allowed scope/purpose, validity and revocation state.
- **CryptoMigration**: Source/target suites, bounded object set, checkpoint,
  verification state, actor and recovery path.

## Success criteria

- **SC-001 — At-rest secrecy**: Automated planted-secret scans across SQLite,
  WAL/journal, artifact objects, indexes, spool, temp directory, backup and export
  recover zero exact or partial planted text, URL, filename, MIME, caption,
  transcript, image, audio or video signature without AtMem/key authorization.
- **SC-002 — Privilege matrix**: Positive and adversarial tests cover every
  operation for submitter, Levels 1–3, key custodian and unrelated principal with
  zero unauthorized decryptions, exports, existence disclosures or inherited
  privileges across 10,000 generated scope combinations.
- **SC-003 — Application-only access**: Database and object-store tools cannot
  render any evidence. Authorized dashboard/CLI/API/MCP calls return byte-identical
  content through AtMem; direct decryption APIs are absent from public adapters and
  package exports.
- **SC-004 — Quantum-safe profile**: Known-answer and negative tests use validated
  AES-256-GCM, ML-KEM-768 and ML-DSA-65 implementations; reject nonce reuse,
  modified ciphertext/tag/AAD, invalid encapsulation/signature, classical-only
  recipient wrapping, unknown suite and downgrade. Record exact library/module and
  validation status rather than claiming certification that was not obtained.
- **SC-005 — Rotation and crash safety**: Fault injection at every rotation and
  migration checkpoint yields either the old or new verified key state, never
  plaintext or permanent partial loss. After old-key revocation, all intended new
  evidence decrypts and no new object accepts the retired key.
- **SC-006 — Compact settings**: At 375px and 1280px, 10 of 10 automated primary
  journeys identify encryption/lock/rotation status and complete one common action
  in at most two interactions. Keyboard, focus, screen-reader labels and
  confirmation/error recovery pass without horizontal overflow.
- **SC-007 — Locked failure behavior**: With key source unavailable, capture tests
  persist zero plaintext bytes, dispatch zero controlled model/tool requests that
  require full capture, and show one precise recovery action. Unlock resumes new
  capture without fabricating the missed content.
- **SC-008 — Portable encrypted export**: Authorized recipient export/import
  preserves every envelope and multimodal byte; unauthorized recipient, tamper,
  revoked key, wrong scope and interrupted streaming leave zero plaintext files and
  cannot be imported.
- **SC-009 — Dead-agent encrypted disaster gate**: Repeat Spec 020 SC-011 using
  only an encrypted AtMem store copy. Direct inspection reveals nothing; authorized
  recovery through a fresh AtMem process reconstructs the complete oracle; missing
  keys produce only an honest locked state.
- **SC-010 — Performance and footprint**: On the documented consumer-hardware
  reference profile, record capture latency, decrypt/render latency, encrypted
  storage expansion and peak memory for text plus 1 MiB, 100 MiB and maximum-
  supported artifact fixtures. Release notes publish measurements and configured
  ceilings; performance MUST NOT justify plaintext fallback.

## Failure and edge cases

- Key source unavailable before capture, during capture, during an open media
  stream, after acknowledgement, or during reconstruction.
- Crash between ciphertext durability, key wrapping, index update, audit append
  and producer acknowledgement.
- Nonce collision or process/VM snapshot rollback that repeats random state.
- Privilege revoked during pagination, streaming media, export or replay-manifest
  construction.
- A Level 3 Evidence Collector attempts to grant a wider scope than they possess.
- Key custodian attempts content access without evidence privilege; investigator
  attempts key administration or unapproved plaintext export.
- Rotation overlaps backup, restore, export, deletion, capture and another rotation.
- An old application sees a newer suite; a new application restores old encrypted
  data; a provider supplies an Ed25519-signed delegated result.
- Artifact is too large, storage quota fills, ciphertext is truncated, chunk order
  changes, or a tag fails after partial streaming.
- OS exposes file sizes, object count or modification times despite encrypted
  semantic metadata.

## Compatibility and migration

This feature is an additive encrypted-store generation, not an in-place fiction.
Existing plaintext or hash-only stores remain readable only through an explicit
owner-authorized migration running inside AtMem. Migration inventories every
evidence-bearing table/file/index, encrypts into a new store, verifies bytes and
references, switches atomically and offers verified cleanup of the old plaintext
copy. Until cleanup succeeds, status remains `plaintext_source_exists` and the
product cannot claim at-rest protection.

No migration can recover content absent from historical hash-only evidence.
Existing provider request/result contracts and signatures are preserved exactly.
Encrypted format negotiation fails closed on unsupported suites. Rollback requires
an application version capable of the encrypted generation; it never emits a
plaintext downgrade store.

## Threat model and honest limitations

The supported claim covers offline theft or direct inspection of AtMem databases,
artifact storage, indexes, spools, temporary durable files, backups and exports;
unauthorized application users; cross-scope principals; and future quantum attacks
within the security assumptions of the named NIST algorithms.

AtMem does not claim confidentiality from a fully compromised OS/root account,
debugger, malicious kernel/hypervisor, compromised AtMem process, screen capture,
or authorized recipient after plaintext disclosure. Physical file size/count/time
leakage is not semantic evidence confidentiality. “Quantum-safe” means use of the
specified standardized profile and algorithm agility, not a guarantee that no
future cryptanalysis will ever succeed.

## Normative cryptographic references

- NIST FIPS 203, ML-KEM: <https://csrc.nist.gov/pubs/fips/203/final>
- NIST FIPS 204, ML-DSA: <https://csrc.nist.gov/pubs/fips/204/final>
- NIST FIPS 205, SLH-DSA backup signature standard: <https://csrc.nist.gov/pubs/fips/205/final>
- NIST SP 800-38D, AES-GCM: <https://csrc.nist.gov/pubs/sp/800/38/d/final>
- NIST SP 800-57 Part 1 Rev. 5, key management: <https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final>
- NIST Post-Quantum Cryptography FAQ: <https://csrc.nist.gov/Projects/Post-Quantum-Cryptography/faqs>

Implementations MUST track published errata and transition guidance for every
selected standard. The specification names minimum initial algorithms; the
versioned policy registry remains authoritative for supported suites.

## Out of scope

- Claiming protection from an already compromised unlocked AtMem process or OS.
- Giving agents general plaintext evidence access.
- Storing plaintext because encryption is temporarily unavailable.
- Password-only portable exports advertised as quantum-safe.
- Replacing exact evidence with hashes, redaction or metadata in the name of
  encryption.
- Changing Storizon or another delegated provider's signed v1 payload.
- Claiming FIPS 140 validation without using and verifying a validated module in
  the exact deployed configuration.

## Invariant Attestation

Touches INV-004, INV-005, INV-006, INV-008, INV-010 and INV-011 through
`spec028.encrypted_at_rest`, `spec028.authorization_before_decryption`,
`spec028.application_plaintext_boundary`, `spec028.quantum_profile`,
`spec028.rotation_recovery` and `spec028.compact_settings` assertions. The first
source-level encrypted-vault, privilege and compact-settings checks are implemented;
rotation/recovery, complete legacy migration, installed disaster recovery and
certification remain unimplemented and MUST NOT be inferred from these identifiers.
