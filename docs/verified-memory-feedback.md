# Verified memory feedback — implementation status

Spec: `specs/050-verified-memory-feedback/spec.md`.
This feature is a development preview in the `2.3.15b1` beta candidate,
not a production-qualified memory or enforcement feature. Importing `atmem.feedback` enables nothing. Existing recall, stores,
adapters and native authority remain the defaults. The opt-in evidence format
upgrade and new explicit authority boundaries are documented below.

## Current development surfaces

Host-neutral local stdio MCP and CLI, scoped document retrieval, retained context
and per-action outcomes, independent readback, exact metric denominators,
source-grounded review, bounded profiles and typed rules are implemented. The
local dashboard supports authenticated inspection, review, shadow, qualification
selection, rollback and recipient-encrypted export controls. Owner SDKs provide
registered-copy deletion and restore quarantine. These are development paths,
not complete production qualification or a stable promotion.

See [governed RAG and MCP](governed-rag-and-mcp.md) for executable setup, exact
tools, privacy, format-4 downgrade restrictions and remaining limitations. Readback
of correct state alone never certifies an action; operation-bound evidence is
required. Registered independent checkers now support bounded operational failure
classifications with retained original proofs, exact source/effect linkage and
append-only disputes/human resolution. A diagnosis proposal or trace alone cannot
certify a source absence or a retrieval failure. No internal mental causality or
policy qualification is claimed by these classifications. The offline qualifier
always returns inconclusive. No production
activation, learning or DolphinBench improvement is established by synthetic
tests. The live Hermes installation is unchanged. The new opt-in Hermes service
bridge has been tested against the separate pinned candidate; it is not installed
on the owner's runtime or production-qualified.

## Implemented foundation

The offline baseline preflight validates immutable baseline identities, a fixed
memory snapshot, explicit action/check requirements, episode/paraphrase separation,
chronology, finite resources and unchanged acceptance thresholds. A manifest cannot
grant itself authority, assert measured success or enable a paid call. The six
contract scenarios are synthetic metadata, not task results or efficacy evidence.
See `docs/benchmarks/verified-memory-feedback.md` for definitions and limits.

## Initial host boundary and tested remediation

Reviewed Hermes source commit:
`d0288be5b3330d2442e3907185b8e9d0958297bb`.
The host package metadata declares `hermes-agent` version `0.0.0`; that version
alone does not identify a supported runtime, so the source commit is required.
No installed-host conformance or activation capability is certified.

The two source-contract blockers below are now fixed in the separate candidate
commit `1088e06e448bef2af736122a5d424082a57bf548`, based on that reviewed source.
The owner installation remains unchanged. The reproducible patch and manifest
are in `integrations/hermes/patches/`; that directory's README records the exact
test coverage and limits. This resolves the design prerequisite for T002; full
installed-host/rule-service qualification remains T016 and is not complete.

| Boundary | Source contract result | Consequence |
|---|---|---|
| Normal `pre_tool_call` block | `_dispatch_authorized_once` does not invoke the synthetic callback | A normal hook veto exists. |
| Hook dispatch raises | `_pre_tool_block` catches `Exception` and returns `(None, ref.args)`; synthetic callback executes | FR-015 fail-closed outage requirement is not met by a hook alone. |
| Hook checks original arguments, another hook returns `modify` | `_get_pre_tool_call_directive_details` collects modifications after hook observations; dispatcher invokes callback with rewritten arguments | FR-014 exact approval/argument binding is not met by a hook alone. |
| Existing block plus another approval request | Block wins | Existing deny-wins behavior must be preserved. |

These probes execute the pinned function bodies with explicit dependency doubles
and a local effect recorder. They do not import the host runtime, invoke an LLM,
make external writes or prove a complete host installation. Both unsafe paths
are positive counterexamples to treating the hook as a sufficient rule boundary.
The original source-probe tests passing means those counterexamples reproduced,
not that conformance passed. The patched candidate separately passed 467
regressions, including 40 real-import/plugin-discovery cases at the host's
instrumented direct, agent, connector and batch boundaries.

| Platform | Pure preflight | Installed Hermes enforcing boundary |
|---|---|---|
| macOS / Python 3.10–3.13 (AtMem CI), 3.14.7 (Hermes candidate) | AtMem feature matrix passed at `7fd7cfa` | Eleven real AtMem/Hermes candidate dispatch cases passed locally; production qualification pending |
| Linux / Python 3.10–3.13 | AtMem feature matrix passed at `7fd7cfa` | Hermes not qualified |
| Windows / Python 3.10–3.13 | AtMem feature matrix passed at `7fd7cfa` | Hermes not qualified |

No claims are made about other Hermes versions or tools outside this boundary.
The earlier absent-interpreter diagnosis was incorrect: the launcher is a shell
script that uses a present managed Python 3.14 runtime. It was not executed,
repaired or overwritten. Do not invoke Hermes with a temporary `HERMES_HOME` merely to run
these probes: bootstrap can rewrite the owner's global launchers.

## Remediation contract and remaining qualification

The actual tool invocation must revalidate the final canonical arguments and
current policy/source generations after all transformations. Policy loading or
dispatch failure must deny covered writes, including failure outside AtMem's own
callback. Admission must bind and consume approval exactly once at that boundary,
preserve existing vetoes, and expose honest scoped/versioned capability.

A host change must demonstrate those properties. The candidate adds read-only
`authorize_tool_call` checks after final transformations and fails closed on
dispatch/callback failures without ending the conversation. It preserves prior
vetoes, detaches mutable inputs and blocks modifying final decisions. The final
hook is not an approval issuer or atomic nonce consumer; the shared guarded
dispatcher now owns atomic nonce consumption and retained dispatch intent.
`atmem.adapters.hermes.feedback_guard.HermesFeedbackGuard` composes this with
the existing action-guard plugin through the explicit optional
`register(ctx, feedback_guard=binding)` argument. The ordinary staged plugin
passes no binding and retains its previous behavior. Neither swallowing an exception inside
AtMem, registering the hook last, adding a prompt instruction, nor checking a
source hash alone closes both paths. Rerun the hostile matrix and installed-host
journey with the reviewed artifact before any rule activation. Do not patch the
owner's Hermes installation or advertise a capability to bypass this gate.

## Reproduce the current checks

From this worktree with test dependencies installed:

```sh
python -m pytest -q tests/test_feedback_baseline.py
HERMES_SOURCE=/path/to/reviewed/hermes-agent python -m pytest -q \
  tests/test_feedback_hermes_boundary_prerequisites.py
```

Without `HERMES_SOURCE` the source probes skip explicitly. A different commit or
modified pinned boundary fails the probe prerequisite. These checks use no user
memory and no paid calls. Their results are contract evidence only.

## Opt-in Hermes service bridge

The application constructs a `HermesFeedbackGuard` with the same scoped
`GuardedDispatcher` used by generic MCP, the exact pinned candidate source root
and a trusted `session_resolver`. That resolver must bind the host's session,
task, turn and call identities to a scoped application credential; it must not
return a global owner credential or accept identity overrides in tool arguments.
Register each covered tool through `binding.register_tool(owner_credential,
scope, tool=..., schema_version=..., schema=..., native_guard=...)`, then compose
it using the existing action-guard plugin registration. There is no automatic
installation, dynamic model-supplied plugin factory or credential capture.

The adapter verifies all five recorded host boundary file digests before
registration and refuses unsupported hosts. All four host identities must be
present. Execution middleware uses the shared encrypted intent/idempotency,
reviewed rules, current sources and approval admission. The final hook is a
repeatable read-only check of the exact admitted arguments. Changed arguments,
native vetoes, skipped middleware, unknown tools/batches and outages cause no
covered effect. Only explicitly owner-declared read-only exceptions bypass the
proxy; never classify a wrapper or write tool as a read exception. A nested
protected execution is refused. Calls through an unrelated/unintegrated runtime
remain outside this guarantee. This does not prevent arbitrary privileged code
from modifying its own host or bypassing the adapter.

Unknown writes retain the dispatcher hold. A repeated call inspects the latest
retained receipt instead of executing it again. An optional trusted
`approval_resolver` may supply an already issued exact approval ID; the adapter
does not automatically approve. `binding.invocation(...)` exposes the deterministic
binding for the application-owned approval workflow. `capabilities(session)`
authenticates afresh and shows only that scope's registered tools, explicitly
distinguishing registration from qualification. The global task-state
enforcement flag is not changed by merely constructing this adapter.

In the candidate's own Python environment, set `PYTHONPATH` to this checkout
and its `tests` directory and run:

```sh
ATMEM_HERMES_CANDIDATE=/path/to/reviewed/candidate python -m pytest -q \
  tests/integration/test_feedback_hermes_installed.py
```

The test imports real host modules and uses real encrypted AtMem state with
synthetic tool effects; it never invokes the Hermes CLI/bootstrap. Test-seeded
accepted receipts exercise consumers only. They are not emitted by the offline
qualifier and do not establish efficacy, supported production deployment or
cross-platform Hermes conformance.

### Frozen comparison readback binding (development)

Register the independent action reader before freezing an evaluation. The freeze
records its exact scoped registry generation and registration digest, not only
its declared version. Changing or revoking that registration invalidates its
eligibility for that frozen comparison; reusing the same version string does not
preserve eligibility. A fresh evaluation needs a fresh frozen manifest identity.

A successful action readback alone is insufficient for an evaluation arm. Trusted
application readback code must inspect its independent backend journal and retain
`evaluation_input` (the original text, hashed against the frozen task input) and
an `evaluation` object with the exact `manifest_sha256`, `task_id`, `arm`,
`input_sha256`, `configuration_sha256`, `memory_sha256`, `versions`, `environment`
and `evidence_contract` values from the frozen manifest. It must correlate those
values with the actual execution, not copy labels supplied by the agent. These
fields are retained inside encrypted evidence; they are not a model-facing API
for uploading qualification scores. Missing or mismatched evidence is unknown.

The comparison retains each exact outcome digest and eligible verification
receipt set as an encrypted `evaluation_trial` row. Contradictory independent
readbacks remain disputed. Trial rows and the report share a serialized-payload
budget; this is explicitly **not** a measurement of total database, encryption,
backup or filesystem consumption. Evaluation budget counters survive cleanup.
Production power, corpus provenance, resource measurement and acceptance gates
remain unfinished; the service continues to issue only inconclusive diagnostic
qualification receipts. These changes do not establish an efficacy result.

### Direct canonical database restore

The supported SQLiteStore `restore_from` API now records an owner-private,
content-free restore witness next to the canonical database (or on the in-memory
store for RAM fixtures). It records `pending` before canonical replacement and
`complete` only after migration finishes. When FeedbackService is attached to
that memory store, a pending restore blocks feedback, including reconciliation.
Retry the restore explicitly from a known-good snapshot. A completed restore
blocks feedback until the owner uses the existing scoped restore-reconciliation
SDK/CLI operation. This disables old grants/consents/approvals and quarantines
active policy; it does not approve reactivation. Native recall remains available.

Canonical SQLCipher backup and restore now use the SQLCipher connection and the
active household's existing key. The backup remains ciphertext; keep the
household key and policy with the supported recovery materials. A database-only
backup is not a complete Home/evidence/account backup, and this API does not
silently import a plaintext snapshot into an encrypted household. Cross-key
conversion and arbitrary filesystem replacement require a separate operator
procedure. Full rollback of the Home, keys, witnesses and feedback evidence has
no external monotonic witness and is not claimed detectable.
