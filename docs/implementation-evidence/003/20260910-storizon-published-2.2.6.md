# Spec 003: attributed Storizon acceptance against published 2.2.6

Report received 2026-09-10. This entry preserves results supplied by the
Storizon operator. The AtMem maintainer did not rerun the private Storizon
harness or inspect its fixture state during this documentation update.

## Verified public release identity

- AtMem package: `atmem==2.2.6`, present on PyPI.
- OpenClaw bridge: `openclaw-memory-atmem@2.2.6`, present on npm.
- Release commit: `04a063ce1e7bd2c95bf7d0c04bf9098f5f30c08e`.
- The local `v2.2.6` tag resolves to that commit.

## Operator-reported environment and results

The operator ran actual Storizon through authenticated HTTP, real AtMem MCP and
actual OpenClaw 2026.9.2 (`3928bad`) and 2026.9.3 (`1391f7c`) using Claude CLI
2.1.251, Haiku 4.5, Node 26.5.0 and Linux. All 16 scenario assertions passed,
eight per host.

| Scenario | Reported result on each host |
| --- | --- |
| Default owner gate with missing ownership | Refused before Storizon access |
| Legacy `requireOwner: false` without mapping | Refused before Storizon access |
| Wrong mapped session generation | Refused before Storizon access |
| Inject | Matching Storizon v2 receipt ID/hash, exact context digest, one shown delivery, complete verified flight |
| Withhold | Matching Storizon v2 receipt ID/hash, zero deliveries, complete verified flight |
| Read and exec | 2 requests / 2 observed completions; `completed_successfully` |
| Read intentionally missing file | 1 request / 1 observed error completion; `completed_with_tool_errors` |
| Deliberately suppressed result observations | 2 requests / 0 completions; `incomplete_evidence` |

The refusal cases reportedly made zero Storizon callbacks and left provider
state unchanged. Authorized cases used a complete scoped `localOperator`
mapping, private state directory, exact host session identifiers and an
unrouted local CLI process. In the suppression scenario, real tools and host
terminal events remained active while the observer wrapper deliberately
withheld those observations from AtMem.

The operator also reported 30 Storizon tests / 61 subtests, 131 focused AtMem
tests and bridge prepack checks passing. Their existing Storizon HMAC
implementation needed no change; they updated their harness, CI pin and
migration guide. Published bridge modules reportedly matched the tagged build.

## Claim boundary

This attributed report closes the previously recorded Storizon-specific v2
receipt and local toolful lifecycle gaps for these exact versions and this
isolated configuration. It does not establish live shared-channel identity,
other host/backend compatibility, semantic correctness, or an independent
external task outcome. Public package availability and release identity were
checked separately; private harness artifacts, commands and CI logs were not
supplied, so the partner test execution remains operator-reported.
