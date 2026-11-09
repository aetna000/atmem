# Spec 050 implementation evidence — 2026-11-09

Implementation authorized by owner request to start all specified features.
Execution follows `.agents/skills/speckit-implement/SKILL.md` in task order.

## T001 — complete

- Native/AtMem/candidate comparison definitions, immutable baseline commit,
  synthetic corpus, verification tiers, metric denominators, all seven success
  gates, zero-call default and three-candidate cap recorded in
  `docs/benchmarks/verified-memory-feedback.md`.
- Six bounded synthetic task definitions and hashed corpus manifest under
  `tests/fixtures/feedback/`. No measured baseline or quality result asserted.
- Offline `atmem.feedback.baseline` validates those inputs and refuses changed
  memory, split/chronology leakage, unbounded resources, relaxed gates,
  self-approved authority and self-reported success.
- 31 focused preflight tests passed on macOS / Python 3.12.13 / pytest 9.2.0.

## T002 — initial blocker (historical; remediation below)

Source commit pinned to `d0288be5b3330d2442e3907185b8e9d0958297bb`;
version/OS limitations and exact function paths documented in
`docs/verified-memory-feedback.md`.

Four source-contract probes passed, reproducing normal veto, deny-wins, the
fail-open hook-dispatch exception and argument modification after policy checking.
The latter two are conformance failures against FR-014/015 and SC-004, not passes
of those requirements. Local callbacks simulate effects; this is not installed
host conformance. No installed enforcing version could be qualified from
those initial results. The earlier absent-interpreter diagnosis was incorrect:
the shell launcher uses a present managed Python runtime. Launcher availability
was not a blocker, and no launcher was executed or changed.

Invocation:

```sh
HERMES_SOURCE=/Users/javadtaghia/.hermes/hermes-agent .venv/bin/python -m pytest -q \
  tests/test_feedback_baseline.py tests/test_feedback_hermes_boundary_prerequisites.py
```

Result: 35 passed. No network/model calls, actual tool writes, user-memory
mutation, Hermes launch, production activation, release or paid evaluation.
The only installed dependencies are in this worktree's ignored `.venv`.

Regression invocation added `tests/test_action_guard.py` and
`tests/test_hermes_upstream_contract.py` under the same pinned source environment:
97 passed in 1.94 seconds. `git diff --check` passed. This verifies existing guard
behavior and reproduces source contracts; it does not upgrade the host capability.
The isolated test environment occupies 36 MiB; no training or benchmark outputs
were created.

The initial implementation halted at this prerequisite under the implementation
skill. The owner then authorized its repair; see the candidate evidence below.

## T002 — complete: reviewed boundary and local remediation candidate

Hermes branch `fix/final-tool-policy-boundary`, candidate commit
`1088e06e448bef2af736122a5d424082a57bf548`, lives in the separate
`/Users/javadtaghia/gitlab/hermes-tool-policy-boundary` worktree. The owner runtime
at the base commit is unchanged. Its package metadata is `0.0.0`, so the commit
and five source-file hashes, not that non-distinguishing version, identify the
candidate in `integrations/hermes/patches/final-tool-policy-boundary.json`.

The generic host fix:

- Fails closed on outer pre-tool dispatcher errors in agent and direct-tool paths.
- Adds `authorize_tool_call` after transformations at agent callback and
  registry/connector dispatch, including concrete connector batch entries.
- Checks detached final arguments, refuses mutation/modifying decisions, preserves
  existing vetoes and returns ordinary blocked errors so recovery can retry.
- Handles callback/dispatch errors and timeouts without leaking final-policy
  exception text into result/log output. Calls without a final policy keep their
  native path; legacy transform hooks still fire once.

Canonical Hermes test command is reproduced in the patch README. Result: **467
passed** across seven files, including **40 new boundary cases** with actual
module imports and directory-plugin discovery, on macOS / Python 3.14.7 / pytest
9.1.1. Allowed writes create a temporary effect file; denied/failed writes do not.
The connector transport is a test double; there are no real external writes or
model calls. The source-only historical probes above remain distinct evidence.

Regression proof temporarily restored the two unfixed dispatch files, retained
the new hook registration so the fixture could load, then ran the new cases:
four outer-dispatch-error cases failed, and the 32-case final-policy matrix
failed. Both files were restored byte-for-byte automatically. The recorded
467-pass run uses the fixed versions; source hashes match the candidate commit.

The mail patch applies cleanly to the unmodified base (`git apply --check`) and
reverse-checks cleanly on the candidate. Both checks are read-only. Upstream MIT
license and commit metadata accompany the patch. No live source, launchers,
global Python environment, real memory or benchmark was modified. The isolated
Hermes test environment is 248 MiB and was built by its PM, without model extras.

This completes the T002 version/boundary/OS inventory and prerequisite repair.
At that checkpoint T003–T024 remained unchecked; subsequent foundation and RAG completion is recorded below. Installed rule-service conformance, source revocation,
atomic approval use, Windows/Linux, full outcome/review/export/UI journeys and
efficacy remain required by their later tasks. No rule activation, deployment,
release, upstream acceptance or universal enforcement claim is implied.

The owner-requested review of Mem0, LangMem, Letta and LangChain/LangGraph is
recorded with primary sources and limitations in `memory-system-comparison.md`.


## T003–T005 and T025–T026 — foundation and governed RAG

Implemented bounded versioned contracts/schemas, scoped encrypted append-only
persistence, transactional idempotency, authenticated agent grants/revocation and
binding to the existing engine's one-use review authorization. Persistence reuses
the existing vault: evidence and receipts are bounded inline values in one SQLite
transaction, so no dual-store outbox or canonical-memory schema migration was
needed at this stage. Logical tombstones do not establish cryptographic deletion;
full dependent deletion/recovery remains T017.

The RAG service supports owner-configured adapters and a reference provider using
encrypted stored passages with a transient RAM-only SQLite FTS index. It retains
exact passages/digests/citations, applies requested jurisdiction/effective-date
filters, validates scope and source revision, rechecks authority after retrieval,
and records encrypted requests/results. Provider deadlines and concurrency limits
are explicit. Revocation can prevent completing an audit update: an existing
pending request then remains unknown, never an asserted successful delivery.
Retrieval alone admits no memory and activates no rule. Generic MCP/CLI access
was still pending at that checkpoint; its subsequent completion is recorded below.

Validation on macOS / Python 3.12.13:

- Contract, store and authority suite: 57 passed.
- Contract/store/baseline and existing evidence regression selection: 98 passed,
  3 skipped for unavailable optional post-quantum dependencies.
- Latest real RAG/provider/authority/store suite: **33 passed in 26.76 seconds**:

```sh
.venv/bin/python -m pytest -q tests/test_rag_provider.py tests/test_rag_service.py \
  tests/test_feedback_authority.py tests/test_feedback_store.py
```

Cases include real FTS passages, no persistent plaintext FTS index, independent
adapter results, malformed/foreign results, inert injection text, immutable source
revisions, revocation during retrieval, unavailable/hung providers, scoped
readback, real credentials, concurrent retries and key rotation. Synthetic
fictional documents only; no model calls, paid evaluation or real memory mutation.
These counts overlap and must not be added as unique test cases. Cross-platform,
full lifecycle, real MCP client, installed-host integration and quality gates
remain pending. See `benchmark-impact.md` for possible DolphinBench effects;
existing routing, context selection, action guards and scoring files are unchanged.

## Subsequent implementation checkpoint — actual local service journeys

Worktree `atmem-verified-memory-feedback`, branch `feat/verified-memory-feedback`.
The original `aetnamem` checkout, live Hermes source/launchers, real user memory
and benchmark artifacts are untouched. Package metadata remains 2.3.14; these
development changes are not the published 2.3.14 artifact or a new release.

Completed local tasks now include T006 (actual core exposure receipts and late
immutable outcome revisions), T009 (canonical-source/HMAC-authorized review),
T012–T013 (closed typed compiler and deny-wins evaluator), T018 (shared CLI/MCP
read/report/propose surfaces) and T027 (actual host-neutral stdio clients).

The larger tasks have working components but are not checked complete:

| Task | Implemented and locally exercised | Remaining acceptance |
|---|---|---|
| T007 | Registered independent verifier, retained readbacks, assurance tiers, dispute preservation, proposed failure attribution. State-only observations never prove action completion; positive completion requires a unique correlated effect receipt and all checks on one call. | Evidence-backed verified causal attribution and complete hostile-feedback matrix. |
| T008 | Owner-frozen schedules, exact denominators, missing/unknown/disputed counts, independent assessment reducers, diagnostic episode bootstrap, bounded scoped operational counters/p50/p95 and idempotent owner-reported usage. Missing billing is null; reported billing remains partial/unverified. | Full version/task-class coverage and independent production quality/resource gates. |
| T010 | Frozen protected manifests, retained three-arm diagnostic replay, task-contract checks, three-attempt cap and zero-model/time/disk bounds. | Production qualification and accepted/rejected receipts with independent power, conformance and resource gates. The implemented evaluator always returns inconclusive. |
| T011 | Explicit bounded stored-engine candidate budget/context packing/balanced pools; disabled parity and shadow return native context. | Full profile acceptance and qualified activation journey. |
| T014 | Reviewed lifecycle, fresh source/version/expiry checks, atomic generations, versioned activation receipts and historical rollback revalidation. | Full lifecycle/crash matrix and production qualification. |
| T028 | Real local handler effects, native veto, exact single-use approvals, encrypted admission before dispatch, same-key idempotency, timeout uncertainty and persistent cross-key/restart holds. Owner reconciliation requires independent terminal-effect evidence. | Complete concurrency/schema/adapter conformance matrix. |
| T015–T016 | Existing isolated Hermes boundary candidate remains available; generic MCP has actual client/effect tests. | AtMem's installed Hermes service adapter and installed-host qualification. The read-only final hook cannot be used as a one-use approval consumer. |
| T017 | Owner-previewed dependent-copy purge, source/idempotency revocation anchors, RAG generation fencing, standalone encrypted reconstruction, restore quarantine and rollback checks. | Automatic registered restore/retention integration, full deletion/in-flight/crash matrix. External copies and full-Home rollback remain explicit limitations. |
| T019 | Authenticated HTTP facade; CSRF/origin/identity/scope checks; actual Feedback screen, per-action details, review/shadow/suspend/revoke, accepted-receipt selection and evidence, owner activation and previous-generation rollback controls. | Browser export consent and production-qualified positive HTTP journeys. Diagnostics alone cannot enable activation. |
| T020 | Purpose/recipient/preview-bound owner consent, real ML-KEM/AES-GCM/ML-DSA recipient export, exclusions, consent revision and withdrawal. | Full secret/privacy/split/source-revocation acceptance matrix and product consent flow. |
| T021 | Pinned 12-job OS/Python CI definition, published-wheel upgrade test and local current-wheel packaging/import checks. | Actual Linux/Windows and all Python matrix results; installed-host combinations. |
| T022–T024 | Offline baseline validation, diagnostic receipts and bounded 1,000-rule interpreter/resource reporting; setup/limits documented. | Independent complete quality/power/conformance/retrieval-overhead qualification gates, separately approved bounded efficacy manifest/run, final acceptance report. No paid calls or efficacy run authorized here. |

New protected rows use the existing encrypted vault. An encrypted pending/committed
Home checkpoint detects DB-only rollback/deletion and is required in backups.
The first opt-in mutation sets format 4; a real published 2.3.14 binary refuses
the newer format rather than rotating unknown scoped partitions incorrectly.
Native-only containers retain their old format. Full old-Home/key/anchor rollback
cannot be detected without external monotonic authority and is not claimed.
Evidence grant/revoke now serialize against admission using the existing key
transition lock; authorization is rechecked under that lock before decrypting.

Fresh bounded regression invocation (no model/benchmark calls):

```sh
ATMEM_FEEDBACK_BASELINE_WHEEL=/tmp/atmem-spec050-baseline-2.3.14.whl \
ATMEM_FEEDBACK_BROWSER=1 .venv/bin/python -m pytest -q \
  tests/test_feedback_*.py tests/test_rag_*.py tests/test_governed_mcp.py \
  tests/test_guarded_mcp*.py tests/test_rule_*.py tests/integration/test_feedback_*.py \
  tests/test_context_engine_governance.py tests/test_context_engine_contracts.py \
  tests/test_context_engine_retrieval.py tests/test_task_state_service.py \
  tests/test_task_state_guards.py tests/test_action_guard.py \
  tests/test_evidence_protection.py tests/test_continuity_product.py \
  tests/test_control_evidence.py
```

Result: **413 passed, 5 skipped in 215.38 seconds** on macOS/Python 3.12.13.
Four skips require the separately pinned Hermes source; one is Windows-specific
replace semantics. Existing Chrome was used headlessly; no browser was downloaded.
The browser test verified displayed counts and exact arguments, not merely that
a window opened. Real recipient encryption ran with pqcrypto 1.0.0. The isolated
venv is about 176 MiB including test/browser-driver dependencies, with no model
weights or training outputs.

`uv build --wheel` succeeded. A separate temporary target install of that wheel
verified packaged new modules/schemas and the CLI from outside the checkout.
The pinned actual public upgrade wheel SHA-256 is
`37597be588817aa2dad921a683b39b6e6417eb5bdf3ec23256655acf13b19a03`;
`scripts/fetch_feedback_baseline.py` verifies it explicitly. The local development
wheel has the unchanged version string and must not be confused with or uploaded
over that published artifact.

`scripts/check_feedback_docs.py`, `node --check atmem/control/assets/app.js` and
`git diff --check` pass at this checkpoint. Test counts overlap previous runs;
do not add them as unique tests. Source-controlled test fixtures seed accepted
authority only to exercise lifecycle consumers, labelled TEST_FIXTURE_NOT_EFFICACY.
The production qualifier cannot emit acceptance from those synthetic fixtures.
No source release, main merge, website change or deployment is implied.

## Review/CI follow-up

Draft source PR: https://github.com/aetna000/atmem/pull/37 . The initial source
checkpoint is `00a2dae`; it is not approved for merge or release.

- Added authenticated `guarded_tools` schema discovery for application-registered
  proxy handlers. Unsupported nested schemas, invalid required fields, ignored
  keywords and mistyped enums are rejected at owner registration, before any
  client can discover or invoke the handler.
- Focused changed-path checks: **18 passed in 71.60 seconds** across guarded
  SDK/client, generic MCP, documentation and the local lifecycle journey. These
  overlap the 413-test checkpoint and must not be added as unique tests.
- Separately ran all four pinned Hermes source-contract probes with explicit
  `HERMES_SOURCE`: **4 passed in 0.44 seconds**. These reproduce the original
  source behavior, including its known counterexamples; they do not certify the
  installed AtMem adapter or silently install the separate host repair.
- The first 12-job contract workflow failed before tests: the install command
  incorrectly applied `--no-deps` to pytest as well as AtMem, leaving `pluggy`
  absent. Corrected it to install AtMem without optional companion dependencies
  and then resolve the bounded test requirements normally. That failed attempt
  is retained at run 42606699830; fresh cross-platform results remain required.

## Operational reporting and cross-platform corrections

Added process-local metrics with closed operation/reason buckets, exact scope
selection, 64-scope bound and the last 256 latency samples per operation. Errors
cannot turn exception strings into labels; invalid/denied reads cannot obtain
another scope's counters. Metrics do not change decisions and reset on restart.
Owner usage recording is receipt/run-bound and idempotent. Scheduled-run quality
reports and the dashboard distinguish not captured from partial host-reported
usage; neither is verified complete billing or spending approval.

`scripts/evaluate_verified_memory_feedback.py` is an offline bounded diagnostic:
it measures the pure evaluator with 1,000 synthetic applicable rules and creates
one new report file, not a qualification. It rejects invalid/fabricated manifests,
relaxed gates, non-finite measurements and exhausted budgets. Missing native
baseline outcomes, power, conformance and retrieval overhead remain explicit
insufficient evidence. The baseline now rejects task/action/check identifiers
that cannot be represented by the actual namespaced outcome ledger.

Changed-path results: observability/metrics/dashboard/RAG/dispatch/verification
selection **39 passed, 1 skipped in 268.06 seconds** (browser opt-in unset for
that invocation); baseline/qualification/report gates **44 passed in 13.83
seconds**; recovery/docs **5 passed in 22.03 seconds**. These overlap other
counts. One actual 20-sample diagnostic completed in 3.15 seconds, with interpreter
p50 1.73 ms and p95 2.67 ms, zero model calls/tokens/USD. Its decision was
inconclusive. This is one synthetic allowed-call timing on this Mac, excludes
compilation/auth/storage/remote time from interpreter latency, and is not a
general latency or quality qualification.

On corrected CI source `713c886`, all four Linux versions and multiple macOS
versions passed. Windows exposed two real acceptance-fixture problems: Git CRLF
conversion changed the exact frozen corpus hash, and `copytree` into a public
backup root did not preserve private checkpoint DACLs. Added an LF Git attribute
for the frozen JSON corpus and owner-private backup-root creation **before**
copying keys/checkpoints. Checkpoint permission/integrity validation remains
unchanged and fail-closed. These corrections still require fresh Windows CI;
the failed attempt remains visible, rather than relabelling it as a pass.

## Operation status, owner controls and CI follow-through

Effect-bound receipts now explicitly record succeeded, failed, not-dispatched or
unknown backend operation status. Correct pre-existing destination state cannot
turn a rejected/pending call into a successful action. Reconciliation concerns
terminal operation certainty, not task correctness: a conclusive completed-but-
wrong write can clear its hold for an explicit correction while its task remains
failed. Reconciled receipts state `task_success: not_implied`. Unknown legacy
statuses are not backfilled as successes.

The dashboard owner controls submit exact accepted qualification IDs and current
generation checks. Qualification evidence is displayed before confirmation;
scope/version object key order does not affect equality. Rollback reuses the real
lifecycle service. Real Chrome journeys verified keyboard/count/detail display,
accepted test-fixture receipt selection, cancellation leaving shadow unchanged,
and revoked credentials returning a typed HTTP 403 without activation. The owner
facade additionally exercised actual canonical review, missing-qualification
denial, test-seeded activation, suspension, rollback and deleted-source denial.
Test-seeded authority remains explicitly NOT_EFFICACY; production qualification
has not occurred. HTTP callers still require an application-owned per-request
memory factory for thread-bound SQLite actions.

Provider usage can now retain unknown fields individually, preserving known
subtotals without presenting missing subscription/provider billing as zero. The
dashboard labels unknown costs explicitly. Fresh scoped usage/CLI/metric checks:
**8 passed in 29.01 seconds**. Operation-status/dispatch/export/metric checks:
**28 passed in 151.99 seconds**. A preceding contracts/readback/dispatch/export/
recovery selection passed **69 tests**; counts overlap. HTTP/control/lifecycle
and both real Chrome journeys: **12 passed in 61.72 seconds**. Actual MCP/CLI/docs
changed-path selection: **7 passed in 30.29 seconds**. Combined regression is
being rerun on this source; these focused results are not represented as a
completed cross-platform acceptance run.

At source `aa6d28b`, **11/12** feature OS/Python jobs passed, including Windows
3.10/3.12/3.13. Windows 3.11 timed out before its provider-start event in the
revocation test. Its coordination window now uses the supported 30-second bound
and surfaces an early worker/admission exception directly; the distinct short
provider-timeout test and production default remain unchanged. The main Python
CI selection reported **4,236 passed, 189 skipped and one failure**, solely the
dashboard's endpoint inventory missing the three implemented feedback routes.
Added those exact routes; the inventory assertion passed locally.

The unrelated latest OpenClaw declaration gate resolved 2026.11.2, for which no
reviewed fixture exists. It is left failing pending explicit source review; no
compatibility predicate is weakened. A bounded local tarball probe exceeded its
100 MB cap and its 99.6 MB partial download was immediately removed. The CI job
already downloads that same published package, so a failure-only diagnostic now
retains its declaration shape and tarball SHA-512 as a one-day review artifact.
The job remains failed and native authorization unchanged. This avoids another
large Mac install or automatically approving an unreviewed upstream host.

## Subsequent hardening and export acceptance (2026-11-10)

The combined regression at `08ed1d2` completed: **440 passed, 5 skipped in
438.77 seconds**. Four source-only Hermes probes were not selected by environment
and one platform-specific test requires Windows. The separate explicit original
Hermes source probes passed four tests; these reproduce the documented original
limitations, not installed repaired-host conformance. Feature CI run
`42613494068` passed all **12/12 OS/Python combinations** at that commit. These
results predate the hardening below and do not certify it. Other installed-code,
continuity, framework, replay and website-doc workflows at that commit succeeded.

New checks bind a canonical Memory home to a trusted configured tenant, authorize
even disabled feedback-profile requests, and filter exact source IDs by agent,
workspace, status, exclusion and remote sensitivity **before loading content**.
Only explicit local egress permits sensitive source review. Model proposal
responses contain minimal candidate receipts rather than protected source
snapshots or human review prose, including legacy cached responses. Evaluation
attempts reserve their persistent three-attempt budget before computation; a
crash or timeout cannot reset it, and source cleanup retains the budget counter.
Future-issued qualification receipts cannot activate or restore a rule.

The latest OpenClaw declaration-only fixture was recovered from failed CI job
`129149777447`, with its complete packed-tarball SHA-512 matching registry
integrity. Its hook shapes match 2026.11.1; the added fixture does not expand the
native tested-version allowlist or claim runtime identity support. The main CI
Windows provider stop failure motivated a bounded read-only CIM retry and exact
worker-instance identity check. Uncertain process exit now preserves its PID
record; no unknown process is killed. The provider/OpenClaw focused selection
passed **11 tests in 1.26 seconds** locally; actual Windows CI remains required.

Real export HTTP and Chrome journeys passed **2 tests in 52.50 seconds**. They
used independently read-back synthetic writes in a real encrypted store, scoped
admin identity, actual recipient/signing key pairs, explicit consent, exact
preview, human-review checkbox, cancelled confirmation, encrypted download and
successful recipient decryption. HTTP tests also reject absent CSRF, browser
signing-secret injection, withdrawn consent and revoked credentials before key
access. Logout clears plaintext previews and recipient fields. RAG-linked
examples now recheck scope/source generation/revision/active state on preview,
export and cached retry. The complete new suite is still being verified; no
production data, host installation, training, paid inference or DolphinBench
run was performed.

## Service bridge, Home restore and final regression checkpoint

At source `7fd7cfa`, the expanded combined selection completed **463 passed,
5 skipped in 544.55 seconds**, including the real Chrome journeys. Both feature
CI (`42621953286`, **12/12 OS/Python combinations**) and main CI (`42621953053`,
including native unit, provider, OpenClaw and distribution checks) completed
successfully. The supporting workflows also passed. These results apply to that
source; subsequent changes below require their own CI, not a reused green badge.

The pinned Hermes service bridge reuses the shared guarded dispatcher, with
trusted session/call binding and scoped registration. It composes with the
existing routing plugin through an optional keyword argument, preserving its
default hooks. The repeatable final check cannot consume an approval. Real host
execution middleware performs the single admission and dispatch. Native vetoes,
late argument rewrites, revoked grants, unavailable policy, deleted sources,
missing host identity, unknown batches and skipped middleware cause no covered
effect. Repeated calls inspect the latest retained receipt without reexecution.

In the candidate's actual Python 3.14.7 environment, **11 tests passed in 57.86
seconds**, using real host imports/registry/agent middleware, real encrypted
AtMem state, the existing action-guard hooks and synthetic effect files. This is
local candidate conformance, not production efficacy, other-OS Hermes support,
the global task-state enforcement capability or an owner-runtime installation.
The initial real retry check exposed the retained-intent/latest-result mismatch;
the bridge now inspects that receipt and never retries its effect. The failed
initial attempt is not counted as a passing test.

The supported Home restore/adoption path now invalidates feedback authority
through a machine binding, with fail-closed checks after restart. Owner-only
CLI reconciliation works without a surviving agent grant and disables restored
grants, approvals, consents and registrations before fresh qualification.
Direct canonical database restoration and arbitrary copied files remain outside
automatic detection. A Home/key/binding rollback is not advertised as prevented.

A complete changed-path selection with all three actual Chrome journeys,
threaded HTTP activation/rollback using per-request real canonical connections,
Home restore/adoption/reconciliation, profiles, lifecycle, CLI and concurrent
MCP clients passed **41 tests in 195.55 seconds**. A further privacy matrix passed
**9 export tests in 82.76 seconds**, including real held-out manifest exclusion,
detected secrets, conflicting independent readback and unverified outcomes.
The two-process MCP race holds the first callback open and proves a same-actor
retry returns the same intent without a second effect; latest receipt inspection
then reports completion. Active profile consumers now exercise native bounded
fallback on an actual injected engine outage, never on a governance violation.
Activation failure after writing the lifecycle row rolls back its receipt and
state together; retry creates one generation. Test counts overlap prior checks.

All 39 FR/SC identifiers map to the 29 Spec Kit tasks; none are unmapped. Task
checkboxes are reconciled with demonstrated implementation, leaving causal
attribution, production qualification, broader conformance/recovery and efficacy
acceptance explicitly open. No user memory, published package, website deployment
or frozen benchmark was changed.

The wheel at `99ba8bb` built and imported outside the checkout, including all 17
feedback schemas, operation-status fields and export assets. Its development
SHA-256 is `4d59dd46eb46e5121bad4d5ed5413b51b7b5c42522fcde48e5f527a69e85c7c7`;
it is not a replacement upload for published 2.3.14. The further authority,
contracts, review, diagnostic qualification and metrics selection passed
**73 tests in 79.95 seconds**.

Fresh CI at `99ba8bb` found the new profile test incorrectly treating scoped
receipt enumeration as chronological. Random receipt IDs do not define insertion
order. The actual bounded fallback assertions passed; the historical-row lookup
failed on Linux 3.11/3.13. The test now requires exactly one fallback record out
of the three expected comparisons and checks its identity, cause and payload,
without relying on enumeration order. The failure is retained here and fresh
CI is required. A separate exploratory Evidence Collector permission assumption
was rejected after reading the existing role table; no role/permission change
was committed.

A final transport review found that the governed server capped incoming frames
but not assembled quality responses (especially their structured/text copies).
It now streams a bounded tool-result size check and rejects oversized replies
with `result_budget_exhausted`, preserving all evidence and SDK/CLI/API counts.
RPC IDs have bounded exact integers or valid UTF-8 of at most 256 bytes; malformed
surrogates fail as invalid requests. Real encrypted-store quality data exercises
the limit, proving the reply contains no omitted private payload and the original
outcome remains exact. The prior MCP/CLI/concurrent-client selection passed
**9 tests in 54.67 seconds**; the final malformed-ID/escaping changes need their
fresh verification. Native/default MCP and frozen DolphinBench paths are unchanged.

At source `61b64d5`, both the feature matrix (`42629118768`, **12/12**) and main
CI (`42629118586`, **48 jobs**) completed successfully. The rebuilt development
wheel also exercised actual encrypted RAG creation and subprocess MCP
search/inspection/revocation from outside the checkout. Its SHA-256 is
`30e62180542a47278fc62a0270c7f01cf0472b25ce58c5dcc84171f81b1f2d16`.

Subsequent deletion review found that the previous generic ID walk could mistake
business IDs in raw tool results for AtMem references and follow copied payload
identities backward. Source cleanup now uses typed protocol namespaces and
defining-record ownership, ignoring opaque tool arguments/results/readback bodies.
Real-store tests preserve unrelated outcomes whose IDs collide with a document
source or are quoted in a dependent result, and preserve an active canonical rule
whose source ID equals a distinct RAG source ID. Purging active/qualified policy
dependencies now requires explicit revocation first, so deleting its source
cannot silently remove enforcement. Unlinked raw-text copies remain governed by
their own evidence retention; complete semantic forgetting is not claimed.
The recovery/export/dispatcher/journey selection passed **30 tests in 211.43
seconds** during this hardening, and the three new cases passed **3 tests in
26.06 seconds**; counts overlap. Final source verification and CI remain required.

The final recovery/journey selection on the unchanged cleanup source passed
**10 tests in 56.92 seconds**, including all three new lineage/revocation cases.

Final source `3c9d612` passed the 12-job feature matrix (`42632894547`),
but main CI `42632894560` found a genuine failure in the Windows installed
SQLCipher artifact gate: the candidate passed pre-cutover validation and then
raised an HMAC/integrity error after rename in the finalization recovery test.
The migration code was unchanged from main; the trigger is not established.
Local real-SQLCipher baseline tests passed (19 passed, 1 Windows-only skip),
which does not dismiss the Windows failure.

Migration hardening now requires a successful checkpoint and SQLite-managed
transition to DELETE journaling before moving either single-file database.
Busy readers stop migration before cutover. Post-rename verification exceptions,
including SQLCipher HMAC errors, restore the verified plaintext source and retain
the rejected encrypted candidate under `migration-prepared`; runtime remains
fail-closed until explicit migration retry. This also applies to an interrupted
cutover. The regression damages an actual authenticated encrypted page after
export/pre-cutover verification, verifies preserved source integrity, denied
runtime access, and successful explicit retry. A real WAL reader regression
checks both committed rows survive refused migration. An initial regression-test
helper incorrectly attempted plaintext inspection during rollback too; its
predicate was corrected to inspect only the initial plaintext-to-backup rename.
Fresh native, installed-artifact and cross-platform results are required.

SQLite documents WAL files as persistent database state and warns against
separating them from their database: https://sqlite.org/wal.html#the_wal_file .
Checkpoint busy results are documented at https://sqlite.org/pragma.html#pragma_wal_checkpoint .
SQLCipher's authenticated integrity checks and export API are documented at
https://www.zetetic.net/sqlcipher/sqlcipher-api/ . These establish the migration
invariants; they do not prove the original Windows failure's root cause.
The migration/durability/upgrade/storage/feedback-recovery/profile selection passed
**37 tests, 1 Windows-only skip in 60.47 seconds**, with actual SQLCipher 0.6.2
installed. JUnit: `/tmp/atmem-spec050-encryption-fix-20261110.xml`.

Owner-provided Windows host was tested directly via SSH using an isolated
`%TEMP%/atmem-spec050-ef3ffec` venv and synthetic stores; no existing installation
or user memories were changed. Windows 11 build 26200 / Python 3.12.6 / SQLite
3.45.3 / SQLCipher module SQLite 3.51.1 loaded the built wheel from venv
`Lib/site-packages`. Wheel SHA-256:
`9e3e1a17135eb2412d5d5662f9f49114796b2d198753b04e045ee9c276096a61`.
Dependency consistency and installed encryption smoke passed. The first installed
test pass found two test defects: deriving the checkout from the copied test's
parent accidentally excluded a valid venv under TEMP, and the new corruption
regression's SQLite context manager left a connection open for explicit retry.
The gate now receives the actual source root from its runner and verifies the
exact imported module against installed distribution metadata as well as the
site-packages boundary. The test closes its integrity connection explicitly.
After these corrections **all 22 Windows installed encryption tests passed with
no skips in 9.92 seconds**. macOS encryption selection: 21 passed, 1 Windows-only
skip. The Windows broader feature/native suite is still running.

Browser journeys now choose an existing OS-native Chrome (or an explicitly
configured Chromium executable), instead of a macOS-only path. Explicit opt-in
with missing dependencies/browser fails, rather than silently skipping. No browser
is downloaded. All **3 actual Chrome journeys passed on macOS in 59.49 seconds**;
Windows Chrome 156.0.8078.80 was discovered for the pending Windows browser tests.

The owner's broader Windows run exposed a product defect absent on CI runners:
feedback checkpoint temporary paths exceeded classic MAX_PATH. CI runners'
long-path configuration had hidden it. The failed broad run was stopped, preserving
its log; it is not counted as validation. Checkpoints now retain their full
cryptographic identifiers and existing layout while using the Win32 extended
Unicode path prefix (including UNC form) and a short random temporary basename.
No machine-wide registry or permission settings change. A real-store long-Home
regression checks persistence across reopening, protected ACL/mode, encrypted
anchor contents, cleaned temporary files and tamper refusal. Fresh Windows
installed-wheel and broad tests are required. The broad test launcher also now
overrides pytest's source `pythonpath` so it genuinely imports the installed
wheel, preserving only the fixture/test helper path.

The next owner-Windows installed smoke reproduced the intermittent HMAC failure;
standalone journaling alone was insufficient. A deterministic native probe found
the cause: opening an existing binary file with `os.O_RDWR` under Windows CRT
text defaults removed a trailing 0x1A byte (14 bytes became 13 without writing).
`O_RDWR | O_BINARY` preserved all 14 bytes. The old migration flush helper used
exactly the unsafe open mode after successful candidate verification. Encrypted
ciphertext may end with that value, explaining last-page HMAC failures.
The flush helper now explicitly selects binary mode for candidate, target and
rollback-source fsync. Its byte-preservation regression includes every byte value,
CR/LF and a final 0x1A, without depending on chance ciphertext generation.
Native encryption/checkpoint/durability tests passed **29, with 1 Windows-only
skip, in 9.49 seconds**. The earlier WAL hardening and exception rollback remain
valid safeguards but are not presented as the root-cause fix. Direct Windows and
fresh installed-artifact CI are required after this change.
Microsoft documents the binary/text distinction and CRT default at
https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/open-wopen?view=msvc-170
and https://learn.microsoft.com/en-us/cpp/c-runtime-library/text-and-binary-mode-file-i-o?view=msvc-170 .
The owner-host probe establishes the actual truncation behavior on Python 3.12.6.

### Direct Windows final-code result — `a2fb7ce`

With the binary flush fix, installed encryption smoke and **all 23 encryption
regressions passed without skips in 10.85 seconds**. The checkpoint/action
preflight passed **8 tests in 13.19 seconds**, including the long-Home case, on
Windows with `LongPathsEnabled=0`. Every one of the installed wheel's **424 AtMem
files** matched the package bytes. Final development wheel SHA-256:
`18927602eb239973425124605ae04461de16c709543f99698efb9b61ec8072dd`.

The broader installed selection completed in 779.70 seconds: **410 passed,
1 POSIX-only permission-path skip, 1 packaging harness failure**. That packaging
check expects `pyproject.toml` in its working directory. Rerunning it from the
source directory using isolated Python and only the test-helper import path
passed **1 test in 0.38 seconds**; no product/test code change was needed.
The original failed JUnit is preserved rather than relabelled as a clean run.
No Windows functionality test was skipped. All **3 real Windows Chrome journeys**
passed in the broad run (14.827 / 17.393 / 27.881 seconds); their quality and export
screenshots were visually inspected. The synthetic export was actually downloaded
and decrypted, and logout cleared its preview. Counts overlap.

The separate bounded Windows 1,000-rule interpreter diagnostic measured p50
0.9289 ms / p95 **1.6311 ms** across 20 samples, with 1.66695 seconds elapsed,
zero model calls/tokens/USD. It correctly issued no qualification and remained
inconclusive. This excludes compilation/storage/auth/remote verification and
cannot establish retrieval latency, efficacy or production resource gates.

Local evidence bundle: `/tmp/atmem-spec050-windows-evidence-a2fb7ce/`, including
original/rerun JUnit, timing JSON, reviewed screenshots and a plain-language
README. Owner Windows test root remains isolated under TEMP; credentials/stores
are synthetic, with no real memory migration or live installation change.

At product source `a2fb7ce`, the feature workflow `42641161702` passed 11 matrix
jobs but Windows/Python 3.12 reached the job's 15-minute deadline (annotation:
"The job has exceeded the maximum execution time of 15m0s"), without a recorded
assertion failure. This is not a 12/12 result. Windows matrix jobs now have a
bounded 30-minute CI deadline; Linux/macOS retain 15 minutes. No suite, product
qualification threshold or runtime timeout was relaxed. Fresh workflow results
are required. The main workflow `42641161789` has 47 successful jobs and one
queued installed-wheel job at this checkpoint, including a successful Windows
installed-encryption gate. Final statuses are recorded on PR #37.

Main CI `42641161789` subsequently completed successfully: **all 48 jobs passed
on product source `a2fb7ce`**, including all Linux/macOS/Windows installed wheels,
Windows SQLCipher, supported Python versions, upgrades and companion/bridge gates.
A separate isolated macOS/Python **3.13.14** wheel environment also passed all four
installed product/delegation/transport/retrieval smoke scripts plus dependency
consistency; its temporary venv was removed after retaining the log.
The subsequent commit changes only this evidence/task checkpoint and the Windows
feature-job deadline, with no changes to the 424 packaged AtMem files. Final
feature-workflow status remains explicitly tracked on PR #37, not inferred from
these product regression results. Eight feature acceptance/implementation tasks
remain unchecked; no efficacy or complete-feature claim is made.

### T007 — bounded operational classification (subsequent development)

Added a separate owner-registered, versioned independent classification readback
path to `VerificationService`. It rejects writer/proposer self-verification,
model-judgement checks, partial or unbound material, absent delivery receipts,
uncorrelated/unverified effects, stale/revoked source revisions and changed
checker registration. Proofs retain actual observed/expected material under
scope/outcome/invocation binding, not just a label or hash. `AttributionVerification`
is the eighteenth shipped closed feedback schema. Its causal/activation flags
are always false and cannot be elevated through wire data. Complete trusted
checker contracts define bounded operational conditions; they do not establish
an agent's internal motivation or universal source absence.

Real-store tests compare a frozen complete authorised fictional document corpus
with independent operation-start capture, actual core context/exposure bytes,
exact arguments and an actual destination file/backend journal. Complete absence
is distinguished from partial capture or an existing source fact; delivered but
unapplied is distinguished from an empty delivered package. Host omission does
not override an independent operation journal. Original disagreements persist;
scoped owner resolution is CAS/receipt-set-bound, remains human attestation,
and states whether the selected proof supports or disproves the proposed label.

Typed defining lineage removes source-dependent proposals/proofs/caches without
walking back into unrelated outcome history. Model-facing MCP/CLI/quality reports
return scoped summaries and exact per-action checks; raw proof bodies remain in
the encrypted vault. No model tool can register/check/resolve a classification.
The existing dashboard renders these fields on the corresponding read/write
entry. Missing checker/capture remains unknown, and classification never replaces
the independently verified task-success denominator or qualifies a policy.

Validation selections overlap: **96 passed in 309.62s** across attribution,
contracts, readback, recovery, metrics, CLI/MCP and transport during development;
final closed-wire plus classification selection **62 passed in 146.54s**;
false causal/activation-wire elevation checks **2 passed in 0.35s**; actual new
classification Chrome journey **1 passed in 23.45s**. Earlier narrower selections
were 22/9/28/31/59 passes and are not additive or final-source platform evidence.
Fresh installed-wheel, actual Windows and cross-platform tests are required.

## Qualification input binding follow-up (2026-11-10)

T010 remains open. The reducer now pins real verifier registration generations
before replay and checks exact principal/version, still-active generation,
completed readback attempt and original retained input/trial provenance. A host
success from a different reader, input, arm, configuration, memory snapshot,
environment or version cannot count as the frozen comparison. Contrary retained
independent readbacks remain disputed. Exact encrypted trial rows retain the
outcome digest and receipt set, with aggregate invalidation lineage; diagnostic
receipt/trial payloads share the declared serialization budget. No production
power, resource qualification or accepted activation is claimed.

Local Python 3.12 validation: 16 qualification tests passed (147.64s), and 51
recovery, baseline and report-gate regressions passed (49.81s). One initial new
fixture used a nonexistent session principal property; it was corrected to use
authenticated identity, then the qualification suite passed. These are real
isolated encrypted-store tests with synthetic backend effects, not efficacy runs.
The Windows run underway tests committed b4aab99; it does not test these later
uncommitted qualification changes.

Additional final checks: dispute retention and atomic budget failure passed
(2 tests, 29.61s); a stronger receipt-fits/trial-payload-exceeds budget case
passed separately (1 test, 21.42s). Counts overlap and must not be summed as
unique scenarios. Inventory/docs and 67-page website source checks passed using
the worktree virtual environment. These checks do not cover a production run.

## Direct canonical restore admission and SQLCipher snapshots (2026-11-10)

T017 remains open for the full in-flight/source-deletion matrix and final OS
acceptance. The supported canonical restore API now records private content-free
pending/completed witnesses. Feedback checks the canonical witness as well as
Home adoption at admission, including across service/database restart. A pending
restore cannot be reconciled; a completed restore requires scoped owner
reconciliation and fresh grants/requalification. Repeating an identical snapshot
creates a new event rather than reusing old permission. Arbitrary filesystem
copies and whole-Home rollback remain explicit limits.

Found and fixed an existing SQLCipher API mismatch: canonical backup/restore used
plain sqlite3 connections even for a SQLCipher database. They now use the active
household's configured driver/key. The actual encrypted roundtrip test plants a
synthetic marker, checks ciphertext/header and plain-sqlite rejection, forgets the
fact and restores it, then verifies native recall without a plaintext downgrade.
Only temporary household keys/accounts were used; no real memory was changed.

Local Python 3.12: native storage roundtrip/conformance passed (3 tests, 0.74s).
Five direct-restore/revocation/interruption cases passed (23.68s). Final combined
recovery, SQLite lifecycle/conformance and encryption selection passed 40 tests,
with one Windows-only permission-semantics case skipped on macOS (80.62s).
The final selection includes a direct restore with both plaintext and SQLCipher
canonical storage plus encrypted feedback. Initial new fixture errors used a
list as a dict and a record ID as a substring-forget selector; both were fixed
before the final pass. This is synthetic recovery evidence, not a benchmark.

## Beta publication requested (2026-11-10)

The owner explicitly requested a PyPI beta, retained as beta. Release candidate
version: AtMem 2.3.15b1 and OpenClaw bridge 2.3.15-beta.1 (npm beta channel).
AtBot 0.1.1 and AtFlows 0.1.8 remain unchanged; no companion tag is required.
Both target package versions were absent from their public registries when
checked. The release note and README retain all incomplete production gates;
this does not check off T010/T016/T017/T021/T022/T023/T024 or promote stability.
No tag/publication is implied by these source changes. Website refresh is a
separate owner-reviewed PR and cannot be self-merged or treated as deployed.

Local beta source checks: 30 AtBot/release metadata cases passed; OpenClaw
typecheck, build, complete node test sequence and all three Python bridge
smoke/journey scripts passed. The unchanged dependency tree was reused read-only
from the original checkout through an ignored worktree symlink, after confirming
the lock differed only in root package versions; no global install was changed.

## Beta release-gate corrections (2026-11-10)

The first beta CI checkpoint 16f71b0 was not tagged. Full Python 3.10/3.13
runs each reached 4,314 passing cases with 203 skips, but failed three release
 documentation checks: README quick starts still pinned the stable line, the
badge did not carry the required version label, and capabilities.json still
reported 2.3.14/stable. Corrected the source README to explicit beta examples
(with a separately labelled stable alternative) and the capability manifest to
2.3.15b1/prerelease, retaining incomplete feature status. The unchanged checks
then passed locally: 25 documentation/release/inventory cases (0.47s).

The Code installed gate on macOS/Python 3.13.17 failed one short `Ruff` byte scan
in an encrypted database after the encrypted export/import round trip succeeded
(job 129300182993, run 42657598151; 330 passed, 28 skipped, one failure). The raw
runner database was not retained, so the exact matching bytes cannot now be
re-examined. Four-byte scans of ciphertext/base64 are collision-prone and do not
prove plaintext leakage. Strengthened this test to retain/scan a complete planted
private value, assert exact authorized round-trip content and independently
require ordinary SQLite to reject both encrypted databases. No encryption runtime,
threshold or admission check was relaxed. The original failed CI result remains.

The strengthened actual CLI/HTTP cases passed locally (2 tests, 2.89s) and on the
owner's Windows machine (2 tests, 11.34s). Full macOS/Python 3.13.14 installed Code
gate then passed 331 cases with 28 explicit optional/host-probe skips (359 total),
using the beta wheel, isolated synthetic Home and actual SQLCipher/PQ crypto.
The first attempted local gate used a broken uv Python 3.13.12 ensurepip runtime;
the existing Homebrew 3.13.14 runtime completed successfully without a download.
This is installed product compatibility evidence, not an efficacy benchmark.
