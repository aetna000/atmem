# AtMem Code

AtMem Code stores project knowledge in the existing AtMem database and makes it
available across authorized coding-agent sessions. This guide describes the
source preview on `feature/atmem-code-2.3.9`. It has not been published as a new
package release. Phase 9 evaluation and release work remain separate.

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
