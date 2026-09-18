# Memory Fabric tasks

Status: setup and P0a complete; P0b pilot measured, but cold/warm and final
manifests remain pending. Checkmarks mean verified work, not intended work.

## Setup and research

- [x] T001 Define spec, plan and experimental protocol in `specs/033-memory-fabric/` (FR-001–013).
- [x] T002 Record primary-source research, Claude read-only critique and dispositions in `research.md` and `review.md` (FR-013).
- [x] T003 Run Spec Kit consistency/coverage analysis before code; report findings (all FR/SC).

## P0a — Measurement contracts

- [x] T004 Add seeded open-loop arrival generation and strict request/observation validation in `research/memory_fabric/protocol.py` (FR-001–003; SC-001).
- [x] T005 Add outcome reconciliation, per-lane latency and goodput reports in `research/memory_fabric/protocol.py` (FR-002–003, FR-009, FR-012; SC-001).
- [x] T006 Test missing/duplicate outcomes, temporal inconsistencies, deadline boundaries, censored work, deterministic schedules, unknown verification, closed schema, no home/runtime/I/O access and denominator correctness in `tests/test_memory_fabric_protocol.py` (FR-001–003, FR-009; SC-001).
- [x] T007 Document P0a limitations/invocation in `research/memory_fabric/README.md`; run focused tests and record validation in `review.md` (FR-001, FR-013).

## P0b — Real baseline (requires P0a)

- [x] T008 Build disposable synthetic local-memory/evidence/multimodal runner in `research/memory_fabric/local_baseline.py` and integration tests (FR-001, FR-004, FR-010; SC-002).
- [ ] T009 Add real open-loop dispatch, bounded admission, explicit lag/unknown stages, cold/warm profiles and raw report manifests in the runner and `research/memory_fabric/results/` (FR-002–004, FR-007, FR-012; SC-002).
  Remaining oracle work: freeze/replay the full FTS ranking snapshot, not only
  the read subject generation; unrelated-subject writes affect shared BM25
  statistics (see `homa-review.md`).
- [x] T010 Run baseline pilot; record bottleneck evidence and go/no-go decision before scheduler implementation in `research.md` (FR-004, FR-013; SC-002).
- [x] T010a Review Homa/DRR starvation mechanisms; correct the exploratory
  dispatcher/harness, run frozen held-out comparisons and record independent
  review/results in `homa-review.md`. Does not complete P1 authority or P2
  integration gates (FR-003–004, FR-008, FR-011–013).

## P1 — Safety model (requires P0 review)

- [ ] T011 Specify authority/release linearization and read/write/delete barriers in `specs/033-memory-fabric/contracts.md`; map real integration points (FR-005, FR-009–010).
- [ ] T012 Implement reference lifecycle/credit model in `research/memory_fabric/lifecycle.py` with exhaustive small interleavings and randomized tests in `tests/test_memory_fabric_lifecycle.py` (FR-005–007, FR-009–010; SC-003).

## P2 — Scheduling experiments (requires T010–012)

- [ ] T013 Implement FIFO, isolated pools, EDF, estimated-size, DRR and combined policies with identical resource bounds in `research/memory_fabric/simulation.py` and tests (FR-007–008, FR-011; SC-004).
- [ ] T014 Test reserved bulk/tenant service, bound assumptions, estimator abuse, deadline behavior and output parity against baseline (FR-008–009; SC-003–004).
- [ ] T015 Freeze experiment manifests; run ablations, held-out workloads and uncertainty analysis; publish complete synthetic raw reports (FR-003, FR-011–013; SC-004).

## P3 — Opt-in real integration (requires explicit design review after P2)

- [ ] T016 Specify actual runtime contracts and implement opt-in scheduler only at reviewed authority boundaries; tests cover grants, cancellation, retries, revocation ACK/release races and delegated fail-closed behavior (FR-005–010; SC-003, SC-005).
- [ ] T017 Verify protected full-fidelity evidence, authorized reconstruction after host loss, role denials and unchanged retrieval/delegated/adapter behavior; link trace drill-down in existing UI with access tests (FR-001, FR-009–010; SC-005).

## P4 — Paper, not before evidence

- [ ] T018 Complete related-work novelty assessment and manuscript in `research/memory_fabric/paper.md`; Markdown H1 title, LaTeX, actual results/limitations and reproducibility instructions (FR-013; SC-004–005).
- [ ] T019 Read-only independent review of results, claims and reproduction; retain unresolved limitations and negative results in `review.md` (FR-011–013).
