# Implementation plan — Spec 044

## Technical context and constitutional gate

Python 3.10–3.13, existing encrypted SQLite Code documents, source-backed
`CodeKnowledge` projections, `Curation`, MCP stdio, host-specific adapters and
the retained replay harness. No new runtime dependency or authority database.
Reuse 042 authorization/deletion/portable export and 043 isolated source/grading.
The constitution is unchanged. Non-influencing isolated qualification precedes
explicit activation; there is no customer shadow mode. Full-fidelity evidence
remains encrypted, with honest per-boundary coverage and reduced-capture labels.

## Architecture decisions

1. Add `atmem/code/discovery.py`: strict request/result contract and an AtMem
   navigation service over existing Curation. Owner-bound root/scope/provider;
   model input is only opaque request/turn IDs, query, count and byte budget.
   The router is not an automatic prompt injector or generic shell interceptor.
2. AtMem adapter calls authorized `Curation.prepare('discover', kind='code')`
   exactly once; response projection allows only identity, symbol title, source
   location, revision/freshness and non-exhaustive ranking metadata. Never call
   `fetch` for delivery; current Curation may inspect source internally to validate
   candidates, but no body is emitted. Preserve original source-reading tools.
3. Prepare/deliver are separate. Reuse the underlying curation exposure record
   and final `revalidate`/delivery boundary; attach request/response bytes there
   without creating a new document kind. Source changes before delivery withhold
   stale results. Preparation, stream write and model consumption are distinct.
   Keep pending requests bounded and invalidate on failed delivery; no claim that
   an ID retained locally proves a model still remembers it after compaction.
4. Add `atmem/code/discovery_hosts.py`: independent discovery capability model,
   not the old capture-hook registry. Inventory five named hosts, three OSes,
   version, candidate supported transport, actual probe receipts, capability
   state and reason. Default unprobed; a signed configuration or command presence
   cannot self-promote. Do not use a universal guessed hook/flag.
5. Extend `atmem/knowledge/code/mcp.py` with an explicit `navigation` profile
   exposing just `repository_discover`; keep expanded/compact/curated contracts
   unchanged. Update `atmem/code/knowledge_setup.py`, CLI profile choices and
   generated configuration consistently. The profile alone is optional discovery,
   not a routed-host integration. Scope is supplied by the operator, never tool
   arguments. User selects it explicitly; old settings are not migrated.
   Configuration warns if existing automatic recall is enabled. Discovery-only
   activation explicitly sets `auto_recall=false` through existing CLI/dashboard
   controls, without disabling capture or silently changing prior user settings.
6. Implement supported host-specific routing only after official source/installed
   version research and isolated positive/negative probes. Prefer native tool
   controls/SDK interfaces with supported subscription authentication. A launcher
   is optional setup packaging, not proof of replacing host internals. If a host
   cannot mediate navigation, expose optional discovery and an explicit blocker;
   do not fake routing with deny/retry or paid API fallback.
7. Native baseline has ordinary legitimate search/read/edit/test behavior. The
   controlled-backend experiment separately supplies the same `repository_discover`
   contract to native lexical search, pinned upstream Cognee, or AtMem. Native
   literal/regex search remains separately named; no ranked result masquerades as
   an exhaustive search. Actual Cognee uses its own pinned SDK/extractor/index,
   not AtMem's vendored queries. Validate public result fields, scope, freshness,
   budgets and failure behavior at the common gateway. No experience in primary
   discovery-only runs, no learned pruning and no automatic source packs.
8. Trace requested versus executed discovery, every exact delivered result/error,
   fallbacks, source read ranges and overlaps. Use existing encrypted evidence;
   aggregate only measurements visible at captured boundaries. Shell reads not
   observed cannot be inferred absent. Host/model alias and drift are recorded.

## Host qualification matrix (initial state, not a support claim)

| Host | Candidate boundary to research | Before real probe |
|---|---|---|
| Claude Code | Supported native tool inventory/hooks or supported agent interface | unprobed |
| Codex | Supported CLI/app-server tool integration and subscription sign-in | unprobed |
| Copilot CLI | Native CLI controls or supported SDK interface; distinguish the two | unprobed |
| Muse Code | Actual installed product/version and documented extension/hook contract | unprobed |
| Grok Code | Actual installed product/version and documented extension/hook contract | unprobed |

Each host has separate Darwin, Windows and Linux cells. Isolated fixture tests
do not populate real-host pass cells. Record optional discovery separately from
routed navigation. Failures are capability outcomes, not grounds to rename a
different agent or change a provider behind the user's subscription.

## Delivery phases and dependencies

0. Freeze requirements, contracts, budget and preregistration; run read-only
   SpecKit consistency/coverage analysis. Review prior negative evidence and
   parent-spec compatibility. Resolve critical/high issues before product code.
1. Implement/test strict contracts, AtMem projection and delivery revalidation,
   independent host capability inventory, no data migration and no network.
2. Expose explicit navigation MCP/CLI configuration and dashboard mode/status;
   test installed artifact, scope/privacy and unchanged prior profiles.
3. Qualify five host adapters locally without touching real host config. Only
   promote exact tested cells. Unsupported routing is recorded; test the remaining
   hosts rather than silently assuming equivalence. Keep supported subscriptions.
4. Build common discovery comparator and complete trace/usage/read-overlap
   measurement. Freeze native/Cognee/AtMem backends, license/pin/source policies,
   prompts, tool schemas, budgets, model identities and trial accounting.
5. Run Click smoke first on one predeclared task, then the remaining four: 45
   cells if all three scoring hosts qualify. Rotate backend order by a frozen
   task/host schedule; no favorable-result retries. Grade after all attempts in a
   task/host block terminate. Exposed tasks remain diagnostic.
6. Prepare SWE-bench Verified manifest and independent qualification/confirmation
   partitions. Validate official grader/reference controls, container isolation,
   extraction/import policies and complete evidence with zero model dispatch.
   Measure resource needs and quota before any rental. Freeze after local pilot
   changes; never tune on confirmation outcomes.
7. Execute predeclared qualification/held-out/full-target matrix only through
   resource/receipt gates and a conservative USD 6 campaign cap. No separate API
   billing. Rent Vast.ai only if local resources are inadequate and the estimated
   work plus storage/transfer/teardown reserve fits. GPU is justified only by an
   actual GPU workload or cheaper usable offer, not by coding-model branding.
   Capacity insufficient for the full target produces a partial report, not a
   misleading full score; stop dispatch and destroy owned rentals at the cap.
8. Publish all raw/aggregate outcomes, missing cells, paired task results and
   uncertainty; retain encrypted originals, verify readable derivatives and
   dataset licenses. Push code/docs to GitHub feature branch; large evidence to
   AtMem Hugging Face with immutable upload receipts. No release or `main` change.

## Planned artifacts

- `contracts/discovery-v1.md`: request/response, status/fallback and delivery semantics.
- `benchmark-protocol.md`: experimental units, task manifest, two comparison
  regimes, metrics, missing-data rules, spending and promotion gates.
- `tasks.md`: dependency-ordered work with FR/SC mappings.
- `atmem/code/discovery.py`, `atmem/code/discovery_hosts.py` and additive MCP/CLI/UI wiring.
- `tests/test_code_discovery.py`, `tests/test_code_discovery_hosts.py`, host probes
  and compatibility/portable/deletion tests.
- `benchmarks/code_replay/discovery_study.py`, `discovery_metrics.py` and
  `discovery_campaign.py`: comparator execution, measurement and bounded ledger.
- `tools/qualify_discovery_hosts.py`, `tools/freeze_discovery_campaign.py`,
  `tools/report_discovery_campaign.py` and campaign-owned rental guards.
- `RandD/`: exact local qualification and benchmark status/results; no fabricated rows.

## Validation and stopping conditions

Malformed/unsafe requests invoke zero backend calls. Discovery responses pass
allowlist schema, serialized byte bounds, no-body tests and real stale-delivery
tests. Prior Code operations/settings/export/delete stay compatible. Local fixture
tests are not efficacy evidence. A real host boundary must prove navigation,
native reads, edit/test survival, failure recovery and captured usage before a
scored run. Missing complete usage means token advantage unknown, not zero.

There is no promise that USD 6 funds the complete full matrix. Before provisioning,
calculate remaining rental credit and conservative per-task resource time from
the measured pilot. User subscriptions have their own quota, access and model
availability, which are not inferred from a binary or login file. A resource or
host-authentication blocker is recorded explicitly and never bypassed.
