# OpenClaw automated memory control plane

This document describes guarantees specific to the automated OpenClaw adapter.
For a host-neutral runtime integration, use the
[generic adapter contract](generic-adapter.md).

AtMem uses two customer-visible modes.

| Mode | Memory provider | What changes |
| --- | --- | --- |
| Shadow | OpenClaw | AtMem copies, mirrors, verifies, indexes and audits native memory. It does not inject model context. |
| Active | AtMem | Native supplemental memory is frozen; OpenClaw uses AtMem search, get, semantic capture and bounded recall. |

## Guarantees

Before activation, AtMem:

1. discovers the OpenClaw workspace;
2. copies `MEMORY.md` and every `memory/*.md` file, including history created before AtMem was installed;
3. records source path, line range, content digest and snapshot digest;
4. imports the material into an isolated SQLite mirror;
5. verifies the audit chain and complete source manifest;
6. synchronizes files that change during shadow mode;
7. snapshots the plugin configuration needed for restore.

Activation runs a final synchronization, checks the loaded plugin and required tools, protects the frozen native-memory paths, and changes the provider only if every check succeeds. Interrupted activation is detected and must be recovered or restored; it is not silently treated as complete.

Restore first validates and stages the frozen snapshot without changing live files. It then resumes through a durable step journal, preserves unexpected divergent native files as evidence, proves the restored baseline, exports active-period AtMem memories as a separate additions block, restores and re-reads saved configuration, restarts OpenClaw, and verifies the gateway. A successful receipt is bound into the memory audit chain as `control.restored`. Past responses and provider logs cannot be undone. Control-plane evidence is intentionally preserved.

`control verify` measures the current installation without synchronizing, repairing, changing configuration, or restarting OpenClaw. Its named checks cover host and bridge versions, mirror integrity, complete active configuration, shadow safety, frozen paths, restore readiness, and gateway health. Every run has a unique report digest; identical measured state has the same evidence digest.

## Commands

```bash
atmem openclaw install
atmem control status
atmem control verify
atmem control activate
atmem control restore --drill
atmem control restore
atmem openclaw memory status
atmem openclaw memory sync
atmem openclaw memory search "preferred editor"
atmem openclaw memory trace "preferred editor"
```

Use `--json` where offered for automation. Human-readable output is the default.

The restore drill makes exactly three claims: file restoration was tested, saved configuration was readable, and live rollback was not performed. It never changes live host files or configuration.

## Honest boundary

The engine and MCP protocol are model-agnostic. The filesystem discovery, native-memory snapshot, OpenClaw plugin configuration, gateway checks, path guard, and restore adapter are OpenClaw-specific. Other agent hosts need an adapter with equivalent capture, injection, proof, and restore hooks before AtMem can claim a complete switch for them.
