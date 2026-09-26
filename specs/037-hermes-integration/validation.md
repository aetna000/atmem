# Hermes qualification evidence — 2026-09-26

Branch: `feat/037-hermes-integration`.

## Completed work

- Checked out upstream Hermes at
  `d0288be5b3330d2442e3907185b8e9d0958297bb` in a temporary research directory.
- Inspected native provider discovery/lifecycle, context assembly, spill behavior,
  request observers, request middleware and execution middleware.
- Audited AtMem shared-bearer versus server-bound evidence credential handling.
- Added six reproducible no-network source-contract tests in
  `tests/test_hermes_upstream_contract.py`.

## Executed checks

```sh
HERMES_SOURCE=/path/to/pinned/hermes \
  .venv/bin/python -m pytest tests/test_hermes_upstream_contract.py -q
```

Actual checkout: `/private/tmp/atmem-hermes-research.srQkVi/hermes`.
JUnit artifact: `/private/tmp/atmem-hermes-research.srQkVi/host-contract.xml`.
The temporary artifact can be regenerated; the test definitions and observed
outcomes are retained here. The tests verify the commit and reject changed
audited files before probing named upstream functions with dependency doubles.
They do not import or execute the full agent, call models or replace agent code.

| Probe | Observed result |
| --- | --- |
| Pre-request observer raises authorization denial | Error swallowed; request unchanged |
| Compose user context from recall | Recall becomes replayable host content |
| Recall hook placement | Once per user turn, before tool loop |
| Request middleware exception handler | Continues without propagating guard failure |
| External prefetch output handling | Host spill path present |
| Execution middleware raises before downstream call | Downstream callback still invoked once |

**Result: six tests passed.** These passing tests establish the listed behaviors;
they do **not** mean the AtMem integration passed its safety acceptance gates.
Source-level unit probes are not installed host compatibility certification.

## Resolved scope and next action

Per-model-call revocation enforcement cannot be implemented by raising from
these observer/middleware hooks. See [contracts](contracts.md) for the supported
alternatives and the narrower recall-only guarantee. No production activation is
implemented or enabled. The user approved `authorized-at-recall-v1`: authorize
fresh recall without claiming to retract existing host context. Per-model-call
enforcement is deferred, not an integration blocker. Installed acceptance remains pending.

Basic Hermes memory-provider discovery is viable; the approved delivery profile
is fresh-recall authorization with explicitly accepted reduced capture. Installed
qualification of that profile remains pending.
No benchmarks have been run, no task accuracy exists, no paid budget was used,
and no leaderboard upload occurred. Installed acceptance, dashboard work, frozen
memory and full evaluation remain pending.

## Compatibility observations, not certifications

- Reviewed Hermes declares Python `>=3.11,<3.15`; AtMem still supports 3.10–3.13.
  Separate processes avoid forcing Hermes's interpreter range on AtMem base.
- Hermes root license is MIT. Dependency and dataset redistribution review remains
  mandatory before packaging or a paid benchmark run.
- Research ran on macOS. No Linux, native Windows or WSL installed acceptance
has been performed. No supported-version range is advertised.

## Core implementation milestone

Implemented `atmem/adapters/hermes/binding.py` and `provider.py`:

- Trusted service-side identity binding, checked against AtMem topology per operation.
- Ordinary product capture/idempotency and fresh canonical preparation; no fallback
  to previously returned context, no shadow preview disclosure and no assistant
  text promoted as an authenticated human source.
- Native Hermes MemoryProvider subclass created lazily, bounded asynchronous
  write queue, context-preserving worker, source-turn correlation, profile/session
  checks, bot/foreign-author withholding and truthful pending/error status.
- Local CLI only for now; gateway, cron and subagent profiles are rejected.

Executed against the pinned Hermes provider ABC:

```sh
HERMES_SOURCE=/path/to/pinned/hermes .venv/bin/python -m pytest \
  tests/test_hermes_binding.py tests/test_hermes_provider.py \
  tests/test_hermes_upstream_contract.py tests/test_api_contracts.py -q
```

**22 passed in 2.34s.** Includes a real temporary AtMem control-plane
capture/retry/review/activation/recall test. External intelligence is substituted
with its deterministic fallback response in that test; no quality claim follows.
Also ran existing framework-adapter/API tests alongside the initial binding
tests: **17 passed, 7 skipped** (optional framework dependencies unavailable).

Remaining at that earlier checkpoint: scoped transport/provisioning, packaged discovery and installation,
restore/dashboard integration, durable crash/freeze contracts, full installed
acceptance and DolphinBench wiring/runs. The current provider factory requires
an operator-created binding and is not yet a one-command installed integration.
Its RAM queue is not a durable checkpoint and is explicitly reported as such.
Host spill configuration still needs installer qualification. No release, live
deployment, paid calls, accuracy result or public submission occurred.

## Scoped transport and packaged-provider review checkpoint

Implemented the service-side scoped credential lifecycle (provision, disable,
rotate, revoke), encrypted binding records, bounded loopback RPC and distributable
provider payload. The public installer/admin setup journey is still pending.
Bindings start disabled. General API routes reject a Hermes credential; a browser
admin token is not accepted as a Hermes credential. Recall is checked again after
preparation. An observation whose final authorization check fails returns an
uncertain outcome rather than falsely claiming that nothing was written.

Encrypted control-store writes now use a bounded cross-process exclusive lock
and a persisted-image conflict check to prevent stale snapshots from overwriting
newer commits. Schema remains **6**, unchanged. Read-only opens avoid rewriting
unchanged encrypted containers. Slow operations still hold the store lock; an
existing process-wide lock can also delay unrelated requests. This is a safety
fix, not a throughput claim, and broader installed regression remains required.

### Final focused test run

```sh
HERMES_SOURCE=/private/tmp/atmem-hermes-research.srQkVi/hermes \
  .venv/bin/python -m pytest \
  tests/test_hermes_authority.py tests/test_hermes_binding.py \
  tests/test_hermes_provider.py tests/test_hermes_packaging.py \
  tests/test_control_store_process_lock.py tests/test_control_evidence.py \
  tests/test_evidence_protection.py tests/test_generic_control.py \
  tests/test_control_verify.py tests/test_hermes_upstream_contract.py -q
```

**91 passed, 1 skipped in 13.23s.** The skip is the native Windows replacement
semantics test on macOS (confirmed separately with `pytest -rs`). This is a focused contract/regression result,
not a full release or installed-agent acceptance result. A preceding run caught
a bot-sync regression; it was fixed and tested, including a bot repeating earlier
human text. Tests also exercise actual loopback HTTP error-code preservation and
an unexpected post-write authorization-store failure. Generic control tests now
substitute deterministic companion responses rather than contact a running local
AtBot. An earlier long-running test attempt was interrupted and is not a pass.

### Built artifact check

Built with `uv build --wheel` and installed into a new temporary Python 3.12.2
environment. This development wheel retains **2.3.7 metadata**; it is not a
published 2.3.7 replacement or a 2.3.8b1 release.

- Wheel: `/private/tmp/atmem-hermes-reviewed.3U0xQz/atmem-2.3.7-py3-none-any.whl`.
- SHA-256: `e23163710ee110bada081129d974bbf7fc1297b9d14e1c599d87852148afc9e7`.
- Probe: `tests/installed_hermes_payload.py`, run with the installed interpreter
  using `-I` from outside the repository. Checks payload contents, no eager host
  imports, directory registration against the pinned native MemoryProvider ABC,
  and safe unavailability without a service. Result: **passed**. This is **not** a full agent run.

### Read-only Claude review

Claude CLI was invoked with the `opus` alias, `Read,Glob,Grep` tools only, plan
permissions, no session persistence and an empty strict MCP configuration. No
editing or shell tools were available. The exact underlying model revision was
not verified; do not label it Opus 5.5. Claude did not run tests; Codex ran them.

Earlier review findings drove independent authorization storage (so revocation
does not wait behind slow recall), post-write uncertainty handling, stronger
workspace checks and encrypted snapshot concurrency protection. The latest
review additionally prompted moving status RPC outside the provider lock,
counting withheld syncs, handling skill normalization failures and adding tests.

Final follow-up verdict: **no new blocker for this scoped transport/provider
milestone**, conditional on the test results and trusted single-user CLI scope.
This is not approval of the incomplete full integration.

Remaining review points tracked for T006/T007/T011:

- Loopback bearer HTTP authenticates the client, not the listening server. It
  is not qualified for hostile local users or gateway deployments.
- RAM queue and sticky write errors are not durable retry/recovery. Failure
  requires inspection/reconciliation; restarting a provider does not recover
  dropped observations. Normalizer failures currently share the write-error
  counter; separate capture diagnostics belong in the lifecycle work.
- Session/turn/content identities need resume/reset qualification. Repeated
  identical text with a reset turn counter can reuse an earlier receipt.
- The pinned skill normalizer success/empty paths are tested through a stub;
  import/exception and full native normalization compatibility remain to test.
- Provider tests require `HERMES_SOURCE`; CI must supply the pinned source before
  claiming their coverage. Native Windows is explicitly denied pending ACL
  qualification; neither Linux nor WSL installed acceptance has been performed.

Installer, durable worker, dashboard, AtFlows runtime connection and installed
acceptance are still pending. No user Hermes installation, activation, benchmark,
release or submission was performed at this checkpoint.

The coordinated AtFlows read-only planning review found required implementation
gaps in unknown-cost storage, receiver-side redaction, retry/deduplication and
request-versus-turn accounting. Its Spec 006 now has a dedicated observation
contract and T060–T064. No AtFlows Hermes runtime code is claimed by this review.
The follow-up retained unresolved redaction-spec, receiver trust/recognition and
exact cross-project profile/session handoff decisions as T065–T067. They must be
resolved before affected implementation; full cross-project approval is not claimed.

## Standalone local Hermes installation — 2026-09-26

After that checkpoint, the user explicitly requested installing Hermes to explore
it now. Used the official POSIX installer with `--non-interactive --skip-browser`.
This supersedes the earlier no-installation status, not the pending acceptance gates.

- Source: `/Users/javadtaghia/.hermes/hermes-agent`, commit
  `d0288be5b3330d2442e3907185b8e9d0958297bb` (matches the research pin).
- Reported version: `v0.21.5+2453.gd0288be (2026.9.24)`, Python `3.14.7`.
- Launcher: `/Users/javadtaghia/.local/bin/hermes`. The installer added its path
  to `.zprofile`. AtMem 2.3.7 and AtFlows 0.1.3 were not upgraded or reconfigured.
- Installer built the terminal and web interfaces. Started the native Hermes
  dashboard with `hermes dashboard --host 127.0.0.1 --port 9119 --no-open --skip-build`.
  Root HTML and its referenced JavaScript/CSS return HTTP 200. This is HTTP
  verification, not visual UI or end-to-end agent testing.
- `hermes doctor` reports built-in memory active and exits 1 with optional
  tool/provider setup and a browser-dependency vulnerability warning. Browser
  installation was skipped; that does not prove the flagged dependency is absent.
  The warning remains unresolved. No doctor-fix, paid model call, gateway service
  or credential transfer was performed. Provider selection was left to the user;
  no claim is made that a live model conversation has been verified.
- AtMem and AtFlows plugins are **not installed or activated in Hermes**. This
  does not complete T011 or cross-project qualification. Native Hermes history
  is not automatically imported by the planned provider switch.

Open `http://127.0.0.1:9119/` to explore the Hermes interface. Run `hermes setup`
for provider selection, then `hermes` for terminal chat. This dashboard is a
loopback-only process, not an auto-start service; `hermes dashboard --stop` stops
Hermes dashboard processes. Existing AtMem/AtFlows dashboards remain separate.

Claude performed a read-only handoff review (same restricted tools as above).
Its requested distinctions—native dashboard vs integration, HTTP checks vs full
acceptance, unchanged companion installs and unresolved dependency warning—are
retained here. No runtime adapter code changed during this installation turn.

## Native provider-list milestone — 2026-09-26

Supersedes the previous **AtMem plugin not installed** status. AtFlows remains
unconnected. Spec/plan/tasks were updated first, Claude reviewed them read-only,
findings were resolved, and its final design verdict was **no blockers for
inactive discovery** before this slice's code edits. Two further read-only code
reviews checked the implementation; the final review found no inactive-install
blockers. Claude used its `opus` alias, Read/Glob/Grep only, plan permissions,
empty strict MCP configuration and no session persistence. No exact model version
is inferred from that alias.

### What was built

- Product `atmem hermes install/status --hermes-home PATH [--json]`; installation
  is preview-only unless `--apply` is supplied. Native config, memories and
  credentials are not written. An owned hash receipt supports idempotent checks;
  edited/unmanaged/older payloads are not overwritten. Preview needs no AtMem Home.
- Atomic no-replace publication on macOS/Linux, owner/path checks, lock,
  fsynced source/receipt files, invisible double-underscore staging directories.
  Linux code is not execution-qualified by this macOS run. Native Windows is
  refused. Ancestor-directory trust follows the current local-user threat model.
- Real native provider registration survives missing/malformed/insecure files,
  including FIFO, integer endpoint and deeply nested JSON. No secret diagnostic
  echo; unconfigured discovery makes no RPC. Configured discovery uses the
  documented one-second socket budget, not a strict total deadline.
- Native memory-setup hook does not select AtMem; no generic credential form.
  Metadata labels local CLI-only support and pins Hermes base `0.21.5`.

### Verification

Final focused command (macOS, AtMem test Python 3.12.2, Hermes Python 3.14.7):

```sh
HERMES_PYTHON=/Users/javadtaghia/.hermes/tools/python-3.14.7+20260901-darwin-arm64/bin/python3 \
HERMES_SOURCE=/Users/javadtaghia/.hermes/hermes-agent \
.venv/bin/python -m pytest \
  tests/test_hermes_install.py tests/test_hermes_packaging.py \
  tests/test_hermes_native.py tests/test_hermes_provider.py \
  tests/test_hermes_authority.py tests/test_hermes_binding.py \
  tests/test_hermes_upstream_contract.py tests/test_control_store_process_lock.py \
  tests/test_control_evidence.py tests/test_evidence_protection.py \
  tests/test_generic_control.py tests/test_control_verify.py -q
```

Result: **111 passed, 1 skipped, 33.64 seconds**. The skip is an existing native
Windows evidence-file replacement test. Tests requiring host variables skip when
those variables are absent; this run supplied them explicitly.

Actual managed Hermes discovery/status helpers load the packaged provider from
a temporary Home. Guarded dashboard selection rejects unavailable AtMem. The
native memory setup hook preserves selection. A separate test exercises the
generic picker write and actual `_init_memory`: a forced unavailable selection
warns and leaves native memory functioning. This is an upstream behavior, not
AtMem enforcement over all settings APIs. Raw/settings paths can also bypass
readiness. Missing selected providers may trigger upstream catalog recovery;
we neither implement nor claim control of that behavior.

The configured test uses the real product scoped HTTP service and the native
directory provider in separate processes: capture a preference → flush → normal
AtMem reviewer admission → activate the temporary product authority → recall in
a new process/session. Unsupported non-CLI initialization withholds reads/writes.
The companion is deliberately unavailable so normal deterministic product fallback
is exercised. No model call, benchmark shim, retrieval-quality or full-chat claim.

Initial native-test attempts timed out because Hermes bootstrap treated the
empty test Home as a fresh dependency installation. They are not passes. The
test launcher now initializes the already-installed Hermes runtime first, then
selects a disposable data Home before discovery. A forced-selection test exposed
the same bootstrap ordering issue; the corrected three native tests passed.
Initial build attempts found no `build`/`pip` module in the dev environment;
the successful build used `uv build --wheel`.

### Built artifact and local result

- Wheel: `/private/tmp/atmem-hermes-native.QKqHqn/atmem-2.3.7-py3-none-any.whl`.
- SHA-256: `8aea9508657fcaf73b654e2ee2bc1267d71a2be6ab29c90828edf80ec913627a`.
- This is a **development artifact with unchanged package metadata**, not a new
  2.3.7 release or published 2.3.8 beta. Installed in an isolated temporary venv.
- `python -I tests/installed_hermes_payload.py HERMES_SOURCE HERMES_PYTHON`, run
  outside the checkout with that installed interpreter, passed including real
  native discovery. The first attempt rejected macOS's unresolved temporary-path
  alias; the probe now passes the resolved path as the installer requires.
- Applied using the built artifact's CLI to
  `/Users/javadtaghia/.hermes/plugins/atmem`; no dependency installed into Hermes.
  Only Hermes dashboard was restarted, on `http://127.0.0.1:9119/`; root HTTP 200.
- The actual native dashboard metadata helper reports selected `builtin`, an
  `atmem` row with `available: false`, `status: unavailable`, and the expected
  directory. Hermes also reports `configured: true` for providers with no form
  schema; this **does not mean a connection exists**. Its availability/status
  fields are the relevant gate. Native provider resolution matches our directory.
- Unauthenticated hub HTTP requests return 401 as expected. We verified the
  dashboard metadata helper, not an authenticated browser screenshot.
- Hermes config SHA-256 before and after:
  `77bc4ae491f726e4af08470ecad4555bc2a0816c5ac3afd42adabf14577a54ff`.
- Packaged source hashes match the installed receipt; generated Python bytecode
  is excluded from source-integrity claims. Runtime module cache requires a
  dashboard restart after changed payloads.

Local inspection command for this development installation:

```sh
/private/tmp/atmem-hermes-native.QKqHqn/venv/bin/atmem hermes status --hermes-home /Users/javadtaghia/.hermes
```

The ordinary installed AtMem 2.3.7 CLI/service is unchanged and does not yet ship
these commands or scoped Hermes endpoints. No live connection/credential was
provisioned, no native provider was replaced, and no AtFlows activation, benchmark,
commit, tag or publication was performed. Full T004–T026 acceptance is still
pending; T027–T031 complete only the bounded native-list milestone. Before live
connection, qualify credential backup/export handling, durable capture and the
host's fallback/selection behavior.

### Authorized local AtMem update — 2026-09-26 (T032)

This later operation supersedes the preceding statement that the ordinary local
AtMem service was unchanged. It does not complete live Hermes connection setup.

- Read-only Claude Opus deployment review found no code blocker; required artifact
  provenance, rollback material, a stopped-service backup, and honest version labeling.
- Additional regression gate: dashboard daemon and framework adapter/conformance/
  packaging tests: **19 passed, 7 skipped**. Skips are not passes.
- Installed the exact development wheel above, SHA-256
  `8aea9508657fcaf73b654e2ee2bc1267d71a2be6ab29c90828edf80ec913627a`,
  using `/Users/javadtaghia/miniconda3/bin/python -I -m pip install
  --force-reinstall --no-deps`. This uncommitted development artifact still reports
  **2.3.7**; it is not a published beta or a replacement public release.
- Protected rollback directory: `/Users/javadtaghia/atmem-local-update-jDM0YI`.
  It contains the downloaded original release wheel, exact prior installed package
  and dist-info archive, and a stopped-AtMem filesystem archive of the Home.
- Built-in Home snapshot refused the older Home without `manifest.json`; no Home
  migration was performed. Filesystem archive verification compared 6,305 regular
  files by SHA-256 against source: **no differences**. AppleDouble metadata entries
  were excluded from this comparison. Other companion processes were left running.
- Home archive SHA-256:
  `6e063e3fb8b172465da4ec43e892dc22af2c6c7dddf0b5eb61bffa42aa86bbfc`.
  Prior installed-package archive SHA-256:
  `7e5f0a85734dd55b6465385f12dfbd2867eb71077f69aabc2a16adb90660c610`.
- Daemon restarted at `2026-09-26T12:53:59.978700+00:00`, PID 51419,
  existing port 8768 and same miniconda interpreter. Root dashboard HTTP **200**.
  Unauthenticated `POST /v1/hermes/status` returns **401 unauthenticated**;
  an Origin-bearing request returns **403 Hermes operation denied**.
- Isolated installed import resolves to miniconda site-packages, not this checkout.
  Installed `atmem hermes status` verifies the existing plugin source hashes and
  reports `installed`, `activation: not_performed`, `connection: not_checked`.
- Companion package versions unchanged: AtFlows **0.1.3**, AtBot **0.1.0**.
  No dependency upgrades, provider selection changes, live scoped credentials,
  AtFlows activation, commit, tag, or publication occurred.
- Pre-existing environment `pip check` conflicts (limits/packaging,
  opencv-python/numpy, aiobotocore/botocore) were recorded before deployment and
  intentionally not repaired by this package-only update.

The service now contains Hermes RPC support. The Hermes provider can still show
**unavailable** until the separate scoped connection and activation work is
completed; this deployment does not establish end-to-end readiness.
