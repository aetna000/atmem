# Tasks: Encrypted Evidence and Privileged Access

**Status**: Source implementation complete through T020; final installed-upgrade gate remains
**Input**: [spec.md](spec.md), [plan.md](plan.md)
**Evidence policy**: Record verification under `docs/implementation-evidence/028/`.

## Phase 1: Contracts and foundation

- [x] [T001] Implement capture modes, the Viewer/Investigator/Evidence Collector operation matrix and scope validation in `atmem/evidence/models.py`, with exhaustive tests in `tests/test_evidence_protection.py` (FR-007, FR-008, FR-014; SC-002).
- [x] [T002] Implement external-key AES-256-GCM sealed objects and fail-closed optional ML-KEM-768/ML-DSA-65 primitives in `atmem/evidence/crypto.py`; add known-answer, nonce, tamper and missing-provider tests (FR-003–FR-005, FR-015; SC-004).
- [x] [T003] Implement the opaque encrypted SQLite evidence/audit vault in `atmem/evidence/store.py`, including full/metadata/off behavior and no semantic plaintext columns (FR-001, FR-002, FR-006, FR-010, FR-011; SC-001, SC-007).

## Phase 2: Privileged application service

- [x] [T004] Implement authorization-before-decryption, exact read/reconstruction, encrypted export and Evidence-Collector-only confirmed plaintext streaming in `atmem/evidence/service.py` (FR-007–FR-010, FR-016, FR-017; SC-002, SC-003, SC-008).
- [x] [T005] Add three explicit development test accounts and CLI setup/status/capture/show/export commands in `atmem/cli.py`, with credentials stored separately from the vault and clear non-production labelling (US2, FR-008, FR-009; SC-002).
- [x] [T006] Expose the same protected evidence operations through `atmem/service/application.py` and authenticated `/v1/evidence` routes in `atmem/control/web.py`; remove header-selected evidence-role trust and test scope/operation denials in `tests/test_http_api.py` (FR-001, FR-007–FR-010; SC-003).

## Phase 3: Capture integration and interface

- [x] [T007] Integrate `ControlPlaneManager.record_blackbox_event` with the encrypted vault, preserving legacy digest projections while ensuring exact reserved data never reaches legacy plaintext tables (FR-001, FR-002, FR-011, FR-015; SC-001, SC-009).
- [x] [T008] Update `integrations/openclaw/index.ts` to submit exact prompt, model, context, tool and ordered text/image/audio/video/file evidence by default, and update `src/execution-spool.ts` so durable pending envelopes are AES-256-GCM encrypted (FR-002, FR-011, FR-014; SC-001, SC-007).
- [x] [T009] Add one collapsed Evidence protection settings row and focused drawer in `atmem/control/assets/app.js` and `app.css`, showing Data on/off, recorder state, lock/key source and role without a page-sized form (FR-013, FR-014; SC-006).

## Phase 4: Remediation from consistency review

- [x] [T010] Replace the single vault-wide content key with random per-run/partition data keys wrapped by an external key-encryption key, including opaque key slots and exact round-trip tests in `atmem/evidence/crypto.py`, `atmem/evidence/store.py` and `tests/test_evidence_protection.py` (FR-003, FR-005, FR-006; SC-004).
- [x] [T011] Implement missing-key locked detection, no replacement-key creation for an existing vault, capture/read fail-closed behavior and recovery guidance in `atmem/evidence/service.py` and its CLI/UI status tests (FR-001, FR-011; SC-007).
- [x] [T012] Implement and audit search, replay-manifest creation, scoped privilege grant/revoke, retention, verified deletion and key rotation operations, ensuring Viewer/Investigator/Evidence Collector boundaries are service-enforced in `atmem/evidence/` and HTTP/CLI surfaces (FR-007, FR-008, FR-010, FR-012; SC-002, SC-003, SC-005).
- [x] [T013] Replace materialized plaintext CLI export with an authorized chunk iterator, mode-0600 direct output and partial-output cleanup; explicitly mark non-streaming HTTP/MCP export profiles unsupported in capabilities (FR-009, FR-016; SC-003, SC-008).
- [x] [T014] Implement encrypted-control-store inventory and migration state, atomic switch/verification and explicit `plaintext_source_exists` reporting; add previously published store upgrade fixtures and raw semantic-metadata scans (FR-002, FR-006, FR-015; SC-001).
- [x] [T015] Complete the compact Evidence protection drawer with working lock/unlock, key-source, rotate/recover and export-policy actions, keyboard/focus labels and 375px/1280px layout checks in `atmem/control/assets/` and `tests/test_dashboard.py` (FR-013; SC-006).
- [x] [T016] Add complete AES/ML-KEM/ML-DSA negative vectors for nonce reuse, AAD/tag/ciphertext mutation, invalid encapsulation/signature, unknown suite and downgrade in `tests/test_evidence_protection.py`, recording exact module validation status (FR-003, FR-004, FR-015; SC-004).

## Phase 5: Acceptance and documentation

- [x] [T017] Add planted-secret multimodal stolen-store/spool/backup scans, byte-exact authorized recovery and complete role/export matrix tests in `tests/test_evidence_protection.py` and OpenClaw hook/spool tests (SC-001–SC-008).
- [x] [T018] Add a fresh-process dead-agent disaster test that copies only the supported encrypted backup and authorized recovery material, destroys agent/log/workspace state, reconstructs the oracle, and returns only locked state without keys (FR-017; SC-009).
- [x] [T019] Measure capture/decrypt latency, encrypted expansion and peak memory for text, 1 MiB, 100 MiB and declared maximum fixtures on the documented local profile; enforce configured limits without plaintext fallback (SC-010).
- [x] [T020] Update capability/status/release documentation and `docs/implementation-evidence/028/` with exact commands, versions, limitations and measured results (FR-015; SC-010).
- [ ] [T021] Run focused Python, HTTP, CLI, upgrade, documentation and complete OpenClaw build/typecheck/test gates; keep every failed or unavailable profile explicitly unimplemented and do not claim the prerelease is published (SC-001–SC-010).
