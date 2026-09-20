# AtMem product portfolio

The three open-source packages have separate jobs and repositories.

| Product | What it does | Repository |
| --- | --- | --- |
| AtMem | Governed, scoped memory and encrypted evidence; final authority for memory and local accounts | [AtMem source](https://github.com/aetna000/atmem) |
| AtBots / AtBot | Optional model-assisted extraction and retrieval proposals; AtMem validates and decides | [AtBots source](https://github.com/aetna000/atbots) |
| AtFlows | Local LLM observability, traces and cost data; optional evidence-review leads | [AtFlows source](https://github.com/aetna000/atflows) |

AtMem 2.3.4 pins AtBot 0.1.0 and AtFlows 0.1.1 in its base installation. Both remain useful independently: AtFlows can run with standalone accounts, while AtMem works when its server is stopped. AtMem can own the account authority for both dashboards when you opt into AtFlows delegated login. AtBot never receives automatic authority to mutate canonical memory.

Start with [AtMem's first memory](getting-started.md), [AtBot's intelligence setup](atbot.md), or [AtFlows observability](atflows.md). Review the [integration boundaries](integrations.md) before connecting an agent.
