# Coding-agent host capability matrix

**Qualification inventory, updated 2026-10-15.** Tests and limitations are recorded in [implementation-status.md](implementation-status.md). Portable core results do not qualify a host. Copilot CLI 1.0.98 is now qualified separately on macOS and Windows 11; see [probe results](copilot-cli-probe.md). Only the tested subset below may be advertised as automatic.

| Host surface | Local version | Documented extension path | Candidate capture events | Candidate recall boundary | Current claim |
| --- | --- | --- | --- | --- | --- |
| [Muse Code](https://meta-models.github.io/muse-code-sdk/next/guides/extend/) | 1.4.8-R6256.1, macOS and Windows 11 | Project hooks and MCP; [hook reference](https://meta-models.github.io/muse-code-sdk/next/guides/plugins/reference/hook-events/) | Controlled real Mac prompt capture passed; Windows project hook wrapper not invoked | Actual Mac model request includes canary and recalled memory; Windows model request succeeds without hook context | Blocked B01 for normal activation; Mac controlled wiring passed, Windows hook execution blocked |
| [Claude Code](https://code.claude.com/docs/en/hooks) | 2.1.281 | Lifecycle hooks and MCP | Real user-prompt capture tested; tool outcome/flush contracts tested separately | Actual local Anthropic request contained the hook canary and, in a new session, recalled memory | Automatic prompt capture/recall on tested macOS; partial evidence coverage, not full flight reconstruction |
| [Grok CLI](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md) | 1.0.13 (5e9a58528b76), macOS and Windows 11 | Session, prompt, tool and stop hooks; [MCP](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/07-mcp-servers.md) | Real capture and pause passed on both systems with isolated global hooks, not project-trust onboarding | Prompt canary and fresh-session memory both absent from actual local model requests; a different delivery boundary is required | Blocked B02; no automatic activation |
| [GitHub Copilot CLI](https://docs.github.com/en/copilot/reference/hooks-reference) | 1.0.98, macOS and Windows 11 | CLI hooks and [plugin/MCP](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference) | Native executable/arguments, explicit event dispatch and journal invocation identity; actual prompt capture, replay and scope gates tested | Ordinary prompt context observed in new and resumed CLI sessions on each OS; startup recall omitted to avoid duplication | Automatic prompt capture/recall on both tested OSes following workspace trust and offline activation probe; partial evidence only |
| [Codex](https://learn.chatgpt.com/docs/hooks) | 0.162.1 | Trusted project `.codex/hooks.json`, lifecycle hooks and MCP | Actual prompt hook and AtMem capture passed in an isolated trusted fixture | Actual Responses request contained the canary; actual captured memory transferred to a Claude session | Controlled wire probe passed; default activation blocked B04 pending persistent user-trust onboarding |

## Tested platform cells

| Surface | macOS 26.5.2, Python 3.12.2 | Windows 11 26200, Python 3.12.6 | Linux aarch64, Python 3.12.15 |
| --- | --- | --- | --- |
| Encrypted Code core, CLI/HTTP settings and encrypted bundle round trip | Installed wheel passed | Installed wheel passed | Installed wheel passed |
| Dashboard interactive browser journey | Chrome passed | Not run | Not run |
| Claude 2.1.281 prompt capture/recall, enable/pause/restore | Passed | Controlled capture/recall/pause pass; normal activation and restore unqualified | Unverified |
| Codex 0.162.1 controlled model-boundary probe | Capture/recall/pause pass with fixture-only trust flag | Capture/recall/pause pass with fixture-only trust flag; normal activation blocked | Unverified |
| Copilot CLI 1.0.98 prompt capture/recall, enable/pause/restore | Passed | Passed | Unsupported automatic adapter |
| Muse 1.4.8 controlled prompt path | Capture/recall/pause passed; normal activation blocked | Model call passed; hook execution blocked | Unverified |
| Grok 1.0.13 controlled global hooks | Capture/pause passed; recall absent | Capture/pause passed; recall absent | Unverified |

The 2026-10-15 [Claude/Codex rerun](claude-codex-qualification.md) passed eight
installed-package Mac tests and four installed-package Windows tests. Controlled
Windows wiring does not qualify normal activation or restore. Codex's paired
trust test observes no canary without the fixture bypass and a canary with it on
both OSes; production does not use that flag.

The separate [Grok/Muse native-session probes](grok-muse-qualification.md)
establish the narrower results above. Grok's passing regression explicitly tests
absent recall; Windows Muse is an expected failure, not a supported adapter.

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

## Qualification tiers and remaining acceptance

The current positive matrix entries qualify **automatic prompt capture/recall**
only. They do not close the completed-work, compaction or full-reconstruction
gates. Keep these separately versioned per host/OS:

| Tier | Required evidence | Present claim boundary |
| --- | --- | --- |
| Prompt automation | Normal enable/trust, real capture, new-session context submission/model-boundary probe, pause/resume and restore | Only the positive prompt cells above |
| Task-outcome capture | Authorized real tool/test attempt with bound command/source/environment/result receipts | Pending; no automatic experience formation claim from prompt tests |
| Compaction/flush recovery | Forced compaction, shutdown/restart, idempotent flush and no lost pending item | Pending unless separately evidenced |
| Full reconstruction | All required model/tool/media boundaries and evidence-only disaster reconstruction | Blocked B05; current Code capture remains partial |

Spec 042 FR-027/T059 owns expanded tier qualification. T060 issues exact
capability receipts for the Click pilot. A tier cannot be inferred from another.

## Phase 3 probe checklist (tier-specific)

1. Pin the installed host binary/plugin version and OS; inspect the host's approved hook configuration without changing it.
2. Install the AtMem adapter only after user selection and preview; confirm the hook actually runs in a clean session.
3. Submit a harmless unique canary context at the nominated boundary; verify the host acknowledgement and, where observable, the model-input boundary. Do not infer delivery from a successful hook exit alone.
4. For task-outcome qualification, capture a real authorized tool/test attempt with bound outcome evidence. Separately force compaction and process exit to qualify flush/recovery. Pending tiers remain open and do not invalidate a narrower, truthfully labelled prompt-only result.
5. Start a second session with a different supported coding agent on the same authorized project. Verify shared recall, private-lane isolation, source attribution and context budget.
6. Test disabled `auto_capture` and `auto_recall` settings, paths containing spaces, service timeout, malformed event, hostile local process, host upgrade, disable and exact prior-config restoration.
7. Record `automatic prompt capture/recall`, `manual MCP`, `degraded`, or `unavailable` with exact tier receipts. Only the qualified automatic tier supports its particular no-manual-call claim; it does not establish learning from completed work or full reconstruction.

The event sequence is inspired by [Mem0's Codex integration](https://github.com/mem0ai/mem0/blob/main/docs/integrations/codex.mdx): first-prompt recall, post-tool/stop capture, pre-compaction and session-end flush, and explicit search later in the session. AtMem does not inherit Mem0's cloud dependency or its exact hook semantics; each host adapter must pass the local probes above.
