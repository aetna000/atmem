# Implementation review for the unified AtMem product

**Date**: 2026-09-09 (Australia/Sydney)
**Inspected base commit**: `793a00d6c03d92b505903624fa1ece1403e3231a`
**Scope**: Specs 001–018, associated plans/tasks, and targeted implementation paths relevant to native memory, provider governance, execution evidence, onboarding and production operation.

## Method and limits

This is an architecture and integration-gap review, not a fresh certification of every historical requirement or a full security/performance audit. Existing `[x]` task marks and old test reports are retained as historical evidence; they were not all rerun. New amendment and new-feature tasks are unchecked. Source paths mentioned in future plans may be proposed files. No application implementation or release is delivered by this specification pass.

The source was inspected directly in `atmem/control/blackbox.py`, `atmem/control/manager.py`, `atmem/investigate.py`, `atmem/service/application.py`, `atmem/contracts/versions.py`, `atmem/provider_adapters/mem0.py`, `atmem/server/config.py`, `atmem/server/auth.py`, `atmem/onboarding.py` and `atmem/invariants/attestation.py`, alongside feature documentation, plans and task inventories. The code base is newer than the archived Mem0 comparison; that archive remains a historical snapshot.

## Confirmed findings

| Finding | Evidence | Consequence and owner |
| --- | --- | --- |
| Existing flight verification distinguishes missing tool completion and tool error | `atmem/control/blackbox.py::verify_flight`, `flight_attention` | Reuse for Spec 021; do not build another independent verdict engine. |
| Full execution correlation is still planned | Spec 007 Amendment B has 20 unchecked tasks; `atmem/contracts/execution.py` and `atmem/investigation/` are not present in the reviewed tree | Complete 007 contract/link prerequisites, then extend through 020. |
| Exact execution identifier lookup already exists | `atmem/control/manager.py::_execution_identifier_result` | Preserve it; an indexed job/attempt graph and incident model are still required. |
| Native and delegated retrieval are separate authority paths | `atmem/delegated/`, `atmem/provider_adapters/`, existing 003/004 contracts | Spec 019 unifies packaging and evidence without conflating authorization or rewriting signed v1. |
| The previously reported Mem0 dependency gap has changed | Current `pyproject.toml` permits `mem0ai>=2.0.20,<3` | Do not create a duplicate dependency-fix task from the earlier archive; retain installed provider conformance as a gate. |
| Public service supports memory-centric operations but lacks complete job/incident resources | `atmem/service/application.py` | Spec 012 adaptation plus 019–021 public resource services. |
| Framework capability table includes static exact-injection flags | `atmem/contracts/versions.py::FRAMEWORK_ADAPTERS` | Spec 011/020 must distinguish supported capability from observed and verified deployed coverage. |
| Onboarding uses unconditional memory verification | `atmem/onboarding.py::activate` requires capture, paraphrase, context, evidence and restore | Spec 017/022 need adoption-specific gates so investigation needs no memory migration or model. |
| Production key authority is in-memory | `atmem/server/auth.py::KeyAuthority._keys` | Spec 013 must harden durable revocation and actual route/job enforcement before 024 fleet claims. |
| Existing UI ownership conflicts with the requested navigation | 007 FR-041, old plans, ownership file and dashboard design language mandate four workspaces | Explicit target amendment transfers shell ownership to 022, with six routes and legacy redirects. |
| Acknowledgment and run evidence exist, but the proposed resolution lifecycle is broader | Current Black Box/attention surfaces versus proposed incident/remediation/verification states | Spec 021 owns independent state axes, late evidence and safe next-action prerequisites. |

## Review of Specs 001–018

Each amendment includes feature-specific requirements, acceptance criteria, a plan and three new unchecked tasks. The statement “foundation exists” does not certify all historical success criteria, live integrations or production load targets.

| Spec | Reviewed foundation / gap | New traceability |
| --- | --- | --- |
| [001](001-memory-quality-benchmarks/spec.md) | Existing isolated memory benchmark and matched external reports; local/hosted AtBot evidence remains open (T028–T029). | FR-019, FR-020, SC-009; T030–T032 |
| [002](002-supporting-evidence-ranking/spec.md) | Governed supporting-evidence aggregation exists; it is a retrieval signal, not causal incident evidence. | FR-018, FR-019, SC-008; T021–T023 |
| [003](003-delegated-context-provider/spec.md) | Signed exact-byte delegation, replay protection and exposure evidence exist; independent enterprise content authorization is a different mode. | FR-032, FR-033, SC-012; T046–T048 |
| [004](004-context-provider-adapters/spec.md) | Mem0/framework provider adapters exist; current dependency permits Mem0 2.0.20; there is no common native/external governance adapter yet. | FR-021, FR-022, SC-009; T033–T035 |
| [005](005-semantic-setup-and-health/spec.md) | Staged epochs and health states exist; semantic health is specific to native retrieval. | FR-011, FR-012, SC-006; T010–T012 |
| [006](006-memory-extraction-and-updating/spec.md) | Typed admission, review and immutable correction lineage exist. | FR-012, FR-013, SC-005; T010–T012 |
| [007](007-governed-task-state/spec.md) | Task authority and binding exist; Amendment B still has 20 unchecked tasks, including indexed execution/investigation contracts. | FR-069, FR-070, SC-041; T107–T109 |
| [008](008-retrieval-quality-and-reranking/spec.md) | Shared native support classification and fallback exist; external ranking must remain provider-owned. | FR-021, FR-022, SC-009; T017–T019 |
| [009](009-entity-relationship-memory/spec.md) | Derived entity/path evidence exists; it is not an execution impact graph. | FR-008, FR-009, SC-005; T009–T011 |
| [010](010-production-storage-backends/spec.md) | Canonical/derived protocols and caches exist; broad production completion is not established by this focused review. | FR-014, FR-015, SC-006; T011–T013 |
| [011](011-framework-adapter-conformance/spec.md) | Native framework hooks and callbacks exist; static capability declarations do not prove a deployed host exercised a boundary. | FR-011, FR-012, SC-006; T010–T012 |
| [012](012-http-api-and-typescript-sdk/spec.md) | Shared application facade and clients exist; execution, incident and resolution services are not exposed as one public surface. | FR-013, FR-014, SC-006; T010–T012 |
| [013](013-production-service-profile/spec.md) | Configuration, keys, jobs and recovery primitives exist; KeyAuthority stores keys in memory, so durable fleet authentication is not proven. | FR-010, FR-011, SC-005; T009–T011 |
| [014](014-memory-migration-interoperability/spec.md) | Explicit archive migration exists; switching context providers should not require it. | FR-010, FR-011, SC-005; T009–T011 |
| [015](015-memory-lifecycle-controls/spec.md) | Canonical lifecycle and invalidation registry exist; provider-wide source exposure impact and grants are extensions. | FR-011, FR-012, SC-005; T009–T011 |
| [016](016-governed-multimodal-memory/spec.md) | Host-custodied references and derived observations exist. | FR-011, FR-012, SC-006; T010–T012 |
| [017](017-guided-onboarding-and-health/spec.md) | Resumable setup exists; activate currently requires capture/paraphrase/context/evidence/restore checks for every path. | FR-010, FR-011, SC-006; T010–T012 |
| [018](018-cross-cutting-invariants/spec.md) | Invariant registry and attestations exist; new product boundaries need executing assertions and declared deployment coverage. | FR-012, FR-013, SC-006; T015–T017 |

## New ownership

- 019: shared provider package and context-policy/delivery-grant contract.
- 020: durable execution/attempt evidence and actual coverage, extending 007.
- 021: deterministic incidents, impact, explanations and resolution.
- 022: six-section workspace and three adoption journeys.
- 023: context revocation, source exposure impact and policy simulation.
- 024: optional enterprise fleet, deployment and independent evidence operations.

## Baseline verification performed

```sh
python -m pytest tests/test_blackbox.py tests/test_provider_integration.py tests/test_onboarding.py tests/invariants/test_attestation.py -q
```

**Result: 20 passed.** This verifies the selected existing foundations only. It does not prove the new specs or real-host/production completeness. No live provider, customer data, external payment action or release was used.

## Specification validation

- All 24 feature directories contain `spec.md`, `plan.md` and `tasks.md`; structural checks found no broken local Markdown links, duplicate task IDs or unbalanced code fences.
- Specs 001–018 received 54 new unchecked integration tasks. Specs 019–024 received 102 new unchecked tasks: **156 added tasks** in total. All 360 pre-existing task rows were compared with the base commit and preserved verbatim.
- New-feature requirements and success criteria are referenced in their plans and tasks. These are planned acceptance gates, not evidence that the capabilities are implemented.
- Spec Kit prerequisite validation succeeded for the next working feature, Spec 020.
- `python -m pytest tests/test_documentation.py tests/invariants/test_attestation.py -q`: **17 passed**. This suite overlaps the baseline invariant test above; the counts are not a unique combined test count.
- `git diff --check -- specs docs/dashboard-design-language.md` passed.

## Remaining implementation limitations

Spec 001 retains T028–T029 local/hosted AtBot profile evidence. Spec 007 retains its 20 unchecked Amendment B tasks. Historical completed tasks are not renumbered or reset. Added integration tasks do not replace these requirements. No future feature is marked implemented because its documents were generated.

The constitution remains unchanged. Its Principle VII explicitly permits a separately named delegated-authority mode; this does not let external providers mutate native canonical memory. Session/run correlation identifiers are bound to authenticated scope and do not themselves grant access.
