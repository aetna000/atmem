# AtMem 2.2 implementation status

Updated: 31 August 2026

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
- AtBot source consolidated under `packages/atbot` with its history preserved;
  AtMem and AtBot remain separate wheels and processes with no runtime imports
  or direct database access across the boundary.
- AtMem authorization before candidate delivery and record-ID revalidation afterward.
- AtMem-owned AtBot service lifecycle with a pinned private runtime, private
  configuration and logs, loopback-only start/stop supervision, status, doctor,
  protocol/version checks, and actionable safe-fallback diagnostics.
- The AtMem wheel now requires the exact AtBot version. First interactive use
  offers local Ollama, custom local OpenAI-compatible AI, OpenRouter, OpenAI,
  DeepSeek, xAI Grok, native Anthropic Claude, Hugging Face, custom HTTPS API,
  or a remembered safe-fallback choice. Configuration retains only key
  environment-variable names and drives remote candidate filtering.
- Deterministic AtMem fallback when AtBot is absent, invalid, or times out.
- One dark, chat-style AtMem dashboard with thinking state and provenance links.
- Bare and partial CLI commands now guide the user to the next valid action;
  the dashboard exposes the same AtBot provider, model, endpoint, lifecycle,
  safe-fallback, and copyable CLI configuration controls in a collapsed
  **Memory intelligence** settings row. The dashboard renews one expired local
  CSRF session and retries the mutation once.
- AtBot standalone customer UI and public task/chat CLI modes removed.
- Content-free AtBot query expansion feeding AtMem-authorized lexical,
  canonical fact-key, graph, and local-vector candidate fusion.
- Generic and OpenClaw `control_prepare` now use that same governed hybrid
  candidate path, persist one durable generation-bound candidate set, allow
  AtBot to rank only its IDs, and construct exact adapter bytes exclusively
  through `prepare_context_v1()`.
- Authenticated automatic capture now binds the original source in AtMem before
  accepting AtBot fact/entity proposals. AtMem alone creates the scope and
  source binding, strips ungrounded relationship IDs, and records the admission.
- Shadow mode quarantines automatic proposals for review; active mode may admit
  safe trusted-user additions under deterministic AtMem policy. AtBot never
  receives an admission capability and stores no canonical state.
- If AtBot is unavailable or invalid, deterministic local extraction enters the
  same source-capture and AtMem-admission path. Canonical graph and local-vector
  projections synchronize through the normal Memory lifecycle.
- OpenClaw mirror refresh preserves active non-native governed memories.
- Regression and live proof that `fav food` retrieves `JT likes burgers`.
- Verified local `nomic-embed-text` epoch used by governed dashboard recall;
  active semantic providers survive later memory synchronization without a
  silent downgrade to token hashing.
- Optional Pydantic AI 2.x Hooks and LangChain/LangGraph AgentMiddleware
  adapters now automate authenticated capture, hybrid prepare, data-channel
  injection, exact exposure confirmation, model/tool evidence, completion, and
  failure reporting without replacing native history or checkpoint state.
- Both framework adapters share one host-neutral lifecycle implementation and
  pass the same real generic control-plane conformance test, including shadow
  non-injection and multi-agent scope validation.

## Next 2.2 hardening work

- Complete schemas and conformance fixtures for every response and lifecycle API.
- Add authenticated transport adapters and topology membership resolution.
- Complete external extraction, query-expansion, and ranking protocol contracts.
- Add source lookup and correction/forget request contracts to the protocol bundle.
- Add deletion acknowledgements for every AtBot cache and temporary state plane.
- Run performance, migration, crash-recovery, and hostile-adapter acceptance suites.
- Freeze protocol v1 and prepare the 2.2 release notes; no package release is made
  by this development change.
- Publish the already-pinned `atmem-atbot==0.1.0a1` distribution before AtMem 2.2 so
  the required dependency resolves for a clean installation without a
  repository checkout.
