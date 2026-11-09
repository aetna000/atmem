# Verified memory feedback — implementation status

Spec: `specs/050-verified-memory-feedback/spec.md`.
This feature is under development and is not a released memory or enforcement
feature. Importing `atmem.feedback` enables nothing. Existing recall, stores,
adapters and native authority remain the defaults. The opt-in evidence format
upgrade and new explicit authority boundaries are documented below.

## Current development surfaces

Host-neutral local stdio MCP and CLI, scoped document retrieval, retained context
and per-action outcomes, independent readback, exact metric denominators,
source-grounded review, bounded profiles and typed rules are implemented. The
local dashboard supports authenticated inspection/review/shadow controls. Owner
SDKs provide registered-copy deletion, restore quarantine, validated historical
rollback and recipient-encrypted example export. These are development paths,
not complete production qualification or a published release.

See [governed RAG and MCP](governed-rag-and-mcp.md) for executable setup, exact
tools, privacy, format-4 downgrade restrictions and remaining limitations. Readback
of correct state alone never certifies an action; operation-bound evidence is
required. The offline qualifier always returns inconclusive. No production
activation, learning or DolphinBench improvement is established by synthetic
tests. The live Hermes installation is unchanged and its AtMem service adapter
is still pending.

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
| macOS / Python 3.12 (AtMem), 3.14.7 (Hermes candidate) | Tested locally | Candidate boundary tests pass; full installed rule-service conformance pending |
| Linux / Python 3.10–3.13 | Not yet exercised | Not qualified |
| Windows / Python 3.10–3.13 | Not yet exercised | Not qualified |

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
hook is not an approval issuer or atomic nonce consumer; those remain required
in the forthcoming AtMem service. Neither swallowing an exception inside
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
