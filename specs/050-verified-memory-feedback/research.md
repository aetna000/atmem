# Evidence and scope decision

Date: 2026-11-09. Source inspected: upstream `main` at
`1f5c72e0d98dd57a5fba2f836123dd54741db892`, package version 2.3.14.
The user's screenshot describes another architecture and rates AtMem from its
public documentation, explicitly without testing. Its claims about that other
product are unverified. This is a source review, not a fresh runtime audit.
The initial aetnamem checkout was at 70ff078 / 2.3.13; it was not used as the
final version baseline. Work is isolated in `feat/verified-memory-feedback`.

## What already exists and what the chart misses

| Topic | Source evidence | Implication for this feature |
|---|---|---|
| Exact aliases | `atmem/graph/identity.py:IdentityService.resolve`, `tests/test_graph_aliases.py`, `docs/entity-relationship-memory.md` | One active exact subject-scoped match resolves; ambiguity returns review_required. Describing this only as fact-key retrieval is incomplete. This does not establish arbitrary business-record/field authorization. |
| Human review | `atmem/extract/review.py:ReviewAuthorization`, `ReviewPolicy`, `ReviewService.decide` | Action-bearing typed proposals require authenticated scoped review; approval rechecks stale state. Reuse rather than invent another approval queue. Ordinary facts need not all wait for manual approval. |
| Typed memories | `atmem/extract/models.py:MemoryUnitKind`, `atmem/schemas/v2/memory-unit.json` | atomic_fact, durable_rule, environment_state, state_transition, procedure, failure_gotcha, premise_constraint already exist. Counting competing categories is not a quality measurement. |
| Rule-shaped context | `tests/test_context_assembler_v2.py:test_sufficient_rule_becomes_a_structured_action_constraint`, `tests/test_context_engine_retrieval.py:test_rule_evidence_yields_grounded_non_executing_action_constraint` | Evidence can become a structured context constraint. This alone is not execution-boundary enforcement. |
| Actual guard mechanisms | `atmem/action_guard.py`, `atmem/adapters/hermes/action_guard_plugin.py`, `tests/test_action_guard.py` | Existing targeted routing/detour guards and remembered route failures are useful integration points. They do not establish general evidence-to-rule promotion with held-out qualification. |
| Task guard capability | `atmem/task_state/enforcement.py`, `atmem/task_state/guards.py`, `atmem/task_state/host_boundary.py` | Task guards explicitly distinguish detection from prevention. No production register_enforcer call was found in the inspected atmem tree. Do not generalize this finding to the separate action guard. |
| Product invariants | `atmem/invariants/registry.py`, `docs/invariants.md` | Product conformance checks are not user-derived business rules. Preserve this distinction in UI and claims. |
| Retrieval evaluation | `docs/retrieval-quality.md`, `docs/benchmarks/retrieval-2310-evaluation-loop.md`, `specs/046-retrieval-performance-2310/spec.md` | Direct support, abstention and an evaluation protocol already exist. Missing product loop: scoped verified outcomes, per-agent calibration, reusable qualification receipts and operational promotion/revocation. |
| Evidence and privacy | `atmem/evidence/store.py`, `atmem/contracts/models.py`, constitution II/IV | Reuse encrypted retained evidence and existing authority. A signed host statement is not independent verification of a real-world effect. |
| Version difference | `docs/releases/v2.3.14.md` | 2.3.14 is a branding release and explicitly makes no new retrieval or benchmark claim. |

## Prioritized product direction

1. Record what was retrieved, actually delivered, used in an action, and independently
   verified. Diagnose missing evidence separately from evidence delivered but not applied.
2. Show per-agent error, coverage and action outcomes, with sample sizes, verification
   status, cost and regressions. Propose versioned retrieval changes in shadow.
3. Turn only expressible, authorized, qualified memories into narrowly typed tool guards.
   Enforce at one named host boundary first; report advisory-only elsewhere.
4. Offer an explicitly consented, provenance-preserving export of verified examples for
   future training. Training, adapter serving and automatic retraining are separate work.

This closes a concrete operational loop without claiming that retrieval itself is
learning. It does not attempt to reproduce the other architecture's mobile messaging,
legal corpus, business-object ABAC, or transport cryptography from an unverified slide.

## Deferred roadmap

- Separately specify connectors that map real business records and field-level rights
  to the intersection of user and agent authority; no such connector is implied here.
- If the measured rule/retrieval loop is useful, separately qualify consented model
  training against the unchanged native and AtMem baselines, with tenant-isolated
  datasets and served adapters, rollback, and deletion/retraining limitations.
- Owner notification/mobile channels and legal-document versioning are independent
  products, not prerequisites for the first measurable loop.

No model calls, paid experiments, benchmark resumes, publication or user-memory
mutation are authorized or performed by this specification task.
