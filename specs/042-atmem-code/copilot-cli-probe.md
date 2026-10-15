# Copilot CLI integration qualification

Date: 2026-10-15. Host: macOS. CLI: `@github/copilot` 1.0.98,
installed globally using `npm install -g @github/copilot`.

Tests use temporary Git repositories, isolated `COPILOT_HOME`, explicit fixture
workspace trust, `COPILOT_OFFLINE=true`, and loopback protocol servers.
The servers return fixed text, not model-generated answers. No paid inference,
GitHub authentication, owner configuration, or production memory is used.

| Boundary | Observed outcome |
| --- | --- |
| CLI prompt execution | Exits successfully and returns the local server's response |
| Hook discovery | Repository hooks execute after explicit fixture workspace trust |
| Startup delivery | Unique startup canary appears in the actual model request |
| Ordinary prompt delivery | Unique prompt-hook context canary appears in the model request, contrary to the current reference |
| Native payload | `sessionId`, timestamp, cwd, prompt; no event discriminator or stable prompt/turn ID |
| Normal setup/enable | Production registry and offline activation probe pass, without an activation bypass |
| Workspace trust | Missing trust refuses enable without changing owner hooks or trust |
| Capture | An ordinary formatter preference creates one canonical memory without a memory-tool call |
| New-session recall | A separate session's actual model request contains the saved preference |
| Resume | An identical question in a resumed session receives context again |
| Disable | The next prompt neither captures new facts nor injects saved memory |
| Re-enable | Recall resumes using existing memory |
| Existing hooks/uninstall | Owner handler remains active; uninstall restores original file bytes exactly |
| Failed reinstallation | A failed activation verifier restores the owner hook file and leaves memory disabled |
| Native settings rewrite | Copilot-managed JSON-with-comments remains readable for reinstallation; owner trust is never rewritten by AtMem |
| Cross-agent handoff | Normal Copilot→Claude and Claude→Copilot capture/recall pass at actual model request boundaries |
| Identity/safety unit tests | Replay, distinct identical prompts, missing/ambiguous journal, wrong version/session, traversal, symlink, bounded tail, secrets and cross-repository refusal |
| Tool-outcome unit test | Native tool result does not become an unsupported canonical fact |

The original adapter captured zero memories. The corrected adapter supplies
the event explicitly in its command and matches the exact native input against
the current session journal's `hook.start`. It uses the host-issued
`hookInvocationId`, never prompt text or timestamp alone, as the stable identity.
Completed owner hooks are excluded when identifying the current live invocation;
ambiguous concurrent matches withhold processing.

Only the named session's version/session header and a bounded 2 MB journal tail
are read. The transcript is not imported as memory. The journal is a live adapter
input, not canonical authority: accepted observations and context receipts are
retained independently by AtMem. Missing, mismatched, symlinked or unqualified
journals withhold capture/context.

The native settings reader accepts JSONC comments and trailing commas without
stripping comment-like text inside quoted strings. This fixes a second issue
found after Copilot rewrote its own `config.json` during the reinstall test.

Run:

```sh
python -m pytest tests/test_code_copilot.py tests/test_code_copilot_events.py -q
```

The reference says command/HTTP prompt-hook output is dropped, but this exact
installed version demonstrably injects top-level `additionalContext`. Production
support is pinned to CLI 1.0.98 on macOS. Startup recall is omitted to avoid
duplicate injection; ordinary prompt recall precedes capture.

Activation uses a clean temporary project and isolated Copilot configuration,
so it does not run the owner's unrelated project/user hooks or change their
trust store. A short-lived credential-bound probe permits only its exact random
canary prompt in that temporary repository. Ordinary events still require the
enrolled real repository. Failed activation restores previous hook configuration.
Production context receipts say `submitted`; only controlled endpoint tests and
the activation probe independently establish `model_input_observed`.

Coverage remains partial and `not_reconstructable`. No complete tool/model/media
flight reconstruction, forced compaction, coding-quality or latency benefit is
claimed. Sandbox policies that prevent journal/database access cause withholding;
AtMem does not widen sandbox grants. No release or phase 9 evaluation was run.

Reference: [GitHub Copilot hooks](https://docs.github.com/en/copilot/reference/hooks-reference).
These observations qualify CLI 1.0.98 on this Mac only, not VS Code or cloud agents.

## Installed-artifact evidence

The final local wheel passed 79 portable-core tests (10 host tests deliberately
skipped there), followed by all 16 Copilot host/identity tests outside the source
checkout. The latter includes actual Copilot↔Claude handoff. Machine-readable
commands, artifact digest and scope are in [copilot-verification.json](copilot-verification.json).
The package retains the baseline version for this local preview; no release was
published. Earlier cross-platform and remote CI evidence is not relabelled as
verification of this follow-up.
