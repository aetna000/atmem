# Coding-agent host capability matrix

**Qualification inventory, updated 2026-10-15.** Tests and limitations are recorded in [implementation-status.md](implementation-status.md). Portable core results do not qualify a host. Copilot CLI 1.0.98 has now been probed on macOS; see [probe results](copilot-cli-probe.md). Only the tested subset below may be advertised as automatic.

| Host surface | Local version | Documented extension path | Candidate capture events | Candidate recall boundary | Current claim |
| --- | --- | --- | --- | --- | --- |
| [Muse Code](https://meta-models.github.io/muse-code-sdk/next/guides/extend/) | 1.4.7-R6101.1 (initial inventory: 1.0.2) | Project hooks and MCP; [hook reference](https://meta-models.github.io/muse-code-sdk/next/guides/plugins/reference/hook-events/) | A prior echo probe executed the prompt hook; subsequent startup also timed out | Echo `PreLLMCall` omitted the canary; isolated Meta-protocol endpoint received zero requests within 30 seconds | Blocked B01; no automatic activation |
| [Claude Code](https://code.claude.com/docs/en/hooks) | 2.1.281 | Lifecycle hooks and MCP | Real user-prompt capture tested; tool outcome/flush contracts tested separately | Actual local Anthropic request contained the hook canary and, in a new session, recalled memory | Automatic prompt capture/recall on tested macOS; partial evidence coverage, not full flight reconstruction |
| [Grok CLI](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md) | 1.0.13 (5e9a58528b76) | Session, prompt, tool and stop hooks; [MCP](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/07-mcp-servers.md) | Configuration adapter and normalized intake exist; no real automatic capture qualification | Documented allowing `UserPromptSubmit` output discards `additionalContext`; a different delivery boundary is required | Blocked B02; no automatic activation |
| [GitHub Copilot CLI](https://docs.github.com/en/copilot/reference/hooks-reference) | 1.0.98, macOS | CLI hooks and [plugin/MCP](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference) | Explicit event argument plus journal invocation identity; actual prompt capture, replay and scope gates tested | Ordinary prompt context observed in new and resumed CLI sessions; startup recall omitted to avoid duplication | Automatic prompt capture/recall on tested macOS, following workspace trust and offline activation probe; partial evidence only |
| [Codex](https://learn.chatgpt.com/docs/hooks) | 0.162.1 | Trusted project `.codex/hooks.json`, lifecycle hooks and MCP | Actual prompt hook and AtMem capture passed in an isolated trusted fixture | Actual Responses request contained the canary; actual captured memory transferred to a Claude session | Controlled wire probe passed; default activation blocked B04 pending persistent user-trust onboarding |

## Tested platform cells

| Surface | macOS 26.5.2, Python 3.12.2 | Windows 11 26200, Python 3.12.6 | Linux aarch64, Python 3.12.15 |
| --- | --- | --- | --- |
| Encrypted Code core, CLI/HTTP settings and encrypted bundle round trip | Installed wheel passed | Installed wheel passed | Installed wheel passed |
| Dashboard interactive browser journey | Chrome passed | Not run | Not run |
| Claude 2.1.281 prompt capture/recall, enable/pause/restore | Passed | Unsupported automatic adapter | Unverified |
| Codex 0.162.1 controlled model-boundary probe | Passed with fixture-only trust flag | Unverified | Unverified |
| Copilot CLI 1.0.98 prompt capture/recall, enable/pause/restore | Passed | Unsupported automatic adapter | Unsupported automatic adapter |
| Muse, Grok automatic adapters | Blocked as above | Unverified | Unverified |

The Codex test does not approve the owner's hooks or change their trust store.
It creates an isolated `CODEX_HOME`, persists project trust there, and permits
only a vetted generated command for that invocation. CLI `-c` project trust
and `--ignore-user-config` were insufficient for loading the project hooks in
the first probes. Production does not add the bypass flag. The registry
refuses default Codex activation rather than claiming normal sessions will run
an untrusted hook.

All automatic Code status and exposure receipts mark evidence coverage
`partial` and reconstruction `not_reconstructable`. Host memory capture is not
the separate full Agent Black Box evidence service. Actual task success,
forced model compaction, every tool boundary, and media reconstruction have
not been established by the local no-tool protocol probes.

GitHub Copilot in an editor and GitHub's cloud coding agent are distinct host surfaces, not covered by the Copilot CLI row. Each host adapter must advertise explicit event availability, user trust/approval, input payload limits, output/context limits, timeouts, OS support, and the strongest observable delivery state: `submitted`, `host_acknowledged`, or `model_input_observed`. A hook response is not proof of model input unless the host exposes that boundary.

## Phase 3 probe required for each automatic cell

1. Pin the installed host binary/plugin version and OS; inspect the host's approved hook configuration without changing it.
2. Install the AtMem adapter only after user selection and preview; confirm the hook actually runs in a clean session.
3. Submit a harmless unique canary context at the nominated boundary; verify the host acknowledgement and, where observable, the model-input boundary. Do not infer delivery from a successful hook exit alone.
4. Capture one real prompt and one completed useful task outcome, force compaction and process exit, then verify exactly-once flush/recovery and no lost pending item.
5. Start a second session with a different supported coding agent on the same authorized project. Verify shared recall, private-lane isolation, source attribution and context budget.
6. Test disabled `auto_capture` and `auto_recall` settings, paths containing spaces, service timeout, malformed event, hostile local process, host upgrade, disable and exact prior-config restoration.
7. Record the cell as `automatic`, `manual MCP`, `degraded`, or `unavailable` with raw receipts. Only `automatic` may support the no-manual-call product claim.

The event sequence is inspired by [Mem0's Codex integration](https://github.com/mem0ai/mem0/blob/main/docs/integrations/codex.mdx): first-prompt recall, post-tool/stop capture, pre-compaction and session-end flush, and explicit search later in the session. AtMem does not inherit Mem0's cloud dependency or its exact hook semantics; each host adapter must pass the local probes above.
