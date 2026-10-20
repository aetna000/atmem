# Code context curation v1

Request operations: discover, fetch, changes, capabilities. The existing operator
binds subject/project/profile/agent/root; model arguments cannot choose them.
Closed arguments: query (0–4000 UTF-8 bytes), kind (code|experience|both), ids
(1–8 references), goal (0–1000 bytes), limit (1–8), budget (256–8192 bytes),
session and epoch (bounded opaque identifiers), known (up to 64 ID/version
references), references (boolean). Each operation permits only relevant fields.

Responses use `atmem-code-curation-v1`, status, items, coverage, estimator and
exact serialized byte count bounded by budget. Index items carry kind, ID,
bounded title, location or observed outcome/revision, version digest, estimated
detail tokens and `fetch_ref`. No-match is an empty list, not fabricated context.
Experience applicability in an index is `unchecked`; detail fetch rechecks it.
Source fetch preserves exact original lines, line numbers, hash and omitted
ranges. Goal is a selector, not a new fact or command. Failure returns a bounded
explicit withheld/missing response. Raw execution output is not a fetch tier.

`changes` checks known references and fetches current changed evidence; unchanged
references require actual delivery in the same session/epoch and explicit opt-in.
There is no client-selected acknowledgement level. A restart forgets ephemeral
delivery state. Stream revalidation precedes final retention and delivery.
Code authority/source checks and secret screening precede display of metadata.

Native CLI history rewriting and pretrained learned pruning capabilities are
false. The pure masking helper operates on a copy supplied by a prompt owner,
replaces only eligible old tool outputs with retrievable references and leaves
original full output retained by that owner under its authorized evidence policy.

Encrypted project bundles add v3 when curation settings or evidence are present; the
reader preserves unchanged v1/v2 field sets and validates v3 scope/record links.
No SQL schema migration. Older readers cannot import v3 and must upgrade; old
bundles and canonical data remain supported. Session delivery state never travels.

## Future efficacy protocol

Engineering comparison: native, legacy automatic content, curated discovery.
Separate code-only from experience-enabled arms, then add ledger/masking/pruner
individually. Freeze build/model/task IDs/budgets/order before dispatch. Existing
five tasks are inspected engineering only. Confirmation uses untouched tasks;
chronological experience contains only earlier authentic observed attempts and
includes unrelated/stale entries. Never seed future fixes or hidden tests.

Measure all attempts, official task grades, complete input/output usage, cache
categories, actual charge or labeled estimates, p50/p95 agent and total latency,
indexing separately, auxiliary service cost, fetch/refetch/duplicate bytes and
failures. Preserve original prompts and outputs under existing encrypted evidence
rules. Publish paired differences and task-clustered uncertainty; predeclare a
quality margin and adequate sample size. A zero-model qualification proves
contracts, not task quality or token savings. No model evaluation is run here.

## SpecKit consistency review

The extension contains six functional requirements and five success criteria,
covered by eight tasks. No unmapped extension task, blocking ambiguity,
duplication or constitutional conflict remains. Broader pre-existing feature
qualification work is not marked complete by these tasks.

| Requirement | Tasks |
| --- | --- |
| FR-029 and SC-014 | T126, T129, T131, T132 |
| FR-030 and SC-015 | T126, T127, T129, T131 |
| FR-031 and SC-016 | T128, T129, T131 |
| FR-032 | T129, T131, T132 |
| FR-033 and SC-017 | T130, T131, T132 |
| FR-034 and SC-018 | T125, T129, T131, T132 |

## Implementation verification 2026-10-19

Branch: `feature/atmem-code-2.3.9`. T125–T132 are complete within the extension
scope. No release version, owner installation or published registry changed.
All earlier coding benchmark outcomes remain unchanged.

| Gate | Result and boundary |
| --- | --- |
| Broad Code and knowledge regression set | 1099 passed, 1 skipped, 1 deselected, 2 expected failures in 554.20 seconds; installed host files were explicitly excluded from that invocation |
| Final installed curation suite | 40 passed in 103.70 seconds, importing the isolated wheel rather than the source package; includes the final projection-integrity and exact wire-retention checks |
| Claude, Codex, Copilot and owned-process cleanup set | 8 passed in 68.62 seconds; local fixture endpoints, no paid model inference |
| Controlled Claude/Codex/Grok/Muse session set | 6 passed in 53.27 seconds; fixture qualification preserves existing activation limitations |
| Installed Claude index-only behavior | Actual CLI and local endpoint observe an unchecked experience index, without full command output; included in the 40-case suite, not an additional independent result |
| Build | Wheel and sdist built; all 350 wheel package files match current source, 294 Python files parse with Python 3.10 grammar |
| Other gates | Dashboard JavaScript syntax, diff whitespace, task ID inventory and pinned licensed source-import reproduction pass |

The suites overlap and their counts must not be summed as independent tests.
The skipped/expected-failure host probes do not become qualified automatically;
in particular the separate Muse echo/Meta-protocol limitations remain.

Private acceptance artifact:
`/private/tmp/atmem-code-curation-acceptance-20261019/atmem-2.3.8-py3-none-any.whl`.
SHA-256: `0b94af55cf202c4624f47859c122af8dc51491af7b172c0344912aa001d93533`.
Its 2.3.8 metadata is private development metadata, not a new published 2.3.8
distribution or a release-qualified 2.3.9. Installed target:
`/private/tmp/atmem-curation-acceptance-installed-20261019`.

Initial broad checks exposed legacy tests assuming content injection after fresh
setup. They now select content mode explicitly, retaining their original recall
assertions; new tests separately assert fresh index mode. A subsequent run
exposed a Codex test-home cleanup race with a surviving background plugin
checkout. The test runner now uses a new owned POSIX process group and stops
its descendants before temporary-home cleanup. An isolated descendant regression
and the affected installed-host set pass. No owner process is targeted and no
production host activation rule is relaxed. Earlier failed/interrupted test
attempts are not presented as successful runs.

The pure masking helper and deterministic goal selector are implemented.
Native CLI prompt-history rewriting, pretrained SWE-Pruner integration, Windows
qualification for this extension, browser usability qualification and a new
paired coding-efficiency study are not claimed. No training data, new model,
GPU, Vast.ai instance or paid inference was used. The future efficacy protocol
above is the next gate before claiming token or latency improvements.
