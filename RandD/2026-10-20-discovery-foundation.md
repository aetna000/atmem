# Spec 044 — foundation qualification, not efficacy

Phases 0–2 have an additive discovery-only source preview. The dedicated
`repository_discover` MCP tool emits ranked source locations and digests, not
source bodies or experience. The profile is explicit in CLI/dashboard config
generation and does not activate a host. Existing expanded/compact/curated
profiles and settings remain unchanged. Native source reading is not intercepted.

## Verification

- SpecKit read-only consistency review: 18 FRs, 8 SCs, 33 tasks; no critical/high
  conflicts identified. Review is by the implementing agent, not an independent
  reviewer. See `2026-10-20-discovery-spec-review.md`.
- Discovery + host-inventory fixtures: 42 passed in 7.42s. These are plumbing and
  authority fixtures, not authentic coding quality or token-saving results.
- Navigation, existing curation, portability and knowledge-MCP regression subset:
  124 passed in 33.59s (overlapping cases; counts are not additive).
- Latest combined source regression run, including installed Claude, Codex and
  Copilot loopback boundary tests and existing Codex/Copilot integrations:
  **134 passed in 58.81s**. These are protocol fixtures, not subscription-backed
  coding attempts, agent adoption measurements or benchmark token results.
  Final repeat after documentation/budget confirmation: **134 passed in 58.61s**.
- Python wheel built and loaded in a fresh arm64 Python 3.12.12 environment.
  `-I` import resolved to installed site-packages; tool schema contained only
  `repository_discover`; 15 host/OS cells were unprobed; Torch was absent.
- Verification wheel SHA256:
  `62ffc968b087fbfffaac9ae0c0b51eba9b5bea4f3df6e4476ea0d5804c7cc48a`.
  Metadata remains 2.3.8 for this private source preview, not a new public release
  or the earlier scored benchmark artifact.
- Final rebuild including the automatic-recall warning SHA256:
  `77a67773e33adcfe2c8a60d5a1da29326f0bc2dfe27663fc5f14297d0e272d92`.
  Reinstalled in the isolated verification environment; `-I` again resolved to
  site-packages, advertised only the navigation tool and found no Torch. The
  first rebuild invocation failed because the default interpreter lacked the
  packaging `build` module; `uv build` with the test interpreter succeeded.
- MCP CLI help accepts `expanded`, `compact`, `curated`, `navigation`.
- Dashboard JavaScript syntax, Git diff whitespace and website docs inventory
  checks passed; website inventory stays at 2.3.8, 56 pages. Nothing is deployed.

Discovery requests are closed-schema, scoped before backend work, screened for
secrets and byte bounded. Exactly one Curation backend entry is selected; its
own authority/freshness checks can recompute candidates internally. Duplicate
pending requests do not repeat backend entry. Results use a nested source-anchor
validator. Stale results are withheld at MCP write; unvalidated/tampered delivery
cannot be recorded as written. Navigation correlation and full wire share the
existing encrypted `curation-exposure` document, so its existing deletion/export
boundary covers the added representation. No migration or new authority store.

## Real-host inventory (macOS only)

| Host | Installed version | Discovery routing |
|---|---|---|
| Claude | 2.1.281 | unprobed |
| Codex | 0.163.0 | unprobed |
| Copilot CLI | 1.0.98 | unprobed |
| Meta Muse Code | 1.4.11 (1.4.11-R6667.1) | unprobed |
| Grok | 1.0.13 (5e9a58528b76) | unprobed |

Exact `--version`/`--help` output and command receipts are retained in encrypted
AtMem evidence at
`/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/discovery-044-hosts-20261020-no-update/vault`.
This is static interface inventory, not subscription access, model behavior or
a real navigation-call qualification. Windows/Linux are unprobed, not inferred.

An earlier inventory root `discovery-044-hosts-20261020` is preserved. Muse then
reported no usable version. Inspection showed its launcher can auto-update or
attempt a login before forwarding even help/version requests. That initial run
did not explicitly disable this path and is not used to establish a
non-influencing probe. The subsequent inventory explicitly sets the launcher's
supported `MUSE_NO_AUTO_UPDATE=1`, `MUSE_LOGIN=0`; it returned the version above.
No inference request or rental is claimed from either inventory.

## Current limits and next gate

Three installed macOS hosts passed local protocol fixtures. Each fixture asks
for a valid discovery call, an invalid authority-field call, and ordinary native
read/edit/test operations against an isolated encrypted fixture repository.
The actual local host process carries the discovery response back to a loopback
model endpoint. Native editing and test execution survive; malformed discovery
requests cannot select a different root. Fixture endpoint usage is fabricated
for protocol testing and must never enter an efficacy/token comparison table.

The first Claude fixture failed because the parent test process had already
bound a different file-key default before its fixture home was selected. The
fixture was corrected to create a new key in its own home, matching its fresh
MCP child. No owner key was copied and no product authority check was relaxed.
The corrected fixture passed. This was plumbing repair, not a retried scored
coding attempt. Codex records its exposure only after its client writes and
flushes the actual dynamic-tool RPC response.

Adding the navigation MCP profile does not disable an existing automatic recall
hook. Configuration now exposes that state and warns when it is enabled.
Discovery-only sessions explicitly set `auto_recall=false`; capture remains
unchanged. Benchmark activation must verify this rather than count both paths.

The new profile is an optional tool, not proven replacement of an agent's native
exploration. Claude/Copilot expose tool selection; Codex exposes a documented
experimental app-server dynamic-tool boundary and a stable shell-tool feature.
These are candidates to qualify, not evidence of effective adoption. Muse's
headless interface differs and Grok's MCP configuration is host-specific.

Primary references checked against installed interfaces:

- https://code.claude.com/docs/en/cli-reference
- https://learn.chatgpt.com/docs/app-server
- https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/allowing-tools
- https://code.claude.com/docs/en/headless
- https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/set-session-limit
- https://docs.github.com/en/copilot/concepts/billing-and-usage/individuals/billing

The official Codex app-server dynamic-tool API is experimental and requires
explicit capability opt-in; the installed 0.163.0 JSON schemas were generated
without starting an inference turn. Native search/read semantics must not be
silently replaced with ranked results. Actual model adoption, fallback and total
usage remain to be measured with the frozen three-backend protocol.

Read-only native authentication checks reported Claude's first-party Pro sign-in
and Codex's ChatGPT sign-in. No account email, OAuth file or credential was
retained in this report. These checks do not prove remaining subscription quota
or a zero-overage policy. Claude's documented bare mode does not use subscription
OAuth, so it must not be used as a purported subscription-backed isolation fix.
The older benchmark's credential-extraction helper is not eligible for 044.
Copilot's documented per-session credit limit is soft, not an enforcement of
zero paid overage. A qualified native subscription launch and usage/quota checks
are still required before scored dispatch. No credentials or billing settings
have been changed to bypass these gates.

## Remaining work (not completed by the foundation tests)

- Native subscription launch/isolation, captured real usage and reversible
  activation for the three scoring hosts; supported Muse/Grok integration.
- Matched native/Cognee/AtMem runner, frozen Click trials and real comparisons.
- Official SWE-bench manifest/grader resource pilot and feasibility estimate.
- Campaign-owned rental ledger/watchdog implementing the USD 6 bound before
  provisioning. A written cap alone is not an operational spending guard.
- New campaign evidence recovery/publication and final full or partial report.

Local inventory measured approximately 3.4 GiB free on the system disk, 69 GiB
on MEM, and a local Docker allocation of 2 CPUs/~4 GB RAM. Do not pull large SWE
images onto the system disk without a resource plan. These are resource
observations, not proof that GPU rental accelerates the workload.

No Click/SWE-bench scoring attempts, new API-billed requests or rentals have been
started for 044. USD 6 is authorized for the new rental campaign; spent so far:
USD 0. No efficacy comparison table is claimed at this gate.
