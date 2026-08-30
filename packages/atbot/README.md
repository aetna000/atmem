# AtBot

AtBot is the local-first intelligence companion for AtMem.

> AtBot proposes and ranks; AtMem authorizes and stores.

AtBot provides model-backed memory inference, entity and relationship
proposals, query expansion, reranking, and bounded memory maintenance. It is
not an independent customer-facing agent and does not own canonical memory.

The supported product interface is the unified AtMem dashboard. Host agents
such as OpenClaw, Hermes, and other runtimes integrate through agent-specific
adapters into the same AtMem authority contracts.

## Companion development

During joint development, install both packages editable:

```bash
python -m pip install -e ..
python -m pip install -e ".[dev]"
```

Start the headless local companion:

```bash
atbot serve
```

Then open the AtMem dashboard. AtMem discovers the companion and uses it for
natural-language memory query, extraction, and ranking. If AtBot is unavailable,
AtMem continues through its deterministic and hybrid-search fallback.

Run the suites from the AtMem repository root:

```bash
python -m pytest -q
python -m pytest -q atbot/tests
```

See [the companion specification](research/research.md) and
[architecture](docs/architecture.md).

## License

AtBot is licensed under the [Apache License 2.0](LICENSE). It permits
commercial and internal enterprise use, modification, and distribution,
subject to the license terms. Apache-2.0 also provides an explicit contributor
patent grant and does not require an organization to publish private changes
merely because it runs the software as a service.
