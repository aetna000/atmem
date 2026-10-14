# Coding-agent host capability matrix

**Phase 0 inventory, 2026-10-14.** This is a design inventory, not an automatic-support claim. The local macOS versions below were discovered with `--version`; Copilot CLI is absent. Published hook documentation may describe a newer version than installed. Phase 3 must probe each installed host/OS combination before changing a cell to `automatic`.

| Host surface | Local version | Documented extension path | Candidate capture events | Candidate recall boundary | Current claim |
| --- | --- | --- | --- | --- | --- |
| [Muse Code](https://meta-models.github.io/muse-code-sdk/next/guides/extend/) | 1.0.2 | Hooks, plugin and MCP; the [1.3.0 hook reference](https://meta-models.github.io/muse-code-sdk/next/guides/plugins/reference/hook-events/) must not be assumed to match 1.0.2 | `UserPromptSubmit`, `PostToolUse`, `Stop`, `PreCompact` where supported | `UserPromptSubmit` or `PreLLMCall` if the installed version can return model-visible context | Unverified; manual MCP until probe |
| [Claude Code](https://code.claude.com/docs/en/hooks) | 2.1.281 | Lifecycle hooks and MCP | User prompt, post-tool, stop and compaction hooks | Session or prompt hook with model-visible additional context, subject to installed-version probe | Unverified; manual MCP until probe |
| [Grok CLI](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md) | 1.0.13 | Session, prompt, tool and stop hooks; [MCP](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/07-mcp-servers.md) | `UserPromptSubmit`, `PostToolUse`, `Stop` where supported | Prompt hook only if the installed version can add model-visible context; `SessionStart` alone does not prove injection | Unverified; manual MCP until probe |
| [GitHub Copilot CLI](https://docs.github.com/en/copilot/reference/hooks-reference) | Not installed | CLI hooks and [plugin/MCP](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference) | `userPromptSubmitted`, `postToolUse`, `sessionEnd` where supported | `sessionStart` can supply `additionalContext`; command/HTTP `userPromptSubmitted` output is dropped, so per-turn prompt-time recall cannot be claimed from that hook | Unverified; installation and probe required |
| [Codex](https://developers.openai.com/plugins/build/plugins) | 0.162.1 | Trusted local plugin lifecycle hooks and MCP | `UserPromptSubmit`, `PostToolUse`, `Stop`, `PreCompact` if present in the installed version | Prompt hook or plugin context path only after actual model-boundary probe; installing a plugin does not trust its hooks | Unverified; manual MCP until probe |

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
