# Evidence discovery in 2.3.10b1

Give an agent a bounded way to look up missing details instead of assuming the
first memory packet is complete. The new read-only tools return original,
scoped source passages and provenance. The agent still interprets the evidence
and chooses its actions; AtMem controls access and memory state.

This is an **opt-in beta SDK/host integration**, not a change to ordinary
`remember`/`recall`, Code hooks, OpenClaw setup, or the default retrieval profile.
Stable users can stay on [2.3.9](releases/v2.3.9.md).

## 1. Install in a separate environment

These commands apply once 2.3.10b1 is published; source preparation alone does
not make the beta available from a package registry.

Use Python 3.10–3.13. On macOS/Linux:

```sh
python3 -m venv .venv-beta
source .venv-beta/bin/activate
python -m pip install --upgrade --pre "atmem[encrypted]==2.3.10b1"
atmem --version
```

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv-beta
.\.venv-beta\Scripts\Activate.ps1
python -m pip install --upgrade --pre "atmem[encrypted]==2.3.10b1"
atmem --version
```

The beta pins AtBot 0.1.1 and AtFlows 0.1.4. It does not install Torch, download
a model, enable remote calls, or activate agent injection. Platforms without a
SQLCipher wheel need its compiler/development prerequisites.

## 2. Run a model-free example

Download [the example](../examples/evidence_discovery.py) from this release's
source tree. Run it from any directory with the beta environment active:

```sh
python evidence_discovery.py --database ./discovery-demo.db --text "Our deployment channel is #engineering." --query "deployment channel"
```

Choose a **new** database path on every run. The example creates an encrypted
household with file-backed keys next to it, imports only the supplied text under
an explicit local-owner authority, freezes its source generation, and searches.
Keep that database and its key files out of version control. It does not capture
an agent conversation or demonstrate full Agent Black Box coverage.

The response identifies `format: atmem-evidence-discovery-v1`, includes original
`evidence[].text` and `source_range`, and declares `sufficiency: not_assessed`.
An evidence passage is not a verified answer or permission to act.

Add `--mcp` to the same command to expose only `memory_search` and
`memory_inspect` over standard-input/output MCP. Initialize the server, list its
tools, then search or inspect a returned unit ID. The example process owns the
session; restarting it cannot restore or extend the previous session's budget.

## 3. Integrate an existing authorized host

Use `Memory.open_evidence_discovery(request, authorize=..., budget=...)` with a
typed `ContextRequestV3` and `NavigationBudget`. Keep the `Memory` instance open
for the session. The application supplies and rechecks the authenticated scope;
never let a model choose tenants, authorization callbacks or provider factories.
Wrap the session in `EvidenceDiscoveryMCP` when the host uses MCP.

For Hermes, `HermesService.open_discovery(...)` is an administrator-only host
operation. The binding must already be active, influencing and configured for
`context-v3`; setup does not silently convert an existing binding. It creates a
15-minute-or-shorter lease with shared persisted bounds: eight operations,
96,000 response bytes and 16,000 bytes per response. The authenticated agent
uses authenticated `POST /v1/hermes/discovery-search` with
`{"lease_id":"<host-issued lease>","query":"<focused query>"}` or
`POST /v1/hermes/discovery-inspect` with
`{"lease_id":"<host-issued lease>","unit_id":"<returned evidence ID>"}`.
The host can provision the connection file and scoped credential for
`python -m atmem.adapters.hermes.discovery_stdio CONNECTION_FILE` to expose
these operations as MCP tools. `HermesRPCClient` does not have named discovery
methods. The agent cannot mint or reset its own lease.
Binding disable/revocation and source-generation changes invalidate access.

These are trusted Python host interfaces. They are not a new dashboard switch or
a promise that every supported coding CLI automatically uses the tools.
See the [wire/authority contract](contracts/evidence-discovery-v1.md).

## Optional meaning-based nominations and source interpretation

For the explicitly configured native vector backend, add:

```sh
python -m pip install --pre "atmem[encrypted,context-retrieval]==2.3.10b1"
```

`context-retrieval` pins `sqlite-vec==0.1.9`; it is not an embedding model.
The selected connection must support SQLite extension loading. Some macOS
Python builds omit that capability; use the encrypted SQLCipher backend shown
here or an extension-enabled Python build. An unsupported runtime fails with
an explicit capability error, without silently changing retrieval backends.
`SemanticIndex` provides a bounded persistent LSH index inside the encrypted
canonical database. `SQLiteExactSemanticIndex` is a separately selected exact
backend capped at 100,000 vectors. Build the former only in a building generation,
before verification/freeze, using explicitly authorized IDs and pinned embeddings.

`SourcePartSemanticIndex` and `SourceCoherentHybridFactory` use a separate
encrypted, rebuildable cache capped at **10,000 vectors**. Its builder requires an
explicit local `OllamaEmbedder(..., truncate=False)` with a verified model digest.
Provide your own authorized source manifest and cache directory, build it before
querying, and explicitly supply the factory to the host. There is no automatic
model pull, first-query embedding build, paid fallback or scalable-ANN claim.

The cache registers with the canonical household. Source/generation deletion,
subject reset and relevant forget operations purge registered derived rows;
missing/unverifiable caches stop verified deletion instead of reporting success.
Retired or changed source generations cannot serve a retained cache object.
Reopening a known pre-registry research cache adopts it; unknown old research
directories are not discoverable automatically. Inventory or discard those
disposable caches before relying on a new release's deletion receipts.

AtBot's `assess_memory_state` / source-state endpoint can classify exact supplied
quotations for current, historical, future or conditional applicability.
Remote providers require explicit configuration and egress permission. Their
interpretations remain fallible proposals, never canonical truth or mutation
authority. Initial annotations/dossiers, source bundles and date frames are
separate host-selected options, not the default or an accepted quality claim.

## Compatibility and recovery

- No default profile or Code capture/injection behavior changes. Disable the
  optional integration to return to the existing deterministic path.
- Keep a verified, quiescent copy of an existing Home/database **before** an
  upgrade. Test on the copy first; do not downgrade a live modified Home in place.
- Existing 2.3.8/2.3.9 data uses the normal schema migration path. Optional cache
  registration reuses the existing registry; there is no mandatory embedding rebuild
  for an installation that never enabled semantic discovery.
- Restore the preserved pre-beta copy when rolling back to 2.3.9. Keep original
  evidence and keys together; optional caches are disposable, not memory authority.
- Invalid schema, revoked scope, stale generation, budget exhaustion or unavailable
  providers produce explicit errors/degradation. They do not widen access.
