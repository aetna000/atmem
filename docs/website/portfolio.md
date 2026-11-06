# AtMem product portfolio

The projects have separate responsibilities and installations.

| Product | What it does | Repository |
| --- | --- | --- |
| AtMem | Governed, scoped memory and encrypted evidence; final authority for memory and local accounts | [AtMem source](https://github.com/aetna000/atmem) |
| AtBots | Standalone Pydantic AI agent platform with private agent memory, workspaces, reusable connections and optional supervision | [AtBots source](https://github.com/aetna000/atbots) |
| AtFlows | Local LLM observability, traces and reported costs; optional evidence-review leads | [AtFlows source](https://github.com/aetna000/atflows) |
| AtForma | Local AI stack design, architecture canvas, review, cost estimates and delivery-pack exports; no infrastructure provisioning | [AtForma source](https://github.com/aetna000/atforma) |
| AtSys | Durable coding-task supervision, bounded recovery and independent acceptance checks | [AtSys source](https://github.com/aetna000/atsys) |

Stable AtMem 2.3.13 pins the separate legacy companion `atmem-atbot==0.1.1`
and `atflows==0.1.6`. The companion provides optional model-assisted memory
proposals; it is not the standalone `atbots` distribution. AtMem validates
proposals before changing governed memory. Installing standalone AtBots does
not replace the companion or grant authority over another agent's memory.

`atmem init` starts and checks local companions with AtMem-owned dashboard
login. AtFlows also supports standalone accounts. AtMem's deterministic memory
path remains usable without a running model service. AtSys runs independently
of AtMem/AtFlows; AtBots connects its integrations explicitly. Native AtSys
workspace supervision supports macOS/Linux, not native Windows.

Start with [AtMem's first memory](getting-started.md), the
[legacy companion setup](atbot.md), [AtFlows observability](atflows.md), or the
[AtBots platform guide](https://github.com/aetna000/atbots/blob/main/docs/agent-platform.md).
Review [integration boundaries](integrations.md) before connecting an agent.
