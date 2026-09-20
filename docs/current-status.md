# Current status

**Release line:** AtMem `2.3.4b1`, OpenClaw bridge `2.3.4-beta.1`, AtBot
`0.1.0`.

**Source candidate:** AtMem `2.3.4b2` installs AtFlows `0.1b6` by default;
OpenClaw bridge `2.3.4-beta.2` accompanies an opt-in, read-only AtFlows
review-lead handoff. No AtFlows server starts automatically, and existing AtMem
flows still work without one. This candidate has not been published; see
[draft release notes](releases/v2.3.4b2.md) and
[local installed-artifact evidence](implementation-evidence/026/20260920T094307Z-85c2ae2-atflows-b2.md).

**2.3.4b1 scope:** local query expansion, exact-search/index reuse improvements,
bounded answer-support corrections and responsive session-archive layout.
The `core-rrf-v1` candidate strategy and scoped graph nominations, with bounded
paths and canonical revalidation, ship as opt-in developer evaluation options.
Retrieval defaults are unchanged. See the
[core hybrid experiment](implementation-evidence/031/core-hybrid-benchmark.md)
and [graph implementation and four-profile results](implementation-evidence/031/graph-nomination.md)
for the measured results behind both, and the
[continuing retrieval research](../specs/031-mem0-head-to-head-retrieval/spec.md).

AtMem 2.3.4b1 is the beta local encrypted Agent Black Box and governed-memory
release. The package records exact host-observed text, URLs, tool arguments and
results plus supported image, audio, video and document bytes when capture mode is
`full`. New installations use full capture by default. Operators may deliberately
select encrypted metadata-only capture or turn the recorder off.

## What is verified

- One portable AtMem Home contains memory, encrypted evidence, accounts, keys,
  configuration, multimodal artifacts, migration receipts and disposable runtime
  state. `--home` overrides `ATMEM_HOME`, which overrides `~/.atmem`.
- A copied home can be structurally verified, opened read-only with `atmem restore`,
  authenticated using its own Administrator account, and adopted without rewriting
  historical evidence. Copy-first migration and verified quiescent snapshots leave
  their source untouched.
- Viewer receives content-free metadata and hashes. Investigator can decrypt and
  reconstruct in AtMem. Evidence Collector can additionally download/export
  plaintext. Administrator has the same evidence authority and manages accounts,
  recovery, restore and adoption.
- OpenClaw captures exact supported host boundaries, durable replay spooling,
  governed memory exposure, model/tool lifecycle and current WebChat media bindings.
  Pydantic AI and LangChain/LangGraph provide governed native and delegated context
  delivery; their full OpenClaw-style multimodal host capture profile is not claimed.
- Delegated providers use per-instance HMAC request authentication, deadline and
  replay rejection before provider access, authenticated health and Ed25519 result
  verification. Delegation stays disabled until an exact registration is enabled.
- AtMem's default retrieval requires direct query support. Fact-key retrieval covers
  personal questions such as age even when generic terms are absent, while unrelated
  personal facts remain withheld.

## What AtMem proves

AtMem proves what a connected host supplied and what AtMem stored, authorized and
delivered. External side effects — a website, a payment, a message — carry their
own receipt; attach one and it is evidence, otherwise the action is recorded as
observed rather than confirmed.

AtMem never invents evidence. A missing host hook is reported as a gap, never as
success or failure. Records captured as hash-only or metadata-only stay that way:
fidelity is a capture-time decision, and no upgrade rewrites history.

The AtMem home is a local, single-writer design by default: no cloud sync, no
multi-primary replication, no automatic conflict merging. The artifact vault
streams and deduplicates content. Post-quantum recipient export activates when
its optional cryptographic backend is installed; local at-rest payload encryption
uses the documented authenticated symmetric profile.

See the [2.3.4b1 release notes](releases/v2.3.4b1.md) for upgrade and migration commands,
and the [implementation evidence index](implementation-evidence/README.md) for the
recorded gates.
