# Memory and evidence, under your control

AtMem is a host-neutral Agent Black Box and reversible memory control plane.
Keep scoped memories useful across sessions, control which context reaches an agent,
and investigate the evidence a supported host captured.

## Start with a working example
[Install and run your first memory](getting-started.md). The Python example runs
without an API key or a model download. Then [connect an agent](integrations.md)
and review shadow mode before enabling context injection.

## New in 2.3.7: preserve work across restarts

Connected workflows can reuse saved tool results, query supported destinations
after a lost receipt, or stop uncertain actions for confirmation. AtFlows 0.1.3
shows attempts and reported recovery costs, with grouped event charts.
Start with [Resume work](../continuity.md) and read the
[2.3.7 release evidence and scope](../releases/v2.3.7.md).

## Explore the documentation
- [Product portfolio](portfolio.md): AtMem, AtBots and AtFlows roles, source repositories and integration boundaries.
- [Getting started](getting-started.md): installation, first memory and troubleshooting.
- [AtBot](atbot.md): optional model-assisted memory proposals governed by AtMem.
- [AtFlows](atflows.md): local observability, optional shared login and evidence-review leads.
- [Integrations](integrations.md): OpenClaw, frameworks, MCP and delegated providers.
- [Reference](reference.md): commands, HTTP, retrieval, evidence and storage.
- [Examples](examples.md): small runnable workflows and expected results.
- [Releases](releases.md): changes, compatibility and upgrade instructions.

## Know what the evidence proves
AtMem retains what supported host boundaries supply. A tool returning successfully
is not independent proof that a purchase or message succeeded externally.
Missing historical content cannot be reconstructed from a hash.
Read [evidence and roles](evidence.md) before choosing a capture profile.

These are latest-stable guides. For older installations, read that version's release
notes and upgrade instructions; full historic guide sets are not published here.
