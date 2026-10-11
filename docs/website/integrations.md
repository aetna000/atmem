# Connect your runtime

Choose the boundary you control. Integrations do not all expose identical evidence.

| Runtime | Start here | Important boundary |
| --- | --- | --- |
| OpenClaw | [Setup](../openclaw-setup.md) | Supported hook profile includes full-fidelity multimodal capture |
| Hermes | [Setup](integrations/hermes.md) | Reversible isolated shadow mode by default; active recall and sharing are explicit |
| Pydantic AI | [Capability adapter](../framework-adapters.md#pydantic-ai) | Keeps framework history and model selection |
| LangChain / LangGraph | [Middleware](../framework-adapters.md#langgraph-and-langchain) | Keeps checkpoints and workflow state |
| Custom host / MCP | [Generic adapter](../generic-adapter.md) | Host must report actual delivery truthfully |
| Python application | [Embedded memory](python.md) | Retrieval alone is not model-input evidence |
| HTTP application | [HTTP API](../http-api.md) | Local authentication and scope still apply |
| Context provider | [Delegation](../delegated-context-provider.md) | HMAC request auth and signed decisions |

## Before activation
Use persistent authenticated subject, agent and workspace identities. IDs supplied
by an untrusted prompt do not grant authority. Shadow mode observes and prepares
without injecting. Review [the control plane](../control-plane.md) before activation.

## Provider versus host
A host adapter delivers context to the model and reports lifecycle events.
A delegated provider chooses context for a registered scope. AtMem authenticates
the request, verifies the signed response and records authorization/delivery.
Provider delegation does not imply that the provider stores every agent session.

## Compatibility
The 2.3.9b1 source candidate and OpenClaw bridge are aligned at
2.3.9-beta.1; AtBot is 0.1.1b1 and AtFlows is pinned to 0.1.4b3. The locked OpenClaw
conformance profile uses 2026.8.1, not a promise about every future host.
Framework exact-delivery support does not imply the same durable multimodal capture
coverage as OpenClaw. See [release compatibility](../releases/v2.3.9b1.md).
