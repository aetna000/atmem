# Indexing and coding MCP depth: pinned baseline gap closure

2026-10-18. Branch `feature/atmem-code-2.3.9`. Unreleased source preview;
not a performance benchmark, a release, or completion of every CK requirement.
SpecKit convergence tasks T108–T111 track this bounded implementation.

## Delivered

| Area | Current implementation |
| --- | --- |
| Coding MCP depth | Existing `code_search` accepts all eight pinned operations: facts, exploration, traversal, paths, potential impact, architecture, findings and delta |
| Compatibility | Legacy compact search/explore/source/context tools and old disabled memory behavior preserved; four read-only tool names unchanged |
| Traversal | Structured traversal up to 20 hops; bounded nodes, response bytes and scope. Legacy compact explore remains two-hop |
| Input coverage | Rich source policy separated from syntax fallback; additional language, template, protocol, infrastructure and manifest extensions admitted |
| Findings | Incorporated upstream finding conversion, in memory; confidence/metrics/evidence retained; original artifacts remain protected |
| Locations | Actual files retain hashes/spans; directories and Ruby/PHP virtual coupling records are labelled, never assigned invented file spans |
| Maintenance | Atomic generation publication, unchanged no-op, edit invalidation, real reindex deltas, rename cleanup and legacy-generation reads |
| Authority | Existing authorization, scope filtering, secret/encoding limits, offline worker and final transport freshness retained |

Structured responses use additive `atmem-code-query-v1`. Unknown operations,
scope/root overrides, invalid budgets, nonfinite arguments and unsupported
filters are refused. Default response bound is 12,288 bytes; a structured caller
can select 256–131,072. Oversized responses are withheld rather than silently
losing nodes or relationships. CLI and MCP reuse the same query implementation.

The underlying query algorithms remain the licensed pinned incorporation, not
new independent versions. The insight conversion has one mechanical file-access
adaptation (`open(path)` → `path.open`) permitting a read-only in-memory artifact;
no private findings file is created on the host. Import reproduction/check and
the modification manifest retain the source pin and notices.

## Installed qualification

- AtMem wheel SHA-256:
  `280c3c169cfa23f42f9233fe737eb182b628242aafd2b347a4e3c561b88aa351`.
  Every installed package source file was checked against this wheel before
  execution. Metadata remains private-preview 2.3.8, not the published stable
  artifact. Owner installation was not changed.
- macOS/aarch64 CPython 3.12.12; isolated package environment with the already
  qualified SQLCipher 0.6.2, pqcrypto 1.0.0 and cryptography 48.0.1 dependencies.
- Linux/aarch64 offline worker image:
  `sha256:cc9713ee74ce41d7a4ac8a55789920985dab0e9def37f7ffe536d1cde8dbabf6`;
  Enola 0.4.26 / v287. No network, owner mounts or repository-provider commands
  during extraction. This does not prove bit-reproducibility of the binary.
- Query baseline: Cognee `f154b32a9e544dac73e7ddf2010327cf9988edcd`.
- Extractor fixtures: Enola `f2bf59913016ec4fe05ca9ce228f95d6616e1da5`.
- Additional public regression sources: Serena
  `2cb6cabc100539a1364bc243b543e664f0fa8f43`; its `test/resources` component is
  MIT-licensed, not incorporated Serena application code. Its license text and
  selected original bytes are retained in the qualification record. Cognee and
  Enola are Apache-2.0; AtMem's retained notices remain in distributed artifacts.

The fixed admitted control set has **77 original upstream files / 38,826 bytes**:
selected Serena regression sources across 16 input families, Cognee's code-repo
fixture, and Enola's OpenAPI, AsyncAPI, gRPC, Flask, Gin, HCL, Ansible, ORM,
ASP.NET and Laravel fixture sources. These are upstream regression fixtures,
not a production corpus, training data or a coding-task success sample.
Harness size/secret selection happens before extraction; zero exclusions in
the indexed receipt refer to this admitted set, not every file upstream.

| Installed observation | Result |
| --- | ---: |
| Original raw Enola facts | 392 |
| Materialized objects, including derived findings | 422 |
| Retained relationships, including unresolved references | 646 |
| Symbols | 251 |
| Modules | 37 |
| Endpoint objects | 29 |
| Storage objects | 9 |
| Dependency objects | 50 |
| Findings | 35 |
| Extraction accounts | 2 |
| File references | 9 |
| Pinned original-method differential operations | 8 / 8 |
| Independent installed MCP stdio operations | 8 / 8 |
| Stale-source withholding operations | 8 / 8 |
| Model / embedding / paid API calls | 0 |

The differential compiles methods directly from the immutable upstream blob
and compares all eight results on the **actual extracted, authorized state**.
It is an algorithm differential, not a comparison of the two complete storage
backends. AtMem still performs its own admission/mapping and privacy filtering.

A separate fresh Python process opens the installed package/database and serves
real MCP stdio. Initialization, tool discovery and eight tool calls produce ten
bound replies matching the common service exactly. This proves protocol and
installed-service behavior, not a fresh real Copilot/Codex/Claude conversation.

After a real source edit, all eight operations return `not_current`. Reindexing
publishes generation 2, with one changed file and three source-bound updated
objects. A subsequent real file rename publishes generation 3; querying the old
source path returns zero current facts. An unchanged reindex does not run the
worker again. Original-generation results and maintenance receipts are retained.

The separate product regression suite passes **316 tests in 94.60 seconds**.
An additional six-node/five-hop MCP control was added afterwards and is reported
with the final focused verification below; overlapping runs are not added up.

Final focused verification: **100 passed in 56.66 seconds**, including the
six-node/five-hop real MCP-service traversal, index/virtual-location controls,
all operation contracts, original-method differentials and task inventories.
The source-import reproducibility check and `git diff --check` also pass.

## Intentional differences and failures retained

The first source-selection control found a legitimate Ruby virtual coupling
location rejected by the old mapper. The expanded framework control found the
equivalent PHP record and Ansible directory-role symbols rejected as nonexistent
files. These were loader failures, not failed coding-agent solutions. The
original v1/v3 failure records and inputs remain; v2/v4 are separate installed
qualification artifacts. No model attempt was retried or benchmark result
selected. The expanded v3/v4 admitted inputs are unchanged by the mapping repair.

Mappings now recognize only the pinned documented forms and bind their parent
directories to admitted source. Arbitrary out-of-snapshot files remain errors;
unresolved references are not guessed by name. Virtual/directory locations have
no invented source hashes or measured spans. Findings are attributed structural
or heuristic evidence, not verified developer intent or execution.

Delta counts use exact source-bound objects/properties/locations and resolved
edges, with bounded name samples and source-file counts. They are not a claim
of matching upstream fact-hash write counts or incremental-write performance.
Changed graphs are rebuilt atomically rather than promising per-file incremental
storage work. Restricted projections do not expose repository-wide delta counts
or extraction receipts. Old persisted generations without repository metadata
remain readable; reindexing provides the new metadata, with no SQL migration or
canonical-memory rewrite.

## Boundaries still open

- This closes the named pinned-baseline integration gaps, not every feature in
  newer upstream releases. Later operations require a separate pinned intake.
- Selected source fixtures are not exhaustive language/framework accuracy
  evidence. Service, test-reference, intent, association and lint cells not
  emitted in this control remain unqualified, rather than counted as passes.
  Python is exercised by Cognee's own fixture even though the selected Serena
  Python files do not emit symbols. No runtime completeness follows.
- Native Windows rich-source reading, other architecture/interpreter cells,
  complete binary/source reproducibility and transitive SBOM remain separate
  gates. Existing host automation qualification is unchanged.
- Rich extraction stays explicit and optional. `graph-index` remains the
  limited fallback; `knowledge-index --image-id` selects richer indexing.
  MCP registration does not install hooks or enable automatic indexing.
- Normal automatic coding-outcome formation, complete model reconstruction,
  broad Explorer usability, broad parity and coding-quality/token/latency wins
  are not established by these controls. No new agent benchmark was run.

## Evidence and use

`tools/qualify_code_knowledge.py` retains frozen inputs, original artifacts,
generation, complete query answers, maintenance checks and its own source via
the protected evidence service. `tools/qualify_code_mcp_stdio.py` adds exact
independent-process protocol requests/replies.

Internal state: `AtMem Benchmarks/code-index-depth-20261018-v4`.
Evidence run: `code-index-parity-20261018-v1` (v1 names the evidence schema/run,
not the preview build). Keys and protected databases remain internal. The
source controls live only in dedicated qualification workspaces; no owner's
repository or normal AtMem database was indexed or changed.

See [the usage guide](../docs/atmem-code.md#full-structured-code-search) for
typed examples, explicit rich-index setup and agent MCP registration.
