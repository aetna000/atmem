# AtMem Code

### Packaged Code preview: 2026-10-19

The current branch adds packaged graph-worker resources, saved extractor
configuration, generated read-only MCP configuration, an explicit local command
producer and experience inspection. This is an unreleased preview, not a claim
that every coding host automatically captures source-bound execution experience.
The package metadata still uses the 2.3.8 base version; use a dedicated virtual
environment and the supplied preview wheel, not a plain PyPI upgrade command.
No Laya model, Cognee SDK, embedding model or GPU is required by these paths.

#### Set up the richer graph once

After the existing encrypted household and project setup described below:
add `--db /path/to/memory.db` to commands if using a non-default household.

```sh
# Write the packaged build recipe; does not build, download or execute it.
atmem code knowledge-worker ./atmem-extractor
# Explicit network/build step, when you choose to install the optional worker:
docker build -t atmem-code-extractor ./atmem-extractor
docker image inspect --format '{{.Id}}' atmem-code-extractor

# Paste the resulting immutable sha256 ID. Configuration does not enable hooks.
atmem code knowledge-config --project /path/to/project --image-id sha256:YOUR_IMAGE_ID
atmem code config --project /path/to/project --set '{"graph_enabled":true}'
atmem code knowledge-index --project /path/to/project
atmem code mcp-config --project /path/to/project
```

For a smaller optional MCP interface, generate configuration with
`atmem code mcp-config --project /path/to/project --tool-profile compact`.
This advertises one read-only `code_query` tool instead of the expanded tool
catalog. Its `operation` selects `context`, `search`, `source`, the eight graph
operations, or `experience` when enabled; `arguments` carries the existing
operation parameters. For example, `{"operation":"context","arguments":{"query":"request routing"}}`
or `{"operation":"source","arguments":{"path":"src/app.py","line_count":30}}`.
Existing generated configurations remain expanded. Scope, source checks, result
formats, default context budgets and stored evidence are unchanged. The compact
catalog reduces interface size; total coding-token savings require separate
agent evaluation and are not yet established.

`code_context` accepts up to 4,000 UTF-8 query bytes and rejects larger input
with an actionable error. It does not silently cut a long query to its first
1,000 bytes. Compact symbol-search limits remain unchanged. Source-pack output
budgets are separate from this input bound.

Add the returned `configuration.mcpServers.atmem_code` entry to a compatible
client's MCP configuration. This command does not modify the client. The server
uses the installed interpreter in isolated mode, with fixed project/scope/root;
tools cannot supply new database paths or execute commands. Its optional
`code_experience` view is enabled in generated configurations. Existing four-tool
server configurations remain unchanged unless `--experience` is supplied.
Regenerate client configuration after moving environments or restoring a bundle.
The machine-specific approved worker image is deliberately not a portable secret
or silently downloaded dependency. Reconfigure it on the destination machine.

The large-repository preview uses one consistent bounded envelope: at most
5,000 eligible source candidates, 24 MB of admitted source, 256 KiB per file,
32 MB of extraction artifacts and 50,000 writer facts. Unsupported assets do
not consume the eligible-file allowance; discovery itself is capped at 50,000
paths. Oversized/invalid-text files remain explicitly omitted, not truncated.
Scope checks, secret screening, source freshness and atomic publication still
apply. Derived graphs must fit the query envelope (60,000 objects / 500,000
relations) before publication. Query response and traversal bounds are unchanged.
Large protected generations may be losslessly compressed inside the same
16 MB physical row limit, with a 256 MB bounded logical decode limit. The usual
zlib envelope is retained; larger generations can use the versioned XZ fallback
with a bounded decoder dictionary. It uses Python's standard-library `lzma`,
not a model or a new ML dependency. Unsupported readers withhold the graph.

If upgrading an older preview, generate a **new** worker build directory with
`knowledge-worker`, explicitly build and inspect its image, then approve the
new immutable ID with `knowledge-config` and reindex. Installing Python changes
alone does not update an already approved Docker image. AtMem never silently
replaces your pinned worker. Repositories outside these envelopes still fail
explicitly; this is not an unlimited-indexing claim.

An MCP-only client chooses whether to call these tools. It is not automatically
injected context. Enabled, qualified turn-hook adapters use the automatic
context path; simply registering MCP does not establish that a model used it.

#### Record an actual command outcome

```sh
atmem code run --project /path/to/project --host claude \
  --intent 'Check the parser regression' --anchor src/project/parser.py \
  -- python -m pytest tests/test_parser.py -q
atmem code experiences parser --project /path/to/project --host copilot
atmem code experience-evidence RECORD_ID RECEIPT_ID --project /path/to/project
```

This explicit producer runs the supplied argument array with the user's normal
permissions, no shell interpolation and closed stdin. It is **not a sandbox**:
run only commands you authorize. It does not obtain commands from read-only MCP
or the dashboard, does not retry, and does not select or download models. An agent
can use this test-command prefix; ordinary host tools are not intercepted merely
by installing it. Automatic user-assertion hooks and this richer command producer
remain separate qualification tiers.

Actual stdout/stderr, argv, exit status and source/environment identity are
retained inside the existing encrypted store after screening. The default
deadline is 300 seconds (maximum 1800), with a shared 500000-byte stdout/stderr
limit. Timeouts, incomplete output and changing source yield `unknown`, not a
successful fix. Recognized secret output is withheld without forming experience
or returning the secret; this partial capture is not complete Black Box evidence.
An optional `--note` remains an attributed user note. The CLI returns the child
exit status after emitting its JSON receipt. Source anchors must be explicit
admitted repository files. The environment check currently covers the local
Python host/package set and repository configuration, not an exhaustive identity
of arbitrary external tools or services.

Shared-profile experiences can be recalled by another agent for that authorized
project. Changed anchors/configuration or another worktree cause withholding;
unrelated source edits do not automatically discard an unchanged anchored
experience. `auto_capture=false` suppresses memory capture even if the user
explicitly runs a command. This is a command/source-bound historical observation,
never proof of a generally correct fix or an instruction to execute it again.

#### Inspect and manage experience

Memory → Coding memory → **Explore coding experience** searches task intent and
observations, shows the bounded outcome and current applicability/withholding
reasons, and lets an authorized user inspect exact captured command output.
The CLI uses the same service. Ordinary `inspect`, `correct`, `forget` and scoped
clear remain available. MCP summaries do not automatically include raw command
output. The list is bounded to 1000 candidates, at most 50 entries per page and
a 32768-byte response; an oversized response is explicitly withheld, not silently
truncated. A five-person usability study and full host/platform qualification
are still open gates.

AtMem Code stores project knowledge in the existing AtMem database and makes it
available across authorized coding-agent sessions. This guide describes the
source preview on `feature/atmem-code-2.3.9`. It has not been published as a new
package release. Phase 9 evaluation and release work remain separate.

The [knowledge/experience expansion](../specs/042-atmem-code/spec.md#pending-expansion-maintained-knowledge-experience-and-exploration)
has experimental source-preview implementations with separate qualification
gates. The basic graph remains a Python syntax index; richer extraction requires
an explicitly selected, locally available pinned worker. Ordinary host formation
and benchmark-only coding-attempt integration are not interchangeable support
claims. [Click replay](../specs/043-click-historical-replay/spec.md) has executed
small comparisons, recorded in RandD; it is not a production-quality guarantee.

## Install the source preview

From this branch's checkout:

```sh
python -m pip install '.[code]'
atmem init --flavour code
```

The `code` extra adds SQLCipher and post-quantum bundle cryptography. The Python
structure index uses the standard library. No embedding or decision-model
weights are downloaded. The exact download size depends on Python and OS; use
`python -m pip install --dry-run '.[code]'` to inspect your platform's packages.
Python 3.10–3.13 are the declared package range; verification results name the
particular versions actually tested.

Code memory requires encrypted storage. For a new database, initialize it once:

```sh
atmem household init /path/to/memory.db --encrypted
```

For an existing plaintext database, use the existing household migration path
before activating Code. Package installation and `init --flavour code` leave
automatic memory off.

## Configure a project and agent

```sh
atmem code setup --project /path/to/project --db /path/to/memory.db --host claude
atmem code setup --project /path/to/project --db /path/to/memory.db --host claude --apply
atmem code enable --project /path/to/project --db /path/to/memory.db --host claude
atmem code status --project /path/to/project --db /path/to/memory.db --host claude
```

Setup previews the database, hook location and activation behaviour. `--apply`
records the disabled project binding. Explicit enablement installs the hook and
requires a successful installed-host capture/context probe. Claude's probe uses
an isolated local model endpoint and does not spend provider credit. It saves
the exact previous host configuration for uninstall. Open a new host session
after the first installation so that the host loads its hooks.

The qualified automatic adapter and outstanding host gates are listed in
[the capability matrix](../specs/042-atmem-code/host-capabilities.md). An
unqualified adapter refuses automatic enablement. An installed CLI binary or a
successful configuration merge alone does not qualify it.

### GitHub Copilot CLI

The source preview supports Copilot CLI **1.0.98 on macOS and Windows 11**. First open
`copilot` (`copilot.cmd` on Windows) in your project and approve its workspace trust prompt, then exit.
AtMem never grants that trust or overrides `disableAllHooks` for you.

```sh
atmem code setup --project /path/to/project --db /path/to/memory.db --host copilot --apply
atmem code enable --project /path/to/project --db /path/to/memory.db --host copilot
atmem code status --project /path/to/project --db /path/to/memory.db --host copilot
```

Enable runs an isolated offline CLI probe without provider credits. Start a
new Copilot session afterwards. Ordinary prompts automatically recall earlier
authorized memory before capturing eligible new facts; no memory-tool call is
needed. Use `--host copilot` with the same disable, enable and uninstall commands
below. Existing hook entries are preserved and uninstall restores their exact
previous file bytes. A changed file is not overwritten on uninstall.

This adapter uses a bounded, read-only lookup of the current event in Copilot's
local session journal to obtain its stable invocation ID. It does not import
the transcript as memory. Missing journals, an unqualified CLI version, or
ambiguous event identity withhold capture/context. Keep the CLI's session
journal accessible to the hook. On Windows the npm CLI launcher is invoked
through Node directly, and generated hooks use native executable/argument
arrays; neither prompt text nor paths are shell-quoted. After upgrading this
Windows preview, restart all AtMem clients so they use the corrected shared
household lock. Migration still requires exclusive access. Linux, VS Code
Copilot and the cloud agent remain unqualified. See the
[test report](../specs/042-atmem-code/copilot-cli-probe.md).

Ordinary prompt events call the local AtMem hook runner. It retrieves earlier
authorized memory before forming new memory from that turn. The agent does not
need to choose a `remember` or `retrieve` tool. A shared profile is common across
agent IDs; other profiles keep separate agent lanes. Clone/worktree names do
not grant sharing by themselves.

The deterministic formation path admits bounded explicit user assertions such
as “Our project uses SQLite for local persistence”, “We decided to keep the
database local”, “We always run unit tests before committing”, and “We fixed
the deadlock by acquiring locks in stable order”. It preserves the source
statement rather than inventing a lesson. These are English rule patterns, not
a general multilingual semantic extractor. Unsupported or transient statements
do not become canonical facts. A user's reported fix is an attributed claim,
not independently verified test execution.

Automatic native recall conservatively withholds source-dependent project
assertions when the repository is dirty or its Git revision differs from the
captured revision. Preferences are not invalidated by source edits. Historical
assertions remain searchable for inspection; they are not silently rewritten.
This whole-repository check can withhold an unchanged assertion after an
unrelated commit. It is not fine-grained semantic dependency analysis.

To attach an authorized second local clone to an existing project, use
`atmem code attach --project /path/to/clone --project-id PROJECT_ID --db
/path/to/memory.db`. The dashboard offers the same explicit attachment action.

```sh
atmem code disable --project /path/to/project --db /path/to/memory.db --host claude
atmem code enable --project /path/to/project --db /path/to/memory.db --host claude
```

Disable pauses automatic capture and context injection. It preserves saved
memory, hooks and restore material. Enable resumes the same installation. A
changed host version requires a new installed-host verification. To restore
the previous hook settings, explicitly disable and then run `atmem code
uninstall` with the same project, database and host arguments.

## Search and change memory

```sh
atmem code projects --db /path/to/memory.db
atmem code search formatter --project /path/to/project --db /path/to/memory.db
atmem code search formatter --project /path/to/project --db /path/to/memory.db --profile shared --agent claude
atmem code inspect RECORD_ID --project /path/to/project --db /path/to/memory.db
atmem code correct RECORD_ID 'My preferred formatter is Black.' --project /path/to/project --db /path/to/memory.db
atmem code forget RECORD_ID --project /path/to/project --db /path/to/memory.db
```

Search also accepts type, source, status, and timezone-aware time filters.
Commands return JSON, including source links and deletion receipts.

Clear first previews an exact project/profile/agent selection:

```sh
atmem code clear --project /path/to/project --db /path/to/memory.db --profile shared
atmem code clear --project /path/to/project --db /path/to/memory.db --preview-token TOKEN_FROM_PREVIEW
```

A changed selection invalidates the preview. Clearing removes canonical memory,
queued source observations and affected local context copies, and verifies
registered vector cleanup. A local clear reports external-provider data as
not deleted; it does not manufacture a remote deletion receipt.

## Settings and dashboard

```sh
atmem code config --project /path/to/project --db /path/to/memory.db
atmem code config --project /path/to/project --db /path/to/memory.db --set '{"auto_capture":false,"auto_recall":false}'
```

The Memory → Coding memory dashboard uses the same application and database as
these commands. It offers project search, source inspection, correction,
forgetting, clear preview, host status/toggles, routing, structure queries and
encrypted bundles. The owner subject selects the same opaque subject used by
CLI; the default Code subject is `local`. Investigators can read their scoped
memory. Administrators can change settings and memory.

Optional review is off by default. Turn `review_workflow` on to queue proposed
formation for approval. Use `atmem code reviews` and `atmem code review EVENT_ID
approve` (or `reject`), or the dashboard queue. Turning this workflow off does
not disable scope checks, source provenance, secret screening or encryption.

Context receipts distinguish prepared bytes, submitted bytes, verified host
acknowledgement and independently observed model input. Code event capture is
not complete model/tool/media flight recording; these adapters do not inherit
the full Agent Black Box reconstruction claim.

## External context and code structure

[The route contract](../specs/042-atmem-code/provider-contract.md) describes
registered RAG and Mem0 services. Configure a route, its exact profiles/agents,
permitted tags, egress and fallback. Set `context_tags` to choose default tags
for automatic task requests. Without matching configured tags, recall uses
AtMem. Credentials and endpoints remain in the existing delegated-provider
configuration and are excluded from portable Code bundles.

```sh
atmem code config --project /path/to/project --db /path/to/memory.db --set '{"graph_enabled":true}'
atmem code graph-index --project /path/to/project --db /path/to/memory.db
atmem code graph-search run --project /path/to/project --db /path/to/memory.db
```

The index stores Python definitions/imports and syntax-level call references.
Other supported text files receive file-level search entries. Dynamic calls
are unresolved. Source locations, file digests and Git revision travel with
results. Changed files/branches withhold stale automatic structure context
until reindexed. Indexing follows Git's ignored-file selection and screens
eligible content before persistence. The optional structure index is stored
inside the encrypted database.

For the experimental richer projection, `knowledge-index --image-id` requires
an immutable local extraction image: it never downloads or selects one silently.
`knowledge-status`, `knowledge-query` and `knowledge-source` inspect its current
generation and bounded evidence. Qualified automatic turn preparation prefers
that richer generation when available, otherwise keeps the labelled syntax
fallback. Consult the knowledge qualification register before choosing a host.

The richer context pack uses task-ranked, source-hash-checked implementation
excerpts with readable file/line references. It removes redundant graph IDs,
labels omitted code explicitly and bounds the entire pack under the existing
shared context budget. Static cleanup call sites are source observations, not
proof that code executed or is correct. Source changes still withhold the old
pack at delivery; no model is added to this packing path. Native search and tests
remain available. Measured token/correctness outcomes belong to the separately
versioned [efficiency loop](../RandD/2026-10-17-structural-efficiency-loop.md), not
an installation-wide savings promise.

The experimental pack may also show one bounded existing test or usage example
from the same authorized source snapshot. It is labeled **not executed** and
does not become a new knowledge-graph fact. Typing-only examples and source
withheld by the secret screen are not used to fill this section. An empty usage
section means no eligible example was selected, not that the code lacks tests.

An experimental read-only progressive reader is available in this source preview:

```bash
python -m atmem.knowledge.code.mcp --db /path/to/memory.db --root /path/to/project --subject local --project-id EXISTING_PROJECT_ID
```

It uses an existing indexed project and exposes read-only `code_context`,
`code_search`, `code_explore` and `code_source`. `code_context` returns focused
current-source excerpts in one request. Installed stdio conformance is tested;
normal host onboarding and general performance claims remain separate. The operator binds project and scope; model arguments
cannot change them or mutate memory. Source edits withhold the old index until
it is reindexed. This command serves MCP over stdio; it does not install itself
into your agent, capture conversations or enable automatic indexing. Host and
token-saving qualification remain separate from the basic protocol interface.

### Full structured code search

The existing `code_search` MCP tool now exposes all eight operations of the
pinned structural baseline. Legacy `{"query":"get_help_option"}` calls still
return compact symbol locations. Full requests select an operation:

```json
{"operation":"query_facts","arguments":{"kinds":["symbol","route","storage"],"limit":20},"budget":32768}
```

| Operation | Example `arguments` | Result |
| --- | --- | --- |
| `query_facts` | `{"name":"get_help_option","kinds":["symbol"]}` | Typed facts, properties and relationships |
| `explore` | `{"id":"ID_FROM_SEARCH","max_depth":2}` | Component neighbourhood |
| `traverse` | `{"node_ids":["ID_FROM_SEARCH"],"direction":"reverse","max_depth":10}` | Dependencies/dependents; up to 20 hops |
| `find_path` | `{"source_id":"SOURCE_ID","target_id":"TARGET_ID"}` | Discovered connecting path |
| `impact_analysis` | `{"target_id":"ID_FROM_SEARCH","max_depth":3}` | Potential affected components, not a runtime guarantee |
| `architecture` | `{"max_nodes":30,"diagram":"mermaid"}` | Overview and diagram |
| `insights` | `{"min_confidence":0.5,"limit":10}` | Extractor findings and evidence |
| `delta` | `{}` | Latest generation changes and extraction receipt |

Full responses use `atmem-code-query-v1`, with status, snapshot/generation,
coverage and the operation result. The byte budget defaults to 12,288 and is
configurable from 256 to 131,072. Oversized results are withheld, not silently
truncated; use filters, pagination or smaller neighbourhoods. `code_explore`
keeps its original two-hop compact contract. No operation grants database,
root or scope selection, writes memory or executes repository code.

### Select richer indexing explicitly

`graph-index` remains the limited syntax fallback. For richer indexing, build
or select the optional worker and use its immutable image ID:

```bash
docker build -t atmem-code-extractor:0.4.26 tools/code-extractor
docker image inspect atmem-code-extractor:0.4.26 --format '{{.Id}}'
atmem code config --project /path/to/project --db /path/to/memory.db \
  --set '{"graph_enabled":true}'
atmem code knowledge-index --project /path/to/project --db /path/to/memory.db \
  --image-id sha256:IMAGE_ID_PRINTED_ABOVE
```

Build-time network access is explicit. Runtime extraction is offline, pinned
to Enola 0.4.26/v287, without owner mounts or repository-provider commands.
The richer source policy now admits additional language, protocol, template,
infrastructure and manifest inputs, including Kotlin, PHP, Scala, Dart, gRPC,
HCL, Vue/Svelte and GraphQL. Eligibility does not guarantee complete framework
resolution; ignore, secret, encoding, source-size and graph limits still apply.

Findings preserve confidence, metrics and evidence. Unresolved writer targets
are not guessed by name. Directory-based Ansible roles and Ruby/PHP virtual
coupling locations are labelled, never fabricated as actual file spans.
Original artifacts remain in the encrypted generation. Unchanged snapshots
skip extraction; changes rebuild and publish atomically. Deltas describe
AtMem's source-bound records, not identical write counts in another backend.
Legacy generations remain readable; explicitly reindex for the new findings,
source policy and delta metadata.

Register the stdio command above with the agent separately from memory hooks.
Get `EXISTING_PROJECT_ID` using `atmem code projects` against the same database.
Copilot CLI's `/mcp add` local-server form can launch that Python command.
Registration does not enable automatic indexing or conversation capture.

See the [index/MCP qualification report](../RandD/2026-10-18-code-index-mcp-depth.md)
for exact tested cells and remaining gates. This is an unreleased source preview,
not a blanket claim of parity with every upstream feature or version.

## Move a project's memory

```sh
atmem code keygen /private/path/bundle-keys
atmem code export project.bundle.json --project /path/to/project --db /path/to/memory.db \
  --recipient-key /private/path/bundle-keys/recipient.public \
  --signing-key /private/path/bundle-keys/signing.secret \
  --signing-public-key /private/path/bundle-keys/signing.public
```

On the destination, initialize an encrypted database and preview the import:

```sh
atmem code import project.bundle.json --project /path/to/new-clone --db /path/to/new-memory.db \
  --recipient-secret-key /private/path/bundle-keys/recipient.secret \
  --trusted-signing-key /private/path/bundle-keys/signing.public
```

Repeat with `--preview-token TOKEN_FROM_PREVIEW` to import. Use the same owner
subject, or pass its explicit `--subject` value. The importer verifies the pinned
signer, encryption, schema, scoped references, identity collisions and state
digest before committing. It preserves canonical records, source episodes,
lifecycle and audit history, rebuilds local derived indexes and binds the new
clone explicitly. Hosts remain disabled on the destination. Hook settings,
enrollment credentials and provider routes do not travel in the bundle.

Bundles use ML-KEM-768, AES-256-GCM and ML-DSA-65 through AtMem's existing
encrypted-export implementation. Keep secret keys private. Key-loss recovery
and cryptographic certification are not supplied by the Code profile.

In the current source preview, larger bundles use authenticated encrypted
pieces automatically; the export/import commands are unchanged. Keep the
complete bundle file and use a preview that supports
`atmem-code-project-encrypted-chunks-v1` on the destination. Older small bundles
remain readable. The maximum logical project bundle is still 128 MB.

Rich code indexing also supports declared Python source encodings and explicit
text byte-order marks. Unsupported or malformed text is excluded from the
optional graph with a visible `source_encoding` count, never guessed or
lossily decoded. Strict execution capture still rejects incomplete identities.
Large rich generations can use bounded lossless storage inside the existing
encrypted database; their physical row limit remains 16 MB and logical limit
is 256 MB in the large-repository preview (64 MB in earlier previews).
The independent 128 MB whole-project bundle limit has not been raised;
an export exceeding it still fails explicitly. Older previews do not understand
all larger compressed derived rows:
export with a supported reader before downgrading, or explicitly rebuild the
derived index. No canonical-memory migration is needed for these preview
formats, and no published package is upgraded by this source-branch change.

## Index-first context curation

### Explicit discovery-only tool profile

The source preview also offers `atmem code mcp-config --project /path/to/project
--tool-profile navigation --json`. This generates configuration for one read-only
`repository_discover` tool: ranked symbol locations, source digests and explicit
non-exhaustive coverage, without source bodies or experience details. Continue
reading selected original source with the agent's native tools. Exact text/regex
search is a separate operation; navigation does not replace exhaustive grep.

The dashboard's repository-knowledge section offers the same MCP profile selector.
Neither interface installs or activates host configuration automatically. The
profile does not silently disable an existing turn hook. For discovery-only use
with already enabled automatic Code hooks, explicitly set
`atmem code config --project /path/to/project --set '{"auto_recall":false}'`;
automatic capture remains unchanged. The generated configuration warns when
automatic recall is still enabled. The
configuration reports separate discovery qualification for Claude, Codex,
Copilot, Muse and Grok on each OS. All new discovery-routing cells start
unprobed; earlier capture-hook support is not evidence of discovery replacement.
An available MCP tool does not mean the host routes its own exploration through
it. Host probes and the prospective native/Cognee/AtMem efficacy comparison are
tracked in `specs/044-atmem-code-discovery-routing/`; no token-saving claim follows
from this profile alone. Existing profiles/defaults remain unchanged.

The source preview offers ranked discovery followed by selective evidence fetch.
Fresh `atmem code setup --apply` projects select `context_mode=index` while
remaining disabled until explicitly enabled. Existing projects keep their prior
content behavior; adding another host or repeating setup does not migrate it.
To switch an existing project explicitly:

```sh
atmem code config --project /path/to/project --set '{"context_mode":"index","index_limit":3,"index_bytes":1024}'
atmem code mcp-config --project /path/to/project --tool-profile curated
```

Copy the generated MCP configuration into the coding client's configuration.
Generation does not silently edit host configuration. Restart/reconnect the
client as its configuration requires. Existing `expanded` and `compact` profiles
are unchanged. `curated` advertises one read-only `code_query` tool:

* `discover`: pass `query`, `kind` (`code`, `experience` or `both`), optional
  `limit` (1–8) and `budget` (256–8192 UTF-8 bytes).
* `fetch`: pass selected `ids` from discovery and optionally an immediate `goal`.
  Code returns exact bounded source lines and explicit omissions. Experience
  details recheck source/environment applicability and retain observed outcomes,
  not claims of verified fixes. Raw command output remains a separate privileged
  investigation operation.
* `changes`: fetch selected IDs with optional known versions and reference mode.
* `capabilities`: inspect supported behavior and integration limitations.

Enabled automatic index mode presents only a small relevant experience index:
bounded titles, IDs, observed outcomes, revision, unchecked applicability and
estimated fetch costs. Full observations, commands/output, code source packs
and delegated context are not automatically appended. No matching experiences
means no automatic index. Code lookup and full experience details are on demand.
Explicit delegated-provider APIs remain available; automatic tag routing requires
legacy `context_mode=content`. Capture settings and retained full evidence do not
change with presentation. Disable still stops automatic capture and recall.

```sh
atmem code discover 'authentication timeout' --project /path/to/project --kind both --json
atmem code fetch code:ID_FROM_DISCOVERY --project /path/to/project --goal 'timeout handling' --json
atmem code fetch exp:ID_FROM_DISCOVERY --project /path/to/project --json
atmem code curation-capabilities --project /path/to/project --json
```

The dashboard exposes presentation mode and index limits under Automatic memory
settings. Ranked code and experience lookup shows index entries first; selecting
an entry fetches details through the same authorized service used by CLI/MCP.
All displayed repository or memory text is untrusted evidence, not instructions.

MCP reference mode requires `references:true`, caller-supplied opaque `session`
and `epoch`, and `known:[{"id":"...","version":"..."}]` from prior fetches.
Only unchanged evidence actually written by that MCP server in that session and
epoch can return an abbreviated reference. Omit reference mode to fetch full
content again. Change epoch after compaction. Restart clears the bounded
process-local ledger. CLI/dashboard calls do not claim continuity with a running
MCP process or knowledge of what the model remembers. Automatic hooks do not yet
have qualified context-epoch acknowledgements, so they do not suppress indices
on the assumption that a previous one remains visible.

Budgets count serialized UTF-8 bytes. `utf8-byte-upper-bound-v1` labels conservative
detail-token estimates; these are not provider billing measurements. Ranking uses
multiple query terms and bounded graph-neighbor relevance; scores do not claim
calibrated truth probabilities. Experience scanning returns at most 1000 active
candidates. Index applicability is unchecked until a detail fetch validates it.

The optional pure `atmem.code.history.mask_observations` helper is for applications
that own prompt assembly and supply an authorized exact-output retention callback.
It copies the history and masks eligible older tool output while preserving tool
pairing and instructions. No native CLI history rewriting is qualified. Learned
SWE-Pruner weights, synthetic training, Torch/CUDA and remote model calls are not
included. Goal-directed source selection is deterministic and local.

Full curation requests/responses and stream-delivery evidence remain inside the
encrypted Code store. Project exports with curation settings or receipts use bundle v3; this
reader still accepts v1/v2. Upgrade older readers before importing v3. Scoped
clear and experience forgetting include affected curation copies; the ephemeral
delivery ledger is not exported and never grants access to a deleted record.

Zero-model qualification can exercise an already owned encrypted project:

```sh
python tools/qualify_code_curation.py --db /path/to/memory.db --project /path/to/project --project-id PROJECT_ID --query 'relevant symbol'
```

It retains exact response artifacts in encrypted `curation-exposure` documents
and reports per-operation bytes/time. This is a boundary check, not measured
coding quality, end-to-end token savings or universal host support. A separate
prospective efficacy protocol is in
`specs/042-atmem-code/context-curation-v1.md`; prior negative results are unchanged.
