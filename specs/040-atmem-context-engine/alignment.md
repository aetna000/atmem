# Spec and Roadmap Alignment Audit

**Audit date**: 2026-10-01

**Decision**: Spec 040 is the controlling specification for the AtMem 2.3.8
formation/retrieval engine and matched benchmark qualification. Historical
results remain evidence; historical internal architecture is not a constraint.

| Source | Retained obligation | Superseded or constrained decision |
|---|---|---|
| Constitution I | Authority before intelligence and canonical revalidation | None |
| Constitution II/IV | Full source/provenance, standalone reconstruction, encryption, deletion and scoped disclosure | No benchmark optimization may weaken or bypass these guarantees |
| Constitution V/VII | Host-neutral contracts, local-first operation, explicit egress and replaceable intelligence | No host-specific or provider-owned core |
| Constitution VIII | Held-out, matched, reproducible production evidence | Small samples and extrapolations are development evidence only |
| Spec 001 | Versioned benchmark contracts, safety gates and repeatability | Synthetic quality scores cannot establish production leadership |
| Spec 002 | Supporting-evidence aggregation, authorization and byte stability | Its ranking policy does not constrain the new engine |
| Spec 003/004 | Delegated/native context boundaries and adapter neutrality | Providers/adapters cannot own ranking or authorization |
| Spec 006 | Typed proposals, reconciliation, lineage, review and safe fallback | Existing extraction implementation may be replaced; proposal authority remains |
| Spec 008 | Authorization, attributable signals, abstention, profile identity and cross-surface parity | Calibration/ranking architecture and existing default are superseded by Spec 040 after qualification |
| Spec 009 | Entity/relationship evidence and scope | Graph implementation is replaceable and remains derived, never authoritative |
| Spec 015 | Retention, expiry and verified deletion | None |
| Spec 018 | Cross-cutting invariants | None; all affected invariants remain gates |
| Spec 019 | Provider-neutral governed delivery | None; Spec 040 produces the governed package it distributes |
| Spec 020/028/030 | Full-fidelity evidence, encryption and portable AtMem Home | No duplicate plaintext benchmark or derived source store |
| Spec 026 | Temporal correction, consolidation and review | Consolidation may feed formation views but cannot silently mutate authority |
| Spec 031 | Matched Mem0 comparison and honest reporting | Historical tiny calibration and legacy default are superseded; comparator discipline remains |
| Spec 035 | Production corpus/version/cost/latency evidence | Benchmark orchestration is consolidated under Spec 040/038 qualification |
| Spec 037 | Hermes provider, setup, restore, isolation and Dolphin harness | Hermes integration remains; Spec 040 changes only the context engine behind its public boundary |
| Spec 038 | Typed formation, information need, neighbourhoods, sufficiency, performance and benchmark gates | Spec 040 supersedes its extend-the-existing-hybrid implementation decision and becomes the engine owner |
| Spec 039 | Experimental AtMem-MJM reranker and LoCoMo evidence | Optional measured signal only; not release-critical or a source of authority |
| Release roadmap | 2.3.8 includes Hermes, MCP registration, AtFlows redaction and retrieval qualification | Spec 040 owns the retrieval release floor and separate leadership claim gates; unrelated commitments remain |

## Complete Spec 038 gate crosswalk

This crosswalk is normative. “Replaced” means Spec 040 supplies the named
contract; it does not withdraw the outcome or historical evidence.

| Spec 038 IDs | Spec 040 disposition |
|---|---|
| FR-001–FR-004 | Retained by FR-002–FR-004 and FR-008: authority, immutable source, proposal-only intelligence and deterministic fallback |
| FR-005–FR-012 | Replaced by FR-004–FR-008 and SC-002/SC-014: typed views, source fields, occurrence identity, reconciliation and loss receipts |
| FR-013–FR-020 | Replaced by FR-009–FR-013: explicit information needs, independent nominations, temporal/link semantics and bounded neighbourhoods |
| FR-021–FR-026 | Replaced by FR-014–FR-016, FR-034 and SC-015: source-backed sufficiency, fail-closed compatibility and complete reader budgets |
| FR-027–FR-036 | Retained and strengthened by FR-024–FR-029, FR-032, FR-035–FR-036 and SC-017: stage metrics, official inert adapters, frozen splits, ablations, external artifacts and privacy |
| FR-037–FR-050 | Retained by FR-008, FR-017–FR-023, FR-030, FR-033 and SC-007–SC-012: local-first operation, migration, profiles, product parity, bounded diagnostics and cross-platform behavior |
| FR-051–FR-053 | Replaced by FR-001, FR-020–FR-023, FR-033–FR-034 and the V3 contract: neutral ingest/delivery, byte-stable compatibility and sampled shadow |
| FR-054 | Retained verbatim in SC-013 as the pinned LoCoMo no-regression gate |
| FR-055–FR-059 | Retained by FR-005–FR-007, FR-009–FR-014 and SC-014: assertion validation, occurrence identity, resumable formation, attributable ranking and obligation-bound sufficiency |
| FR-060–FR-063 | Retained by FR-013–FR-017, SC-015–SC-016 and task finalization probes: total reader budget, evidence-vs-reader attribution, bounded navigation and no-judge preflight |
| SC-001–SC-002 | Retained and strengthened by SC-001–SC-002 and SC-014 |
| SC-003 | Retained as the absolute 60%/+5pp release floor in SC-013; the stricter matched-lead target is SC-003–SC-004 |
| SC-004 | Reclassified as a Dolphin claim gate in SC-005–SC-006, not a stable-release dependency |
| SC-005–SC-008 | Retained by FR-028–FR-030 and SC-007–SC-012; repeats are symmetric and heavy artifacts stay external |
| SC-009–SC-011 | Retained as research/claim targets in SC-003–SC-006 and SC-017, never converted into safety evidence |
| SC-012 | Retained by SC-010: fresh/upgrade product journey on Linux, macOS and Windows-compatible paths |
| SC-013–SC-015 | Retained and strengthened by SC-007–SC-008 and SC-010: absolute latency/RSS/shadow/storage ceilings and cross-surface parity |
| SC-016 | Retained verbatim in SC-013: pinned LoCoMo regression no worse than two points |
| SC-017–SC-018 | Retained by SC-014: stable identities, supersession and terminal classification for every source part |
| SC-019–SC-020 | Retained by SC-015–SC-016: 13/14 reader-free including `1defc293`, and 4K/8K/16K total-input profiles |
| SC-021–SC-022 | Retained by T005/T044 and SC-015: declared finalization probes and a no-judge paid-run preflight |

## Contradictions resolved

1. **Extend legacy vs replace it**: Spec 038 originally extended `hybrid.py`.
   Spec 040 permits a clean engine and restricts legacy code to A/B/rollback.
2. **Benchmark accuracy optional vs release direction**: Hermes beta packaging
   did not require accuracy. Stable 2.3.8 requires the absolute quality,
   non-regression, governance, performance and product floor in SC-013; matched
   LongMemEval leadership remains the primary research target and a separately
   earned claim, not a safety-release blocker.
3. **Dolphin as optional research vs leadership target**: A usable 2.3.8 package
   does not require the full 600-task spend, but any Dolphin readiness or
   leadership claim requires SC-005/SC-006 respectively.
4. **Model-assisted quality vs local-first**: Models may propose and navigate;
   deterministic safe retrieval and governance remain usable without them.
5. **Full-fidelity evidence vs storage pressure**: Immutable source is stored
   once; every derived view references it and is separately measured/rebuildable.
6. **Benchmark specialization vs product quality**: Every promoted technique
   must pass product-neutral fixtures, installed adapters and performance gates;
   official adapters remain inert.

## Release disposition

- **Must remain in 2.3.8**: Hermes support, MCP registry work, AtFlows secret
  redaction coordination, continuity compatibility, encryption/evidence gates,
  installed cross-platform qualification and release-completion rules.
- **Owned by Spec 040**: new context engine, legacy shadow control, reference
  laboratory, matched LongMemEval comparison, Dolphin development/full claim
  gates, context-engine CLI/MCP/dashboard parity and performance/storage gates.
- **Deferred unless independently ready**: Spec 039 trained reranker promotion,
  broader 2.4 memory-health automation and later multi-agent administration.

## Current-code reconciliation

The repository already contains substantial useful work; Spec 040 does not
pretend it is absent and does not mark new-engine tasks complete merely because
similarly named legacy code exists.

| Existing asset | Disposition under Spec 040 |
|---|---|
| Canonical memory/evidence stores and encryption services | Reuse behind the governance shell after source-range, migration and stolen-store gates pass |
| `atmem/retrieve/` hybrid/rank/semantic paths | Freeze as `legacy-control`; do not import into V3 formation, planning, navigation, sufficiency or packing |
| Hermes/OpenClaw/Pydantic/LangChain adapters | Preserve setup, restore and host boundaries; translate only the shared V3 package after contract tests pass |
| Existing typed evidence and benchmark work from Spec 038 | Reuse fixtures, schemas and measured evidence where identities/provenance match; reimplement behavior inside the clean engine rather than declaring task completion by resemblance |
| `research/production_benchmarks/` LongMem/Dolphin runners | Extend into matched arms and frozen protocols; prior AtMem-only and hosted-Mem0 runs remain historical, unmatched evidence |
| `research/reference_parity/` contracts/source pins | Reuse as the laboratory seed; T002, T003 and T005 are now evidenced. T004 remains open until AgentRunbook-C/V2, encrypted external raw outputs and repeated frozen-hardware measurements complete the baseline |
| Dashboard, CLI and MCP surfaces | Preserve current behavior; V3 status is added only through the shared service and cannot imply activation or qualification |

At specification freeze only T001 was complete. Later checkmarks in `tasks.md`
require executable evidence against the new contracts; prior implementation
reduces effort but is not silently relabelled as passing V3.
