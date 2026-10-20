# AtMem Code: shared project memory for coding agents

Give your coding agents a shared place to find project knowledge and previous
experience. Search code structure, revisit recorded decisions and test outcomes,
and inspect or remove what the project remembers.

Code is optional. Ordinary AtMem memory and existing integrations keep working
without enabling it. No Laya model, embedding model or GPU is required.

## 1. Install

Use Python 3.10–3.13 in a virtual environment, with Git available on `PATH`.
Check `git --version` first. On macOS or Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade "atmem[code]==2.3.9"
```

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade "atmem[code]==2.3.9"
```

The Code extra adds encrypted storage and portable-bundle cryptography, not a
coding agent. Linux platforms building SQLCipher from source need its development
headers and a C compiler first.

## 2. Set up your project

From your Git repository, choose a new database path and run:

```sh
atmem household init ./atmem-code.db --encrypted
atmem code setup --project . --db ./atmem-code.db --host codex --apply
atmem code status --project . --db ./atmem-code.db --host codex
```

Use `claude`, `copilot`, `muse` or `grok` instead of `codex` for another host.
Setup leaves automatic memory disabled. Keep the database, keys and backups
outside version control. For an existing encrypted database, skip initialization
and use its path consistently. Plaintext households need the
[encrypted-storage migration](data-storage-and-backup.md) first.

## 3. Connect your agent

Automatic hooks and on-demand tools are separate connections:

| Connection | Purpose | Activation |
| --- | --- | --- |
| Turn hooks | Capture supported turns and present a small experience index | `atmem code enable --project . --db ./atmem-code.db --host codex` |
| Read-only MCP | Agent requests structure and experience when useful | Register the generated configuration below |

Automatic activation tests the installed host first. An unsupported boundary
refuses activation with a reason. After successful activation, restart the agent.

For on-demand lookup:

```sh
atmem code mcp-config --project . --db ./atmem-code.db --tool-profile curated --json
```

Copy the generated server command and arguments into your client's MCP settings,
then reconnect it. Generation does not modify client settings or enable hooks.
Ask the agent to use `code_query` to discover relevant code or experience, then
fetch selected IDs. It keeps its ordinary editing and testing tools.

Claude Code, Codex and GitHub Copilot CLI have host-specific adapters. Muse and
Grok require their supported runner boundary; an identically named CLI is not
necessarily compatible. Other compatible MCP clients can use the read-only server.
Account policy can disable MCP. Check `code status` for the actual connection;
an available tool is distinct from automatic use or native discovery replacement.

## 4. Add code structure

For local Python syntax navigation without Docker:

```sh
atmem code config --project . --db ./atmem-code.db --set '{"graph_enabled":true}'
atmem code graph-index --project . --db ./atmem-code.db
atmem code graph-search parser --project . --db ./atmem-code.db
```

For richer multi-language structure, dependency traversal, architecture and
potential change impact, use the [structure and MCP reference](atmem-code-structure.md).
That path requires an explicitly built and approved local Docker worker.
The `curated` and `navigation` MCP profiles use this richer knowledge generation;
until it is indexed, use `graph-search` or native source tools. Reindex after
edits or branch changes. Stale evidence is withheld rather than treated as current.

## 5. Share experience across agents

The default project profile is shared. An authorized second host using the same
project and database can search its memory; private profiles remain separate.
AtMem does not merge unrelated projects or automatically upload their content.

```sh
atmem code search formatter --project . --db ./atmem-code.db
atmem code experiences parser --project . --db ./atmem-code.db --host claude
atmem code inspect RECORD_ID --project . --db ./atmem-code.db
```

To record an actual command outcome, supply an existing source file as anchor:

```sh
atmem code run --project . --db ./atmem-code.db --host codex \
  --intent "Check parser behaviour" --anchor src/parser.py \
  -- python -m pytest tests/test_parser.py -q
```

This executes your explicit command with normal user permissions, not a sandbox.
AtMem retains screened output, exit status and source context in encrypted storage.
It records a historical attempt, not a generally verified fix. Ordinary host
commands are not automatically intercepted by this producer.

## Search, correct, delete or pause

```sh
atmem code correct RECORD_ID "Corrected information" --project . --db ./atmem-code.db
atmem code forget RECORD_ID --project . --db ./atmem-code.db
atmem code clear --project . --db ./atmem-code.db
atmem code disable --project . --db ./atmem-code.db --host codex
```

`clear` previews the selection; apply by repeating with its `--preview-token`.
Disable stops automatic capture and recall for that host. It does not erase
memory or block explicit authorized lookup. `code uninstall` restores the saved
host configuration when it has not been changed externally.

Run `atmem init --flavour code`, then `atmem status` to find your dashboard URL.
Under **Memory → Coding memory**, select a project, search memory, explore
experience and change settings. Dashboard and CLI use the same store. Optional
review/audit settings do not disable isolation, secret checks or authorization.
See [portable bundles](atmem-code-structure.md#move-project-memory) to move memory.

## Tests and benchmark evidence

- [AtMem, upstream Cognee and controlled-native results](https://huggingface.co/datasets/atmem/code-discovery-benchmark-evidence-20261020/viewer/trials/test): browse all 18 scored attempts, tokens and timing.
- [Protocol and interpretation](https://github.com/aetna000/atmem/blob/c10c136/RandD/2026-10-20-discovery-benchmark-results.md): separates Click conditions from the one-task SWE-bench qualification.
- [Installed product checks](https://github.com/aetna000/atmem/actions/workflows/atmem-code.yml) and [release gates](https://github.com/aetna000/atmem/actions/workflows/publish.yml).

The comparison retains successes and failures. It is a small diagnostic study,
not a full SWE-bench result. Shared project memory, source-backed navigation,
inspection and portability are the product benefits.
