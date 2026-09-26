# Implementation plan — Hermes integration

**Status:** Planning complete enough for the source/contract qualification spike;
implementation must resolve its gates before activation or paid evaluation.

## Technical context and ownership

AtMem is Python 3.10–3.13 with a local service, canonical storage, encrypted
evidence, framework adapters and a dashboard. Hermes is an independently managed
agent runtime. Use a profile-local directory provider with minimal host-side
dependencies and bounded authenticated loopback calls to AtMem. Package entry
points may be supported for owner-managed environments after installed tests;
they are not the default managed-Hermes installation strategy.

Reuse `atmem/control/`, `atmem/adapters/base.py`, `atmem/client.py`,
`atmem/service/`, `atmem/server/auth.py`, `atmem/evidence/` and existing lifecycle
contracts. Verify actual routes and scoped credentials before choosing endpoints.
Never interpret an agent-supplied role/subject as authorization. A connection
credential is bound server-side to the installation/profile and least privilege.
No admin credential is exposed to the model or normal memory tools.

Proposed new files (not existing implementations):

| Location | Responsibility |
| --- | --- |
| `atmem/adapters/hermes/` | Product binding, capability declarations, hooks, correlation |
| `atmem/adapters/hermes/package.py` and `assets/plugin_entry.py` | Distributable minimal provider directory; packaged client/provider sources reused without adding an AtMem dependency to Hermes |
| `atmem/hermes_install.py` | Profile discovery, preview, atomic activation/restore receipts |
| `atmem/control/memory_checkpoints.py` | Product snapshot/freeze verification if existing contracts are insufficient |
| `tests/test_hermes_*.py` | Authority, lifecycle, configuration and installed tests |
| `docs/website/integrations/hermes.md` | Public setup, limitations and troubleshooting |
| `benchmarks/dolphinbench/` | Inert upstream driver, pinned manifests, commands and report schema |
| `tests/benchmarking/test_dolphinbench_*.py` | Isolation, accounting, recording and packaging tests |

Follow existing dashboard structure discovered during implementation; extend its
integration/settings/status views rather than introduce another dashboard. AtFlows
continues to own visualization and telemetry. Its aligned
`specs/006-guided-integrations/` now owns the Hermes guided connection and
observability work. Both installed products must pass the shared parity gates;
AtFlows remains optional for users, not optional integration coverage for this target.

## Phase A — Source and contract qualification

### Immediate native-list slice (user priority, 2026-09-26)

Implement this bounded part of T005/T006 before full activation. Existing scoped
transport is unchanged; no public/admin credential is needed to install inactive
code. T027–T031 below refine execution order for this slice and do not mark the
larger T006/T007/T011 tasks complete.

1. Extend packaged `assets/plugin_entry.py` so missing connection files register
   a real native MemoryProvider in an unavailable state, with an actionable reason.
   Loading a configured provider continues to use the existing scoped client.
   Do not turn bad config into a working fallback; errors must be secret-safe.
2. Implement `atmem/hermes_install.py` and a bounded `atmem hermes install/status`
   CLI surface. Default install is preview; explicit apply stages the packaged
   files and hash receipt in a sibling directory then atomically renames it into
   `<selected-home>/plugins/atmem`. No native/config/credential writes. Validate
   owner, directory permissions and symlinks; serialize installer operations.
   Existing identical managed files are a no-op; modified/unmanaged installations
   refuse overwrite. Future upgrade/restore must use the same ownership receipt.
3. Use real Hermes discovery plus dashboard status helpers against a temporary
   Home. Check unavailable provider, secret-safe reason, native default unchanged,
   and configured normal capture/recall through the existing scoped service.
   No benchmark imports, live model calls or host dependency modifications.
4. Build/install artifact, Claude read-only code review, then apply only this
   inactive provider payload to the user's Hermes Home. Verify the live Hermes
   metadata endpoint contains AtMem. Restart only the Hermes dashboard after a
   changed payload; do not restart AtMem/OpenClaw or unrelated agents.

Connection and activation remain explicit subsequent product operations. The
live AtMem 2.3.7 does not ship this scoped Hermes transport; do not silently patch
its installed files or enable a dead endpoint. This slice must report that
limitation rather than mark the provider ready. Native memory remains selected.

### Design-review resolutions for the native-list slice

- Both provider states expose a no-write `post_setup(home, config)` hook so
  `hermes memory setup atmem` cannot silently select the plugin. The generic
  plugins picker can write selection directly; report and test this host limit,
  not a nonexistent veto. Forced unavailable selection triggers the host warning
  and native fallback; do not represent it as governed operation.
- Unconfigured discovery does bounded local reads only. Configured availability
  uses a one-second socket budget, an explicit host-contract deviation; do not
  claim strict cancellation of slow response headers. Status accepts the optional
  provider config argument expected by the native CLI.
- Manifest declares `kind: exclusive` and static setup guidance. The dashboard
  lacks a dynamic reason field; do not add generic config fields for credentials.
- Preview/status never initialize AtMem Home or write locks. Apply serializes
  through a sibling lock, stages four payload files and a hash receipt, fsyncs
  them and publishes with an OS no-replace rename (macOS/Linux). Reject native
  Windows, symlinks, unsafe permissions, unmanaged or edited payloads. Identical
  managed installs are no-ops; upgrades are deferred, not implicit overwrites.
  Apply may create the missing `plugins/` parent in an existing Home. Unsupported
  no-replace primitives fail closed, without ordinary rename fallback. Status
  distinguishes an intact older managed payload from user edits.
- Native discovery tests report actual resolved directory and disabled state,
  including collisions with bundled providers. Test interruption before/after
  publication; retain unknown staging directories rather than deleting them.
- Ignore only regular generated `__pycache__` entries in ownership checks; reject
  extra source files. Use `__atmem_stage_*` directories (both scanners ignore
  them), explicit exclusive-kind metadata, and record the exact tested host pin.
  Always restart the local dashboard after changed payload installation.
- Generic settings/raw-config routes also bypass readiness, as does the plugin
  picker. Test and document this boundary rather than promise a veto. Label
  discovery/status CLI-only and test failed initialization cannot read or write.
  Missing-provider catalog reinstallation is an upstream risk, not our updater.
- SC-008 capture means proposal creation followed by normal review/admission,
  not automatic trust. Connection provisioning on the user's live Home remains
  deferred, including credential export/backup protection.

Inspect the research-pinned Hermes MemoryProvider, MemoryManager, registration,
actual model-call context assembly, tool dispatch, background work and spills.
Pin a release/commit and matching environment. Map every intended capability to a
real hook and test. Verify provider discovery on managed and owner-managed setups.
Inspect native MEMORY.md/USER.md coexistence: provider selection alone is not
exclusive governance of all host memory. Default to clearly labeled coexistence;
no automatic native import or deletion.

Gate: authorize fresh recall before returning provider output and prevent
uncontrolled spill. The approved `authorized-at-recall-v1` profile does not require
a per-model-call veto; that stronger capability is deferred. Verify output placement
without claiming control of already disclosed context. Record residual retained-history
exposure and unsupported host modes. Do not manufacture full capture from a
post-turn transcript. Audit existing scoped RPC/auth before implementing missing
versioned endpoints, with bounded payloads and denial tests.

## Phase B — Product provider and setup

State progression: discovered → ready/non-influencing → explicitly active →
degraded or restoring → restored. The readiness phase does not replace the
current Hermes provider. Store activation generation, backed-up field values,
profile identity, package hashes and restore state under governed configuration.
Use atomic operations and conflict checks so restore cannot overwrite user edits.

Bind one immutable scoped connection per profile/session; reject untrusted
cross-profile overrides. Map capture to proposals, not privileged admission.
Use existing policy before returning content; record decisions and exact
supported delivery evidence. Reject or withhold oversized context before Hermes
can spill it; check byte/character conversion and host output wrappers in tests.

Initial configurable bounds: 5-second local RPC timeout, maximum 128 queued
observations per connection and 10-second graceful drain. A queue entry is not a
durable acknowledgment. Persist through existing encrypted product mechanisms;
bounded context-aware host workers report backpressure/errors. Retry the same
operation identity, never duplicate accepted writes. Timeout never widens scope.
Freeze fails if acknowledged work is incomplete. Limits remain visible and are
measured rather than marketed as performance guarantees.

Expose `atmem hermes install/status/verify/activate/upgrade/restore` as the
planned command group. Hermes's native setup/status
surfaces and AtMem UI reflect the same saved configuration and health. Provide
one guided setup path, precise restart requirements and secret-safe copy commands.
Do not install or activate Hermes merely because AtMem is upgraded.

Use `parity.md` as the release checklist. AtMem owns provider switching and
credentials; AtFlows owns its observation connection. Neither installer rewrites
the other's owned keys. Preview partial success explicitly if one component fails.
Provider switching is not historical-memory import. Add Hermes discovery to
`atmem init` and consolidated diagnostics to `atmem status`; recommend exact
repairs using detected Homes and endpoints. Verify with normal installed sessions,
not benchmark helpers. Extend existing dashboards rather than build a third UI.

## Phase C — Product acceptance, independent of benchmark

Build wheel/install into clean environments. Verify remember/new-session recall,
scope denial, deletion/revocation races, retry-safe writes, process interruption,
failed restore and unavailable services. Exercise concurrent profiles/workspaces,
child/cron default denial, first-turn and repeated model-call context freshness.
Run compatibility tests for OpenClaw and existing adapters. Qualify OS claims
separately, including real Windows/WSL distinctions.

Run encrypted evidence/disclosure gates and reconstruct supported captured bytes
from a copied AtMem store without host logs. Dashboard screenshots and tests
must show unsupported/unobserved boundaries honestly. No benchmark package may
be installed/imported for these acceptance tests.

## Phase D — Read-only evaluation and recording contracts

Implement durable scoped memory checkpoints as product functionality if absent.
Snapshot manifest includes schema/version, canonical and required derived-state
generation/content identity, encryption/key reference (not key material), scope
and completed-write watermark. Verify actual restored memory, not labels. Freeze
does not imply a mutable live user Home is globally locked: benchmark personas
use isolated disposable Homes. Block mutations at the product authority boundary.
Authorized evidence/usage append to a separate sink so memory remains unchanged.

Only after Phase C/D gates implement the five upstream driver methods. The driver
selects persona/phase, invokes installed Hermes with its ordinary AtMem provider,
binds supplied MCP apps and records outcomes. Restrict filesystem/network/tool
access to prevent answer leakage and real side effects. Do not replace the agent
loop or supply extraction, ranking, admission, recovery or tailored task hints.
Prove recorded model requests match actual requests, including injected context;
stop if Hermes compaction cannot be represented by upstream export format.

## Phase E — Budgeted evaluation

1. **No-cost checks:** mock provider responses and local MCP startup, admission,
   isolation, recording, upstream `prepare` and package-schema validation. These
   prove plumbing only and produce no accuracy claim.
2. **Public-data pilot:** propose a US$20 total cap, but do not spend until a new
   run budget/model/grader approval is recorded. Historical unrelated budget
   approval is not reused. Select pilot IDs deterministically before running and
   preserve the selection manifest; use actual public data, label partial scale.
   Read-only credentials checks may report presence, never values. Reserve
   maximum in-flight call cost and stop before exceeding cap; if pricing or output
   bounds are unknown, do not launch. Include grading in the cap.
3. **Full run:** quote measured ingestion/evaluation/grading estimates and obtain
   explicit budget. Full histories and all 600 tasks; exact benchmark/model/tool
   settings, AtMem config and binary hashes frozen in manifest. Start with native
   Hermes and AtMem arms; Mem0 is a separate matched arm when approved/available.
   Report missing arms rather than present historical values as rerun controls.
4. **Replication/report:** preserve every failure and checkpoint; paired task
   deltas and bootstrap intervals with seed and persona strata, plus raw per-task
   data, counts and three-persona sample limitation. Plan three independent
   repeated full runs per compared arm for superiority claims, budget permitting;
   one run remains descriptive. Keep development/pilot IDs marked in full-suite
   results and report untouched-task analysis separately without calling the
   already public dataset private held-out. No cherry-picked best-run reporting.

Report action successes/600, overall and per persona; agent/memory cost, separate
grader/infra cost, p50/p95 end-to-end and recall latency, throughput, token usage,
timeouts/refusals, retries, RSS/CPU/disk and capability limits. Supplemental safety
tests remain separate from official accuracy. Keep original evidence protected;
publish only authorized credential-free exports without silently rewriting raw
interactions. Validate the 256 MiB website limit. Upload only upon explicit user
approval; maintainer verification is a separate process.

## Phase F — Documentation and release decision

Target AtMem `2.3.8b2` (selected 2026-09-27). This is a release target, not a
published version. The beta requires an installable opt-in integration and all
applicable product gates, but not a winning/full DolphinBench result. Do not
delay a qualified integration beta merely to reach a leaderboard target.

Update API/setup/integration/troubleshooting coverage, runtime compatibility,
roadmaps and website docs manifest when a release is actually selected. Preserve
2.3.8 maintenance priorities. Only publish a Hermes release after installed gates;
keep the website PR owner-reviewed and deploy from merged main through Firebase
CLI under the existing release process. No tags/pins change in this planning task.

## Constitutional checks

Local service update requested after T031: verify the reviewed wheel hash and
installed runtime location; preserve package rollback plus a protected Home
backup while the dashboard is stopped. Install only AtMem with no dependency
upgrades, restart the daemon on its existing port, and check ordinary dashboard
health plus unauthenticated Hermes status denial. Keep Hermes inactive. This
supersedes the native-list slice's no-AtMem-restart restriction only for this
explicit update. Do not relabel the development wheel as a published beta.

Authority stays in AtMem; host-specific behavior stays in adapter; activation is
explicit/reversible; identity is enforced; evidence uses existing encryption and
audited access; local operation and base package independence are retained.
Benchmarks measure installed features only. A host/API prerequisite not met is a
blocked capability, not an exemption from these rules. Review Spec 011/019/020/
028 dependencies before implementation and run Spec Kit analysis before code.
