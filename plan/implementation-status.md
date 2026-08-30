# AtMem 2.2 implementation status

Updated: 30 August 2026

## Implemented in the `atbot` development branch

- Versioned, dependency-free authority contracts and shipped JSON Schemas.
- Complete subject, agent, and workspace scope on protocol operations.
- Durable source capture with exact digests, replay, and conflicting-key denial.
- Typed memory proposals and admission decisions with interpreter provenance.
- Safe versioned fact-key canonicalization; a key alone cannot supersede memory.
- Governed lexical, graph, and automatic local-vector candidate fusion.
- Candidate-set generation, expiry, digest, scope, sensitivity, and egress checks.
- Byte-stable context serialization and exact exposure confirmation receipts.
- Always-created local vector sidecar with automatic active-memory synchronization.
- Safe vector handling across OpenClaw's staged mirror installation and deletion.
- Dashboard storage visibility, human-readable provenance, search, and user actions.
- Headless AtBot companion boundary with loopback health and governed-memory query.
- AtMem authorization before candidate delivery and record-ID revalidation afterward.
- Deterministic AtMem fallback when AtBot is absent, invalid, or times out.
- One dark, chat-style AtMem dashboard with thinking state and provenance links.
- AtBot standalone customer UI and public task/chat CLI modes removed.
- Content-free AtBot query expansion feeding AtMem-authorized lexical,
  canonical fact-key, graph, and local-vector candidate fusion.
- OpenClaw mirror refresh preserves active non-native governed memories.
- Regression and live proof that `fav food` retrieves `JT likes burgers`.
- Verified local `nomic-embed-text` epoch used by governed dashboard recall;
  active semantic providers survive later memory synchronization without a
  silent downgrade to token hashing.

## Next 2.2 hardening work

- Complete schemas and conformance fixtures for every response and lifecycle API.
- Add authenticated transport adapters and topology membership resolution.
- Complete external extraction, query-expansion, and ranking protocol contracts.
- Add source lookup and correction/forget request contracts to the protocol bundle.
- Add deletion acknowledgements for every AtBot cache and temporary state plane.
- Run performance, migration, crash-recovery, and hostile-adapter acceptance suites.
- Freeze protocol v1 and prepare the 2.2 release notes; no package release is made
  by this development change.
- Publish AtBot, then pin it in the AtMem 2.2 install so a clean installation can
  install it without a repository checkout.
