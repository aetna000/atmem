# Current status

**Release line:** AtMem `2.3.3`, OpenClaw bridge `2.3.3`, AtBot
`0.1.0`.

**2.3.3 scope:** local query expansion, exact-search/index reuse improvements,
bounded answer-support corrections and responsive session-archive layout.
The [continuing retrieval research](../specs/031-mem0-head-to-head-retrieval/spec.md)
retains the 2× target as future work, not a release claim or tagging gate.
The opt-in `core-rrf-v1` candidate strategy is available for developer evaluation;
existing retrieval defaults remain unchanged pending broader quality validation. See the
[core hybrid experiment](implementation-evidence/031/core-hybrid-benchmark.md).
The release also includes opt-in scoped graph nominations with bounded
paths and canonical revalidation. Graph safety fixtures pass, but broad graph
fusion worsened calibration ranking versus no-graph fusion; it is not promoted.
See [graph implementation and four-profile results](implementation-evidence/031/graph-nomination.md).

AtMem 2.3.3 is the stable local encrypted Agent Black Box and governed-memory
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

## Honest boundaries

AtMem proves what a connected host supplied and what AtMem stored, authorized and
delivered. It does not independently prove that an external website, payment,
message or other real-world side effect occurred unless a separately verified
receipt is attached. Missing host hooks remain evidence gaps, not inferred success
or failure. Existing historical hash-only or metadata-only records cannot be made
full fidelity retroactively.

The AtMem home is a local, single-writer design. It does not implement cloud sync,
concurrent multi-primary replication or automatic conflict merging. The artifact
vault streams and deduplicates content, but release tests use bounded fixtures rather
than physically allocating a 10 GiB sample. Post-quantum recipient export is
available only when its optional cryptographic backend is installed; local
at-rest payload encryption remains the documented authenticated symmetric profile.

See the [2.3.3 release notes](releases/v2.3.3.md) for upgrade and migration commands,
and the [implementation evidence index](implementation-evidence/README.md) for the
recorded gates.
