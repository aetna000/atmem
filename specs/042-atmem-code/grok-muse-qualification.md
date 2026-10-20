# Grok and Muse: Mac and Windows native-session tests

Date: 2026-10-15. Branch: `feature/atmem-code-2.3.9`.
Runtime baseline: `f786f299bfbcbe73f7ce2134dd1e5939c29adb8f`.
This follow-up changes tests and evidence, not production adapter activation.

| Host | macOS 26.5.2 / Python 3.12.2 | Windows 11 build 26200 / Python 3.12.6 |
| --- | --- | --- |
| Muse Code 1.4.8-R6256.1 | Canary reaches actual local model request. Real AtMem capture, fresh-session recall and pause pass. | Local model request completes, but project hook wrapper does not execute; no capture or canary delivery. Blocked B01. |
| Grok CLI 1.0.13 (5e9a58528b76) | Real AtMem capture and pause pass. Fresh-session memory context absent, as is the separately emitted canary. | Same capture-positive, recall-negative result. |

These are controlled wiring tests, not normal activation qualification or coding
benchmarks. Ordinary AtMem enable still refuses both adapters; the lifecycle
test asserts that refusal before its explicit fixture-only enabled flag.

## What was tested

`tests/fixtures/grok_muse_probe.py` runs native binaries against a fixed-response
loopback Responses endpoint and logs actual hook inputs and outbound model
requests. Grok uses global hooks in an isolated `GROK_HOME`; it does not prove
project-hook trust onboarding. Muse uses a generated `.muse/hooks.json` with
`--trust-workspace` for that temporary directory only. Each project path contains
spaces. Grok emits snake-case event values and supplies a stable `promptId`;
Muse on Mac supplies PascalCase events and a stable `turn_id`.

`tests/test_code_grok_muse_sessions.py` additionally exercises the real production
hook, enrollment, encrypted SQLite database and canonical formation path:

1. Submit “My preferred formatter is Ruff.” and require exactly one memory.
2. Open a fresh CLI session asking which formatter to use; inspect the actual
   outbound model request, not the model's fixed answer.
3. Pause through `CodeInstall.disable`; another preference must neither create
   a memory nor receive the previously stored formatter.

Muse on Mac passes all three. Grok's test deliberately requires absent memory
context in step 2: **a passing Grok test confirms its limitation, not successful
automatic recall**. The production Grok handler already withholds unsupported
prompt context. The independent hook canary also remains absent from actual
model requests on both systems, consistent with the [Grok hook contract](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md).

The Windows Muse case fails at the first canonical-memory assertion because
the wrapper was never invoked. Repeating with Git Bash as the fixture shell and
an explicit documented `commandWindows` handler did not resolve it. The native
model request succeeds, so this is not recorded as a provider/startup failure.
The current regression marks that exact platform case as strict expected
failure; it is **not a qualification pass**. The underlying Windows hook failure
has not been isolated to a vendor defect versus another integration setting.
See the [Muse settings-level hook contract](https://meta-models.github.io/muse-code-sdk/next/guides/extend/hooks/).

## Corrections made to the probes

Muse's current Meta provider rejects `--reasoning-effort none` despite listing
it in the general help. Tests now use `minimal`. An initial invocation with
`none` failed before hook execution and is excluded from delivery results.
The Grok canary fixture explicitly recognizes `user_prompt_submit`; otherwise a
negative result could merely mean that the fixture never emitted its canary.

Changing HOME for host isolation also changes AtMem's default key location.
The lifecycle fixture now creates its own protected database key file and uses
the same explicit fixture key in the parent and child. No owner's key is copied
or exposed to a model. This corrected a fixture decryption failure, not a
production storage defect. Windows temporary-home cleanup tolerates an OS-held
file handle; no owner directory is targeted for removal.

## Reproduce

Use an installed AtMem wheel with SQLCipher and pytest, and copy `tests/` outside
the checkout. Set `ATMEM_TEST_GROK_BINARY` and `ATMEM_TEST_MUSE_BINARY` to the
version-pinned native executables, then run:

```sh
python -m pytest tests/test_code_grok_muse_sessions.py -q
```

Mac: two passes. Windows: Grok passes its capture/pause/negative-recall checks;
Muse remains a strict expected failure. Each fixture writes
`session-results.json` under pytest's temporary test directory. The separate
canary runner writes full local request and hook receipts under `--output`.
The [verification manifest](grok-muse-verification.json) pins binaries and scope.

The Mac launcher updated itself while reporting its version, from the previous
1.4.7 to 1.4.8. All reported new probes use the downloaded native 1.4.8 binary
directly, with further auto-update disabled. Windows binaries were downloaded
to a dedicated test directory, not installed into the owner's PATH or config.
Muse's Windows binary matches the official manifest checksum. Grok's checksum
is recorded for identity only; no vendor checksum was available to this probe.

No genuine provider keys, owner projects or owner memories were used. No paid
model calls, release, push, trust-store edit, or automatic-adapter promotion was
performed. Fixed responses establish request delivery, not whether a real model
uses the memory, semantic accuracy, task quality, forced compaction or latency.
The installed Mac repeat took about 75 seconds for two tests; that is harness
wall time, **not** memory-path latency.
