# AtMem × Jev Lab

This is an isolated synthetic experiment. It demonstrates how Jev can score
AtMem-nominated candidates while AtMem retains authority over eligibility and
context delivery. It does not read a production database or agent session.

## Offline demo

```bash
python -m research.jev_lab.cli --offline
open research/jev_lab/results/jev-lab.html
```

## Live smoke demo

Put the TypeSafe key in the local environment only (never commit it):

```bash
set -a; source .env.atmem-c709e; set +a
python -m research.jev_lab.cli --model jev-1.13.0
open research/jev_lab/results/jev-lab.html
```

The live path sends only generated synthetic JSON, makes one batched request,
records the returned model ID and latency, and never writes the API key to an
artifact. If the endpoint is unavailable, the report is marked unavailable;
use `--offline` when a deterministic local result is desired.
