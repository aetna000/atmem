# Current AtMem capabilities and arm ownership

> Historical fixture ownership, not a product capability matrix. The journal and
> reconciliation below live in benchmark code and must not supply the new product
> evaluation. See [product-first correction](../../specs/benchmarking/002-agent-continuity/product-first-correction.md).
> Installed product acceptance and revised arm ownership remain open.

Audit: 2026-09-25, source `3ca2733a4d5b641b8eb887aacf5cd9c6277e0c59`,
AtMem 2.3.7b2. Public runtime candidate: LangGraph 1.2.12 with
langgraph-checkpoint-sqlite 3.1.1; dependencies are benchmark-only.

| Responsibility | Durable baseline | +AtMem | +AtFlows | Both |
| --- | --- | --- | --- | --- |
| Dispatch, retries, graph checkpoint | LangGraph + fixture journal | same | same | same |
| Governed task/item commitments | baseline graph/journal | AtMem host boundary | baseline | AtMem |
| Receipt before graph checkpoint | runtime dispatch journal | same; not second task writer | same | same |
| Destination reconciliation | runtime using declared I/Q/N API | same | same | same |
| Context eligibility | baseline current-policy interface, not yet implemented | AtMem governed interface, not yet integrated | baseline | AtMem |
| Observation | supervisor event collection | same + AtMem task history | AtFlows (integration pending) | both (pending) |
| Final scoring | independent evaluator | same | same | same |

## Verified API mapping

- `TaskStateService.start/get` and `HostBoundary.propose` are the current task
  interfaces. HostBoundary derives the host role and checks enablement, session
  binding, capability and policy; the adapter does not pass an authoritative role.
- Operator fixture setup calls `ScopeEnablement.enable` and
  `SessionBindingService.register` in an isolated store. It never changes user Home.
- `TaskItem.item_id` maps to the stable logical operation; task ID and bound host
  session survive the worker restart. Run and attempt IDs are distinct observer
  records. This is not a complete Spec 020 evidence-envelope adapter.
- Unknown effect leaves `running`; safe unresolved recovery proposes `blocked`
  with a reason. Confirmed receipt supports a host proposal to `completed`.
  No new lifecycle state or automatic task completion is introduced.
- Completion requires cited evidence: the adapter retains the actual receipt in
  an AtMem audit event and cites it. Host observation is not independent proof;
  only the hidden evaluator confirms actual effect counts.

## Explicit gaps and limits

Current smoke measures task-state restart only. Canonical context revocation and
supersession in agent execution, full-fidelity standalone evidence recovery,
cross-machine migration and encrypted-profile evaluation are not implemented by
this fixture. Dedicated temporary SQLite task stores use the existing default
test profile; this is not an encrypted evidence compliance claim. Live public
retail execution and native no-fault equivalence remain gates before G2.

AtFlows' matching audit is `specs/010-continuity-observability/capabilities.md` in
the AtFlows repository. Its raw-attribute preservation is not authenticated
continuity support. Unsupported capabilities must not be synthesized by adapters.
