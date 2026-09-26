# Research — Hermes integration

Investigated 2026-09-26. Upstream main is mutable; these are research pins, not
claims of tested package compatibility:

- Hermes: `d0288be5b3330d2442e3907185b8e9d0958297bb`.
- DolphinBench: `81cb6f8405b40a9e76089cef650806a80af06ea2`.

## Source qualification update

The pinned Hermes checkout was inspected and six no-network source-contract
probes executed. See [validation.md](validation.md) and [contracts.md](contracts.md).
The developer guide's description of prefetch as per-API-call is not sufficient:
`agent/turn_context.py::_memory_turn_start_and_prefetch` invokes it once per turn
before the tool loop. Context is persisted in a replayable sidecar. Both
observation and middleware exceptions are swallowed/continued at the inspected
boundaries. In particular `hermes_cli/middleware.py::_run_execution_chain` calls
downstream after a guard callback raises before invoking `next_call`.

Consequently these hooks cannot certify fail-closed per-model-call revalidation.
Fresh recall authorization is a narrower possible profile; it must not be
silently upgraded to the stronger claim. Exact active-profile qualification is
resolved by the user-approved `authorized-at-recall-v1` profile: check fresh recall
before return, without promising retraction of old host context. Per-request
revalidation is deferred. No installed runtime support is claimed yet.

## Sources and consequences

1. [Hermes provider developer contract](https://github.com/NousResearch/hermes-agent/blob/d0288be5b3330d2442e3907185b8e9d0958297bb/website/docs/developer-guide/memory-provider-plugin.md):
   directory plugins and package entry points are supported; only one external
   provider is active. Managed Hermes environments must use supported plugin
   preparation rather than arbitrary pip injection. Prefer a lightweight
   profile-local directory bridge to an independently installed AtMem service.
   Preserve provider selection and native stores for restore.
2. The same contract supplies `initialize`, `prefetch`, `sync_turn`, memory tools,
   session-end and compression hooks. `sync_turn` is non-blocking; asynchronous
   work must preserve context variables using Hermes's context-aware threading.
   Use the supplied profile/workspace identity, not process-global cwd/home.
3. Oversized prefetch can create plaintext spill files. Delivery-time revalidation,
   retained host context and repeated API-call behavior require source inspection
   and executable tests, not assumptions from method names. Disable/avoid spill
   for governed output or refuse the profile if a safe enforced route is absent.
4. Compression checkpoint API v2 can block lossy compaction but receives filtered
   user/assistant prose, not full tool/system evidence. It cannot satisfy complete
   Black Box capture. Any capture extension must be ordinary shipped product code.
5. [DolphinBench driver contract](https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/docs/DRIVER_CONTRACT.md)
   requires identity, agent invocation, durable freeze, checkpoint verification
   and phase costs. Evaluation must block writes, not merely instruct the agent
   not to write. Exact per-response usage and complete interactions are required.
   Non-append-only context rewrites cannot be represented by the current export
   format: qualify the chosen Hermes mode or stop rather than misrecord it.
6. [Run and submit](https://dolphinbench.ai/run/) and
   [leaderboard](https://dolphinbench.ai/leaderboard/): 600 tests across three
   personas; self-submitted/unverified results are distinct from evaluated rows.
   Website archive maximum is 256 MiB, despite a larger local exporter allowance.
   Required grading credentials/model must be checked before spending on ingestion.

## Existing AtMem building blocks inspected

- `atmem/adapters/base.py`: identity and turn lifecycle. `begin()` captures input;
  blindly invoking it during frozen evaluation would violate read-only memory.
  Product read-only capability needs to distinguish memory from evidence writes.
- `atmem/adapters/pydantic_ai.py`: host binding with per-model-boundary hooks; reuse
  contracts, not framework-specific implementation or unverified capabilities.
- `atmem/client.py`: dependency-free loopback client. Its role/subject headers are
  not proof of server-side credential scope; audit authentication before reuse.
- `specs/011-framework-adapter-conformance/conformance-manifest.md`: planned kit,
  not evidence that every conformance runner/schema already exists. Use available
  tests now and do not claim a planned kit has certified the integration.

## Decisions and unresolved qualification work

Prefer a thin Hermes provider bridge with product-owned AtMem service contracts;
keep Hermes dependencies out of AtMem base. Confirm exact supported routes,
server-side scope bindings and hook placement before coding the bridge. Add
missing contracts to the product, not the benchmark. New service routes require
authentication, payload limits, loopback/default egress checks and versioning.

Before implementation sign-off, inspect the pinned host source for final prompt
placement, native-memory coexistence, spills, lifecycle flush and discovery;
record a tested compatibility matrix and supported delivery profile. An upstream
hook gap is a stop/explicit reduced-capability outcome, never permission to claim
OpenClaw parity. Confirm dependency and corpus licenses before live evaluation.

DolphinBench is a published simulated-app benchmark, not real customer traffic.
Its results support this task distribution; they do not alone establish broad
production superiority. Published upstream baselines are contextual unless rerun
with matching versions/settings. Public test failures may guide general bug fixes,
but reruns after inspecting them are disclosed, not called unseen evaluation.
