# Frozen source-incorporation and capability register

Frozen baseline date: 2026-10-17. Initial table states below are historical;
the 2026-10-18 addendum supersedes them for the named tested cells. This is
coverage scope, not a blanket parity or release claim.

## Pins and provenance

- Cognee: `f154b32a9e544dac73e7ddf2010327cf9988edcd`, Apache-2.0.
  Import manifest, exact source hashes and modifications: `third_party/cognee/`.
  `tools/import_code_knowledge.py` reproduces the narrow pure source import and
  `--check` verifies its bytes. Backend, model/session interpretation and TTL
  caching are deliberately not imported; AtMem supplies authorized snapshots.
- Enola source: tag `v0.4.26`, commit
  `f2bf59913016ec4fe05ca9ce228f95d6616e1da5`, Apache-2.0.
  Dependency: optional pinned `enola-cli==0.4.26`, extractor version `v287`.
  Inspected macOS x86-64 binary SHA-256:
  `9e603435d07aaac5b6fe80631d9c03a9d7b64bc82dd85faa1154e78efb1c416b`.
  Go build metadata says `v0.4.26+dirty`: source/binary reproducibility is NOT
  established by matching the version string. This remains a qualification gate.
  Python wheel has no Python dependencies; native Go module dependencies are
  declared in that source's `go.mod`/`go.sum`. Full transitive notice/SBOM and
  installed-platform audit remain T045/T059 gates, not blanket clearance.
- Current AtMem base: stable 2.3.8 commit
  `267c5b3ac08e8cac26dfee13c6eac2842d4bb876`; Code worktree base
  `afdefbb` plus explicitly recorded local changes. Neither is a new release.

## Source-to-capability coverage

All rows below are required baseline cells. `incorporated-unqualified` means
source exists, not that installed product acceptance or differential tests passed.

| Capability | Upstream source/test reference under pin | Decision / AtMem target | State |
| --- | --- | --- | --- |
| Fact/receipt parsing and quality | `tasks/code_graph/enola.py`; `tests/unit/tasks/code_graph/test_enola_contract.py` | Adapt stricter fail-closed parser in `knowledge/code/extractor.py` | Pending |
| Typed facts/relations | `tasks/code_graph/models.py`, `extract_code_graph.py`; `test_enola_contract.py` | Map writer IDs/source locations into scoped contracts; do not collapse ambiguous names | Pending |
| Fact filters | `modules/retrieval/code_retriever.py:CodeRetriever._query_facts` | Incorporate pure query algorithms under `knowledge/_vendor/` | Incorporated-unqualified |
| Explore / dependencies | `CodeRetriever._explore`, `_traverse` | Same algorithms plus bounded authorized wrapper | Incorporated-unqualified |
| Find path | `CodeRetriever._find_path` | Same algorithm; authority filtering before graph construction | Incorporated-unqualified |
| Potential impact | `CodeRetriever._impact_analysis` | Preserve candidate/coverage semantics, not runtime guarantee | Incorporated-unqualified |
| Architecture | `CodeRetriever._architecture`; `code_graph_diagram.py` | Retain deterministic summaries/rendering behind wrapper | Incorporated-unqualified |
| Insights | `CodeRetriever._insights`; Enola insights contract | Attributed rule/heuristic findings, not verified intent | Incorporated-unqualified |
| Snapshot deltas | `CodeRetriever._delta`; write-side `extract_code_graph.py` | Reuse query; AtMem owns atomically published snapshot metadata | Pending write side |
| Incremental/hash handling | `snapshot_identity`, write-side stale sweep | Adapt into AtMem encrypted lifecycle/outbox, not second store | Pending |
| Source/worker security | Enola `internal/providers/`, `internal/config/`, `internal/updatecheck/` | Replace environment/config inheritance with explicit isolated job and no-network boundary | Pending |
| Experience formation/applicability | Existing AtMem authority and Code scopes | Extend AtMem; not supplied by pure graph import | Pending |
| Memory Explorer | Existing Code application/dashboard; Spec 022 shell | Extend one product surface, preserve navigation and role semantics | Pending |

Upstream vocabulary includes repository plus module, symbol, route, storage,
dependency, service, test_ref, file_ref, insight, intent, extraction, association
and lint. Do not discard a vocabulary cell silently or count unknown kinds as
recognized. Relation assurance, unresolved references and duplicate writer IDs
must survive ingestion or receive explicit rejection/coverage receipts.

## Language/framework/platform envelope

Enola's pinned extractor registry includes Python, TS/JS, Go, C/C++, .NET,
Java, Kotlin, PHP, Ruby, Rust, Scala, Swift, Dart, OpenAPI, AsyncAPI, gRPC, HCL,
Ansible, dependency manifests and Markdown intent. These remain unqualified
AtMem cells until tested. Python is the first vertical slice, not full parity.
Framework-specific routes/storage/test relationships are qualified separately;
no runtime link is inferred merely from syntax or filenames. macOS, Windows and
Linux installed artifacts remain separate cells; local macOS discovery does not
qualify another platform or a coding-agent hook.

## Non-negotiable adaptations and evidence gates

Enola can run configured external providers. The wrapper must not inherit a
repository's provider commands or execute its build/test scripts. Strip such
configuration in an authorized source-only staging job, pin the binary identity,
disable update checks/prompts and impose network/filesystem/resource limits.
Do not run the stock generator on arbitrary owner repositories or leave `.enola`
plaintext output on disk. Private derived artifacts must use the protected
AtMem boundary; ephemeral extraction occurs in a declared isolated memory workspace.

Differential tests must compare licensed upstream behavior on identical input,
then add independent source-anchor/authorization tests. Pure algorithm import,
a successful empty query and this register do not establish parity. T043 records
the inventory; T045–T047/T053/T059 retain implementation and qualification gates.

## Current indexing/MCP depth — 2026-10-18

T108–T111 close the newly identified integration gaps against the same pinned
baseline, without declaring the entire CK expansion complete:

- All eight operations are now exposed through additive `code_search`
  operation/arguments fields. Legacy compact searches and the other three
  read-only tools remain compatible. Traversal supports up to 20 hops with
  bounded nodes, bytes, scope and final-delivery freshness.
- Rich capture admits additional pinned language/manifest/template/protocol
  inputs instead of relying on the old syntax index's extension list.
  Scope, ignores, source/encoding limits, secret screening and offline workers
  still apply. The fallback is not relabelled as rich extraction.
- The pinned upstream insight conversion is incorporated at an in-memory
  boundary; confidence, metrics, finding evidence and original artifacts are
  retained. Ruby/PHP coupling virtual locations and Ansible role directories
  have constrained mappings, not invented file spans or broad path bypasses.
- Repository receipts and exact source-bound generation deltas are queryable.
  Unchanged snapshots skip extraction; changed snapshots rebuild atomically.
  Delta write-count semantics intentionally differ from upstream fact hashes.
- Installed macOS/aarch64 CPython 3.12.12 + Linux/aarch64 worker controls on
  pinned upstream regression sources publish 422 objects / 646 relationships,
  including 29 routes, 9 storage resources and 35 findings. All eight original
  upstream algorithm comparisons pass on that real extracted state. All eight
  operations also pass an independent installed stdio process check. Edit,
  reindex and rename controls pass without model calls.

This does not qualify all language/framework combinations, native Windows
source reading, every host's automatic graph integration, binary/source
reproducibility, complete dependency SBOM, usability or broad coding benefit.
The [detailed report](../../RandD/2026-10-18-code-index-mcp-depth.md) records
inputs, exact artifacts, earlier loader failures and remaining gates.
