# Tasks: Portable Multimodal AtMem Home

**Status**: Complete for AtMem 2.3.0
**Input**: [spec.md](spec.md), [plan.md](plan.md)
**Evidence policy**: Record verification under `docs/implementation-evidence/030/`.

## Phase 1 — Home and artifact foundation

- [x] [T001] Implement `HomeLayout` root precedence, canonical directories, safe
  relative resolution, symlink-escape refusal and versioned content-free manifest
  creation/verification in `atmem/home/`, with tests in `tests/test_home.py`
  (FR-001–FR-003, FR-011; SC-003).
- [x] [T002] Implement the streaming encrypted content-addressed artifact vault,
  atomic durability, deduplication, authenticated reads and tamper/orphan checks;
  prove raw stores hide planted image/audio/video signatures (FR-004–FR-005;
  SC-001, SC-003, SC-005).
- [x] [T003] Integrate artifact capture/materialization with protected evidence so
  ordered multimodal parts reference canonical blobs, legacy inline parts remain
  readable and a blob failure cannot claim exact capture (FR-004–FR-005, FR-013).

## Phase 2 — Host capture and product truth

- [x] [T004] Fix OpenClaw attachment capture for current `media`, safe
  `originalMedia`, staging and legacy aliases without filesystem guessing; preserve
  valid bindings across sparse writes and clear them for new text-only turns
  (FR-006; SC-002).
- [x] [T005] Capture and label exact multimodal parts from `llm_input` as the
  model-delivered representation, retaining transformed host-original and model-input
  bytes separately when both exist (FR-005–FR-006, FR-020; SC-001–SC-002).
- [x] [T006] Update evidence/session UI to render authorized artifact bytes and show
  `Captured evidence` separately from `Memory status`, including explicit capture
  failure/legacy placeholder states (FR-014–FR-015; US1, US5).

## Phase 3 — Portable restore and migration mode

- [x] [T007] Add consistent stopped/snapshot inventory and standalone `home status`
  and `home verify` services/CLI with human and JSON output (FR-002, FR-013,
  FR-016–FR-017).
- [x] [T008] Implement `atmem restore HOME` read-only preflight/dashboard launch,
  selected-home propagation and copied-home account login without pre-auth content
  disclosure (FR-007–FR-008, FR-013, FR-016, FR-018; SC-006–SC-007).
- [x] [T009] Implement Administrator-only adoption with writer detection, session
  rotation, machine-local rebinding, index rebuild marker and immutable historical
  evidence/adoption receipt tests (FR-009, FR-012, FR-016, FR-018).
- [x] [T010] Implement discover/preflight/copy/verify/switch/commit migration with an
  fsync journal, restart/rollback tests at every boundary and no automatic source
  deletion (FR-010, FR-016; SC-004).

## Phase 4 — One-home integration and acceptance

- [x] [T011] Route new CLI, dashboard, memory, evidence, identity, AtBot, delegated
  provider and framework-adapter defaults through the selected AtMem Home while
  preserving explicit-path and wire compatibility (FR-001, FR-003, FR-019; SC-008).
- [x] [T012] Add compact authenticated Home health/restore/adopt/migrate controls and
  recovery guidance; keep operational settings concise (FR-007–FR-009, FR-015).
- [x] [T013] Execute the dead-agent destructive acceptance: copy only the AtMem Home,
  remove host agent/media/log/workspace/cache/network, authenticate on a fresh
  process and reconstruct exact ordered text/page/file/image/audio/video evidence
  (FR-013; SC-001, SC-003, SC-006–SC-007).
- [x] [T014] Run identity/role, evidence, dashboard/HTTP/CLI, OpenClaw current/latest,
  delegated provider, Pydantic AI, LangGraph, package build and installed-artifact
  regressions; record exact commands/results and honest residual limits under
  `docs/implementation-evidence/030/` (SC-001–SC-008).
- [x] [T015] Close the live WebChat media gap with a regression matching the exact
  `__openclaw.media[].url = media://inbound/<id>` transcript shape; capture at the
  terminal hook when earlier media hooks are sparse, persist encrypted bytes, render
  image/audio/video inline for Investigator and higher while Viewer remains
  content-free, and expose per-artifact plaintext
  download only to Evidence Collector or Administrator (FR-004–FR-006, FR-015).
