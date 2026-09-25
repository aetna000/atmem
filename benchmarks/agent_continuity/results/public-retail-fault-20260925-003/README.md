# Public retail interruption: request protection

Pinned tau2-bench commit `b7ea9074c1cba482b30687fecdb5c8425fd6f619`, public retail
task0. Dataset/source license: MIT, see upstream
https://github.com/sierra-research/tau2-bench/tree/b7ea9074c1cba482b30687fecdb5c8425fd6f619.
This replays model responses from the preserved real native pilot. It is not
fresh autonomous or held-out evaluation. Paid API calls:0.

An external HTTP boundary killed each application after the store accepted its
exchange request but before returning the response. The store process survived.
All four waited125 actual seconds, then used ordinary LangGraph checkpoint resume.
Only the installed product supplied recovery decisions. The evaluator did not
change a checkpoint, invent a receipt or decide which step to execute.

| Configuration | Repeated request after restart | Additional store changes | Result |
| --- | ---: | ---: | --- |
| Durable LangGraph baseline | 1 | 0 | Store rejected repeat |
| Baseline + AtMem | 0 | 0 | AtMem required confirmation |
| Baseline + AtFlows | 1 | 0 | Store rejected repeat |
| Baseline + both | 0 | 0 | AtMem required confirmation |

AtMem prevented an uncertain request from being repeated. This does **not** show
duplicate exchanges prevented: the store's native guard rejected baseline repeats.
There is no automatic completion claim for a tool without a reliable query or
idempotency contract. After baseline's changed response, the recorded model
cassette correctly stopped rather than making up a new answer.

Each compressed JSON contains the original native effect journal, before/after
database, exact result/error, post-restart disposition and read-only checkpoint
metadata. `protocol.json` pins code, corpus, cassette and installed distributions.
`summary.json` is derived from those independent observations. `SHA256SUMS.json`
covers generated artifacts; this README and LICENSE are ancillary descriptions.
No product vault, key, access token, private Home data or model credential is exported.

Reproduce using installed development wheels matching the protocol RECORD hashes,
the pinned upstream checkout, preserved native pilot and an isolated AtFlows:

```sh
python -m benchmarks.agent_continuity.retail_fault_qualification \
  --upstream /path/to/pinned/tau2-bench \
  --native benchmarks/agent_continuity/results/pilot-usd20-20260925/native-task0-001 \
  --output /path/to/fresh/output --atflows-url http://127.0.0.1:ISOLATED_PORT
```

`ATFLOWS_CONTINUITY_TOKEN` must match that isolated server. Never target a user's
production agent or customer data. Loopback checks are Python tripwires, not an
operating-system sandbox. This is one qualified fault cell, not the full20-repeat
all-barrier gate or a general production failure-rate estimate.
