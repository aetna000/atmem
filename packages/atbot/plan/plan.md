# AtBot companion implementation plan

Updated: 30 August 2026

## Outcome

AtBot becomes a headless, local-first intelligence companion installed and
managed by AtMem. It performs Mem0-like inference and ranking but never becomes
an independent product agent, authority store, or dashboard.

## Migration decisions

- Remove `atbot task` from the supported CLI.
- Recast `atbot chat` as a development-only memory-query diagnostic, then move
  customer query entirely into the AtMem dashboard.
- Stop presenting or serving the standalone AtBot UI.
- Remove the legacy agent loop, task tools, direct database gateway, and
  independent authority configuration.
- Add companion protocol endpoints for health, extraction, query expansion,
  eligible-candidate ranking, and memory-query answering.
- Do not create a separate AtBot canonical database in companion mode.

## Workstream 1: companion protocol

- [x] Add versioned health and capability negotiation.
- [ ] Add typed extraction request/result.
- [x] Add content-free query-expansion request/result.
- [x] Add eligible-candidate ranking request/result.
- [x] Add dashboard memory-query request/result.
- [x] Require immutable candidate-set membership and return record IDs only.
- [x] Add deadlines, payload limits, local-only binding, and structured errors.

Exit: AtMem can call AtBot without importing Pydantic AI and invalid output
degrades safely.

Semantic retrieval correction:

- [x] Expose bounded query-only expansion on the companion protocol.
- [x] Send no candidate content during expansion.
- [x] Have AtMem run original and expanded queries through governed lexical,
  canonical fact-key, graph, and local-vector candidate generation.
- [x] Merge and deduplicate candidates before AtBot ranking.
- [x] Prove `fav food` retrieves `likes burgers` while unknown returned IDs are
  still discarded.

## Workstream 2: companion-only runtime

- [x] Isolate memory intelligence in the headless companion runtime.
- [x] Make Qwen/Ollama the default and deterministic rules the fallback.
- [x] Remove general task execution from public CLI and service routes.
- [x] Remove the legacy independent-agent and task-capability implementation.
- [x] Remove direct AtMem database access and the AtMem package dependency.
- [x] Remove ownership of canonical memory and independent workspace identity.
- [ ] Enforce AtMem-declared scope, sensitivity, egress, model, and budget.

Exit: AtBot cannot operate as a customer task agent or mutate memory directly.

## Workstream 3: unified AtMem interface

- [x] Retire standalone AtBot web assets from the served product.
- [x] Move chat-style query into the AtMem dashboard.
- [x] Return answers with used-memory summaries and fallback status.
- [x] Show thinking, retrieval, companion-unavailable, and retry states.
- [x] Adopt AtBot's dark minimal visual language across AtMem.
- [x] Preserve every AtMem status, decision, provenance, deletion, storage,
  topology, Safe Switch, restore, Black Box, and audit action.

Exit: users need only the AtMem dashboard.

## Workstream 4: installation and lifecycle

- [ ] Define the pinned AtMem–AtBot compatibility matrix.
- [ ] Make AtMem installation verify or install the companion package.
- [x] Start an installed/configured AtBot on dashboard launch and expose health.
- [ ] Detect local models without silently downloading one.
- [ ] Provide explicit model setup actions.
- [ ] Add start, stop, restart, upgrade, and diagnostic commands through AtMem.
- [ ] Never enable remote egress automatically.

Exit: one AtMem setup command leaves authority and intelligence ready or shows
an actionable degraded state.

## Workstream 5: adapters and evaluation

- [ ] Keep the existing OpenClaw–AtMem adapter contract stable.
- [ ] Route AtBot intelligence behind AtMem without changing host authority.
- [ ] Preserve OpenClaw shadow, multi-agent, activation, restore, and flight tests.
- [ ] Publish a host-neutral adapter conformance kit for Hermes and others.
- [ ] Evaluate extraction, ranking, poisoning, scope isolation, fallback,
  latency, cache stability, and deletion propagation.

Exit: OpenClaw is the green reference adapter and another fake/generic adapter
passes the same intelligence and authority suite.

## First implementation slice

1. Remove public independent-task mode.
2. Add AtBot companion health and authorized-candidate query endpoints.
3. Add the AtMem companion client with safe fallback.
4. Add chat-style memory query to the AtMem dashboard.
5. Apply the dark AtBot visual language without removing AtMem controls.
6. Add protocol, UI, fallback, and regression tests.
