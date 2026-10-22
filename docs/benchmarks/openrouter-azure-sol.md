# Azure-hosted Sol through OpenRouter

This optional research CLI checks the Azure route advertised by OpenRouter.
It does not deploy a model in your Azure subscription and does not change the
official DolphinBench runner or claim leaderboard acceptance.

## Credentials and credit

Set `OPEN_ROUTER`, `OPENROUTER_API_KEY`, or `OPEN_ROUTER_API_KEY` in the process
environment, or pass `--env-file /absolute/path/to/private.env`. The file is
parsed as literal assignments, not executed. Do not commit credentials.

OpenRouter credit is separate from an API key's spending limit. A key with a
$100 limit does not provide $100 credit. Buy credit directly at
<https://openrouter.ai/settings/credits>; do not send payment details to an agent.

## Commands

The script uses the Python standard library; no new SDK, daemon or CLI install
is required. Run from the repository root with Python 3.10 or later:

```sh
python3 scripts/openrouter_azure_sol.py check --env-file /path/to/private.env
python3 scripts/openrouter_azure_sol.py smoke --env-file /path/to/private.env \
  --confirm-paid-call --evidence /path/on/external/disk/unique-smoke.json
```

`check` authenticates and queries model metadata without an inference call.
`smoke` makes at most one inference request, with no automatic retry. Each
attempt requires a new evidence filename; an existing marker may indicate an
uncertain paid call and must not be overwritten or automatically retried.

The request uses model `openai/gpt-5.6-sol`, Azure-only provider routing,
fallback disabled, parameter support required, medium reasoning, JSON object
output and an 8,000 completion-token ceiling. Provider price ceilings are
$5/M prompt and $30/M completion tokens. This bounds completion cost to $0.24
plus the short prompt, before credit-purchase fees; this is not a campaign
budget controller. The response must identify Azure, the expected Sol model,
the expected JSON result, usage and cost to qualify.

Only a harmless fixed diagnostic prompt is sent, never project conversation
history, credentials or benchmark answer keys. Evidence records the request,
response and elapsed time, excluding the authentication header. Protect the
evidence directory and stage it on a suitable filesystem.

## Benchmark boundary

The unmodified official DolphinBench runner requires a direct Azure judge.
OpenRouter is a different transport even when its reported provider is Azure.
Maintainer approval remains necessary before presenting a modified run as an
accepted official submission. Do not set the backend label to Azure merely to
bypass that runner check.

Routing reference: <https://openrouter.ai/docs/guides/routing/provider-selection>.

## Private AtMem campaign

`benchmarks/dolphinbench/` contains the disclosed macOS integration. It reuses
the pinned upstream corpus, chronological runner, simulated app servers,
append-only conversation validator and unchanged grading prompts/rubrics.
It is not the official built-in-memory adapter, and does not relabel OpenRouter
as a direct Azure deployment.

The campaign uses installed Hermes with Luna (medium, 4,096 completion tokens,
20 tool turns) and Azure-hosted Sol for grading (medium, 8,000 completion
tokens). AtMem is installed from a patched 2.3.9 wheel with a product-owned
Hermes memory freeze. Record the exact wheel hash, not merely its version.
The modification is not part of the published 2.3.9 release.

Each interaction starts a fresh isolated Hermes profile. Only the persona's
AtMem store persists between interactions; native session-search history does
not cross those boundaries. All persona histories must finish before testing;
test-time canonical writes are denied by the product, not by a prompt.
The normal AtMem provider handles capture and recall; the harness does not
extract facts, classify memories, choose retrieval candidates or auto-approve
proposals.

The agent can reach only the model gateway, its scoped AtMem endpoint and its
simulated-app socket. It cannot read controller data, grading files, answer
keys or real API credentials. The socket client is the upstream byte-forwarder
with its socket pathname changed for macOS and stderr-only connection diagnostics.
Byte forwarding is unchanged and source provenance is retained.

Every outgoing model request is durably recorded and cost-reserved before
network I/O. Actual returned usage/cost settles the reservation; an uncertain
request remains reserved and cannot silently become free or be replayed.
Native lifecycle identities distinguish conversational calls from auxiliary
calls. Exact gateway messages, not truncated hook text, form the exported
conversation. The gateway buffers streaming responses, so elapsed time includes
that transport overhead; it is not native time-to-first-token.

The first paid plumbing pilot found that Hermes can exit after a bounded wait
while its background title request is still running. Completed main calls are
preserved, not replayed as a repair. The title request retains its conservative
reservation until reconciled. Subsequent configuration uses Hermes's ordinary
`auxiliary.title_generation.model_upgrade_enabled: false`: local derived titles
remain, without an unrelated model title upgrade. The gateway also waits for
outstanding request handlers when closing. Neither change modifies memory
formation or grading semantics.

The user's ceiling is US$250 total, including unsuccessful requests and grading.
The diagnostic and preparation ledgers have US$0.051654 actual-plus-uncertain
exposure. US$0.10 is set aside for those ledgers; the frozen campaign's hard
cap is US$249.90. No other paid infrastructure is used. OpenRouter's key limit
may independently stop requests earlier; automatic credit top-ups do not change
either limit.

Qualification fixtures have zero real provider calls and are never benchmark
scores. Run identities and uncertain in-flight markers prevent silent retries
or configuration changes. Artifacts remain on the external APFS workspace;
allowlisted recovery reports are uploaded to the private AtMem Hugging Face
evidence repository and independently downloaded by exact revision to verify
SHA-256 and size before any staged deletion.

Native dependency import failures also stop qualification. One simulated-app
environment failed macOS signature verification for `pydantic-core==2.50.1`;
its bytes were preserved and it was reinstalled from PyPI without the old cache.
Signature verification, import and all 35 upstream offline tests then passed.
The rig checks that native dependency's qualified SHA-256 before each paid
interaction and refuses requests if the simulated app tool catalog is missing.

A portable-backup-only repair after the first completed ingestion is retained
under `repairs/`, with the previous and replacement controller identities.
It fixes export scope metadata and archives the repair record; it does not
alter product/model configuration, memory decisions or already-saved responses.
Resuming consumes the saved interaction rather than repeating paid model calls.

A longer preparation interaction also exercised Hermes's automatic background
skill-review fork. It has its own agent turn and is not a user conversation;
its interrupted native completion witness therefore failed the strict exporter.
All gateway responses and costs remain preserved. The frozen campaign uses the
supported `auxiliary.background_review.enabled: false` setting, in addition to
disabling model title upgrades. AtMem's ordinary memory provider stays enabled.
That configuration starts from an empty, separate AtMem store; earlier
preparation records are not claimed as part of its results.

The pinned distributed release has **13,539 single-message ingestion
interactions** (Morgan 3,400; Alex 5,011; Riley 5,128), followed by 600 tests.
The earlier construction validator's 11,147 session count refers to the
construction histories, not the distributed single-message replay count.
The distributed manifest and every loaded source hash are validated before
execution; the run identity includes the parsed release digest.
