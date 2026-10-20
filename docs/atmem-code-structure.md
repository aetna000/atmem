# AtMem Code structure, MCP and portability

Start with the [Code quickstart](atmem-code.md). These optional paths use the same
encrypted database and configured Git project; they do not enable automatic hooks.

## Build the richer index

Install and start Docker. Create a new worker build directory:

```sh
atmem code knowledge-worker ./atmem-extractor
docker build -t atmem-code-extractor ./atmem-extractor
docker image inspect --format '{{.Id}}' atmem-code-extractor
atmem code knowledge-config --project . --db ./atmem-code.db --image-id sha256:PASTE_IMAGE_ID
atmem code config --project . --db ./atmem-code.db --set '{"graph_enabled":true}'
atmem code knowledge-index --project . --db ./atmem-code.db
atmem code knowledge-status --project . --db ./atmem-code.db
```

The explicit build downloads pinned dependencies. AtMem uses the immutable local
image you approve; upgrading Python does not silently replace it. Configure a
worker separately on each destination machine. Third-party licenses and notices
are included in the distribution.

The index retains source-linked modules, symbols, dependencies, endpoints, storage
resources, tests and relationships where the extractor supports them. Static
analysis does not discover every dynamic or framework relationship.

```sh
atmem code knowledge-query parser --project . --db ./atmem-code.db
atmem code knowledge-query --operation architecture --project . --db ./atmem-code.db
atmem code knowledge-query --operation explore --options '{"name":"Parser"}' --project . --db ./atmem-code.db
```

Other operations: `traverse`, `find_path`, `impact_analysis`, `delta`, `insights`.
Supply returned seed IDs and filters through `--options`. Impact is potential
structural effect, not runtime proof. Changed snapshots publish atomically;
unchanged snapshots skip extraction. Reindex after source changes.

Bounds: 5,000 eligible sources, 24 MB admitted source, 256 KiB per file, 32 MB
extraction artifacts and 50,000 writer facts. Query generations accept at most
60,000 objects and 500,000 relations. Secret, hidden/configuration, encoding,
size and traversal exclusions remain active and visible. Malformed text is
omitted, never lossily decoded.

## Choose an MCP interface

| Profile | Interface |
| --- | --- |
| `curated` | `code_query`: discover code/experience, fetch selected evidence, check changes and capabilities |
| `navigation` | `repository_discover`: ranked locations only; read original source with native tools |
| `compact` | `code_query`: context, symbol search, source and structural operations |
| `expanded` | Separate read-only context, search, source and structural tools |

Generate one using `atmem code mcp-config --tool-profile PROFILE --project .
--db ./atmem-code.db --json`, then register it with the client. Registration alone
does not force tool use or replace native exploration.

Navigation callers can supply `{"query":"parser error handling"}`. The server
creates IDs and defaults. Optional `limit` is 1–8 and `budget` is 512–8192 UTF-8
bytes. Existing versioned portable envelopes remain accepted. Results contain
ranked, non-exhaustive locations and explicit omissions, never source bodies.

Curated calls use:

```json
{"operation":"discover","arguments":{"query":"parser","kind":"both","limit":3,"budget":4096}}
```

```json
{"operation":"fetch","arguments":{"ids":["code:ID_FROM_DISCOVERY"],"goal":"error handling"}}
```

`kind` is `code`, `experience` or `both`. Fetch only returned IDs. Code details
contain exact bounded lines; experience details check current applicability.
Raw command output requires privileged investigation. Repository text remains
untrusted evidence. Verify edits using actual tests.

## Experience presentation and bounds

Fresh projects select index-first presentation. Enabled hooks present a small
experience index, not source bodies or command output. Existing projects retain
their settings. Switch explicitly with:

```sh
atmem code config --project . --db ./atmem-code.db --set '{"context_mode":"index","index_limit":3,"index_bytes":1024}'
```

For discovery-only use, set `auto_recall=false` if hooks were already enabled.
Capture stays separate. Automatic delegated tag routing requires the legacy
`context_mode=content`; explicit delegated APIs remain available.

Command recording defaults to a 300-second deadline (maximum 1800) and 500,000
combined output bytes. Timeout, incomplete output or changed source yields an
unknown outcome. Recognized secrets withhold capture. `auto_capture=false` also
suppresses explicit producer capture. Applicability covers declared source
anchors and local environment metadata, not every external dependency.

Experience browsing scans at most 1,000 active candidates, 50 entries per page
and 32,768 response bytes. Shared profiles permit authorized cross-agent recall;
private lanes remain separate. Details are checked again when fetched.

## Move project memory

```sh
atmem code keygen /private/path/bundle-keys
atmem code export project.bundle.json --project . --db ./atmem-code.db \
  --recipient-key /private/path/bundle-keys/recipient.public \
  --signing-key /private/path/bundle-keys/signing.secret \
  --signing-public-key /private/path/bundle-keys/signing.public
```

On the destination, initialize an encrypted household and preview import:

```sh
atmem household init ./destination.db --encrypted
atmem code import project.bundle.json --project /path/to/new-clone --db ./destination.db \
  --recipient-secret-key /private/path/bundle-keys/recipient.secret \
  --trusted-signing-key /private/path/bundle-keys/signing.public
```

Repeat with its `--preview-token`. Keep the same subject, or supply `--subject`.
AtMem verifies encryption, trusted signer, scoped references, collisions and state
digest before committing. Host hooks, enrollment credentials and provider routes
do not travel. Reconfigure the worker and explicitly enable destination hosts.

Bundles preserve canonical records, source episodes, lifecycle and audit history.
They use ML-KEM-768, AES-256-GCM and ML-DSA-65; no certification is implied.
Keep secret keys private. Bundle v3 supports curation receipts and reads v1/v2.
Large bundles use authenticated encrypted pieces; logical project limit is
128 MB. Derived rows retain 16 MB physical and 256 MB logical limits. Older
readers may not understand new derived formats; use a compatible reader or
rebuild the derived index before downgrading. Canonical memories are not rewritten.
