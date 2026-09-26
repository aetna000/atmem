# Hermes integration acceptance matrix

Date: 2026-09-27. Target: AtMem 2.3.8b2 with a tested AtFlows companion.
This is an acceptance checklist, not a declaration of shipped parity.

| User action | Hermes release requirement | Current evidence |
| --- | --- | --- |
| Appear in Hermes provider list | Native discovery without replacing current memory | Inactive packaged plugin installed locally; native dashboard metadata lists `atmem`, unavailable |
| Connect an existing agent | Guided profile discovery and preview; no manual Python/environment surgery | Inactive preview/install/status implemented; connection and activation pending |
| Switch memory provider | Explicit activation, backed-up settings, preserved native stores; disclose no history import | Pending installer |
| Remember and recall | Ordinary governed capture, new-session recall, isolated scope | Native directory provider → real scoped RPC capture → product review → new-process recall passed in temporary Homes; live guided activation pending |
| Diagnose a problem | CLI and dashboard agree on versions, provider, endpoints, pending writes and repair | Pending |
| Upgrade safely | Idempotent installed upgrade preserves configuration and memory | Pending |
| Undo the switch | Conflict-safe restore of previous provider; no memory deletion | Pending |
| See activity in AtFlows | Optional guided connection and real session evidence, grouped runs and supported charts | Standalone native observer implemented in AtFlows Spec 006: CLI/dashboard setup, real local Hermes/Ollama call, metadata Timeline and grouping; explicit AtMem session mapping and full parity remain pending |
| Keep existing tools | Preserve OpenClaw, existing telemetry exporter and model-provider settings | Installed regressions pending |
| Know capture coverage | Distinguish prepared recall, returned context, observed model/tool events and unknown outcomes | Core profile only; full boundary audit pending |

OpenClaw comparison must use the shipped package and source, not aspirational
specs: its prompt-build bridge withholds fresh memory on recall failure, while
the agent may continue without that context. Hermes uses the same fresh-recall
authorization boundary. Neither comparison claims revocation of context already
disclosed to the host or global exactly-once execution.

For each completed row record package/host versions, OS, command, exit status,
sanitized receipt and test location in `validation.md`. Qualify native Windows
and WSL separately. A missing host hook remains an explicit capability gap;
do not label complete capture parity until the corresponding evidence exists.

AtFlows requirements are owned by its `specs/006-guided-integrations/`.
AtMem's T023–T026 and AtFlows T055–T059 are coordinated product work; benchmark
code must not supply any part of setup, capture, memory or recovery functionality.
