# Tasks — Spec 052

## Research and contracts
- [x] [T001] Record primary literature, code pins/licenses and design decision in `specs/052-measured-memory-adaptation/research.md` (FR-010, SC-003).
- [x] [T002] Cross-artifact consistency analysis in `specs/052-measured-memory-adaptation/analysis.md` before code (FR-001–011).
## Implementation
- [x] [T003] Implement closed manifest, policy, phase, frozen snapshots and scoped owner API in `atmem/feedback/adaptation.py` (FR-001–005, FR-008).
- [x] [T004] Implement durable trial/model-call budgets, exact encrypted traces, independent verifier and report in `atmem/feedback/adaptation.py` (FR-003, FR-006–008).
- [x] [T005] Add public CLI runner/read-only SQLite/explicit provider adapter in `atmem/benchmark/memory_adaptation.py` and `scripts/evaluate_memory_adaptation.py` (FR-009, FR-011).
## Verification
- [x] [T006] Adversarial actual-service, restart, secret/ciphertext, budget, split/selection and tool-boundary tests in `tests/test_memory_adaptation.py` and `tests/test_memory_adaptation_runner.py` (SC-001).
- [ ] [T007] Freeze manifest before inference and run one real pilot; retain raw encrypted evidence and write `specs/052-measured-memory-adaptation/implementation-evidence.md` with honest all-arm results/resources (FR-009, SC-002–003).
## Delivery
- [ ] [T008] Add `docs/measured-memory-adaptation.md`, SDK/CLI example, affected guide updates and `docs/releases/v2.3.15b2.md` (FR-011).
- [ ] [T009] Version alignment, Python/companion/OpenClaw/build/installed-artifact/docs gates and public review in `specs/052-measured-memory-adaptation/release-evidence.md` (SC-004).
- [ ] [T010] Publish and verify beta GitHub/PyPI/npm; prepare private website source-pin PR, record owner-review/deployment pending (SC-004).
