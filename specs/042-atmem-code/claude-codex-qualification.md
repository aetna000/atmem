# Claude and Codex: Mac and Windows session tests

Date: 2026-10-15. Runtime baseline: `f786f29` on
`feature/atmem-code-2.3.9`. This follow-up changes test fixtures and qualification
evidence only, not production adapter activation or release versions.

| Host | macOS 26.5.2 / Python 3.12.2 | Windows 11 build 26200 / Python 3.12.6 |
| --- | --- | --- |
| Claude Code 2.1.281 | Existing normal enable/capture/recall/pause/restore tests pass; additional controlled session tests pass | Native-argument controlled capture, new-session recall and pause pass; normal AtMem enable still refuses this unqualified adapter |
| Codex CLI 0.162.1 | Controlled capture, new-session recall, pause and Claude handoff pass; normal enable remains blocked | Controlled capture, new-session recall and pause pass; normal enable remains blocked |
| Codex hook trust | Matching canary is absent without trust bypass and present with the fixture-only bypass | Same paired result; no owner trust settings changed |

## What ran

The Mac installed-package run, outside the checkout, passed all eight tests:

```sh
python -m pytest tests/test_code_claude.py tests/test_code_codex.py tests/test_code_host_sessions.py -q
```

The Windows installed-package run passed all four portable host-session cases:

```powershell
python -m pytest tests/test_code_host_sessions.py -q
```

Windows received the matching versions via
`npm.cmd install -g @anthropic-ai/claude-code@2.1.281 @openai/codex@0.162.1`.
The tests resolve the native Claude executable and Codex's Node entry point,
not npm's shell shims. Model requests go to fixed-response loopback servers;
there are no paid model calls or private project/memory inputs.

Each controlled lifecycle case initializes an encrypted temporary database,
binds a temporary Git project and enrollment credential, and explicitly enables
the installation **inside the fixture only**. It then submits an ordinary
formatter preference, verifies one canonical memory, starts a separate CLI
session and observes that preference in the actual model request. After disable,
another prompt neither stores its new preference nor receives prior context.
The scripts retain exact production hook and canonical-memory handling; they do
not invent a memory or inject the expected answer directly into model input.

This is a wiring test, not a coding-quality or semantic-accuracy benchmark.
The fixed endpoint does not demonstrate that a real model used the context.
Normal Claude restore remains verified on Mac only; Windows restore/onboarding
is not inferred from fixture capture. No full-flight or forced-compaction claim.

## Windows fixture requirements and outstanding onboarding

- Claude's controlled hook uses executable-plus-arguments rather than the
  existing product's shell-command packaging. Its native Windows registry entry
  and production activation verifier remain unimplemented, and the test asserts
  that ordinary enable still refuses it.
- Codex uses a reviewed, generated PowerShell command with explicit arguments
  in the temporary fixture. Production does not acquire this test command or
  bypass the user's hook review.
- Windows Codex refuses creating helper binaries inside Windows Temp. Its
  temporary `CODEX_HOME` is therefore allocated beneath the dedicated
  `%LOCALAPPDATA%/AtMemHostTests` directory and removed after each invocation.
- The isolated environment preserves standard Windows OS variables, including
  `SystemDrive`, while excluding provider credentials. Omitting them prevented
  the initial Windows fixture's hook execution; the final paired tests use the
  corrected environment.
- The paired Codex canary differs only in its fixture-only trust-bypass flag.
  Both positive and negative cases run the same hook command format. This avoids
  mistaking a broken command for successful trust enforcement.

The [Codex hook contract](https://learn.chatgpt.com/docs/hooks) requires review
of non-managed hook definitions. The bypass flag is confined to reviewed test
fixtures, not normal onboarding. Claude's
[hook reference](https://code.claude.com/docs/en/hooks) documents its native
executable/argument form. Product qualification remains narrower than these
controlled host capabilities until normal setup/probe/restore journeys pass.

See [machine-readable evidence](claude-codex-verification.json) for counts,
artifact identity, commands and local JUnit locations. No publication was run.
