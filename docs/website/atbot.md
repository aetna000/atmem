# AtBot intelligence companion

AtBot proposes extraction and retrieval assistance. AtMem retains canonical storage,
scope enforcement and final authorization. AtBot is not a second authority database.

## Setup
```bash
atmem atbot setup
atmem atbot --help
```

AtMem 2.3.7 depends on the separately packaged AtBot 0.1.0.
Choose the model provider deliberately. A remote provider can receive authorized
content needed for its work and may charge for requests; local models have their own
hardware and download requirements. The base memory exercise needs neither.

## When unavailable
AtMem keeps its deterministic path or withholds context according to the operation.
An intelligence failure must not widen access. Check companion configuration,
endpoint reachability and model readiness before changing retrieval settings.

## What affects quality and speed
Embedding quality, the query, corpus, scope and retrieval profile matter.
This release reduces redundant work but does not promise one speed multiplier for
all deployments. [Benchmark reports](../benchmarks.md) explain measured conditions.
