# MCP profiles

An opt-in [2.3.15b1 beta](../releases/v2.3.15b1.md) adds governed RAG/MCP and verified feedback.
The stable installation examples below retain 2.3.14. Use the explicit beta pin in the release note to test it.


MCP is a tool transport, not proof that a model received returned content.

## Embedded memory server
```bash
atmem mcp --db /path/to/memories.db --subject demo-user
```

This process accesses the specified database. Its launcher must authenticate the
user and select an authorized subject. Do not take the subject from prompt text.
See the [tool inventory](../integration-guide.md#mcp).

## Host control server
```bash
atmem control mcp
```

A custom host uses the governed preparation and lifecycle protocol. It must
report actual model-input delivery, not just that it fetched context.
See [the generic adapter contract](../generic-adapter.md).

## Operator server
```bash
atmem control operator-mcp
```

Reserve this for a trusted operator process. It exposes governance operations;
do not hand its capabilities to an ordinary agent merely to enable retrieval.

## Failure boundary
Identity mismatch, revoked access or an invalid delegated response must not broaden
scope. Investigate the recorded withholding/failure reason instead.
