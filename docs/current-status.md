# Current status

**Release line:** AtMem `2.3.2`, OpenClaw bridge `2.3.2`, AtBot
`0.1.0`.

**In development, not released:** [2.3.3b1 retrieval beta](../specs/031-mem0-head-to-head-retrieval/spec.md).
Its Mem0 comparison and 2× target remain validation gates, not shipped claims.

AtMem 2.3.2 is the stable local encrypted Agent Black Box and governed-memory
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

The 2.3.2 home is a local, single-writer design. It does not implement cloud sync,
concurrent multi-primary replication or automatic conflict merging. The artifact
vault streams and deduplicates content, but release tests use bounded fixtures rather
than physically allocating a 10 GiB sample. Post-quantum recipient export is
available only when its optional cryptographic backend is installed; local
at-rest payload encryption remains the documented authenticated symmetric profile.

See the [2.3.2 release notes](releases/v2.3.2.md) for upgrade and migration commands,
and the [implementation evidence index](implementation-evidence/README.md) for the
recorded gates.
