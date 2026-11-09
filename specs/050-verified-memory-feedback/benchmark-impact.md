# DolphinBench impact register — Spec 050

Owner request, 2026-11-09: flag changes that can affect DolphinBench quality.
These are possible effects, not measured score improvements. This work has not
changed a DolphinBench run or its frozen artifacts.

| Change | State | Possible effect | Handling |
|---|---|---|---|
| Feedback contracts and schemas | Implemented, offline tests | No intended effect while unused; invalid observations rejected when integrated. | Do not reinterpret historical results as verified outcomes. |
| Scoped encrypted evidence reads and key rotation | Implemented, real-store tests | Storage compatibility, availability and latency risk; no intended memory-selection change. | Preserve default reads; test existing evidence paths and multi-scope rotation. |
| Agent capabilities and review binding | Implemented, real-store tests | Once integrated, denied/revoked calls can change completion and refusal rates. | New feedback service only; existing benchmark authority configuration untouched. |
| External RAG and document FTS | Implemented provider/service/stdio/CLI; local client tests | If enabled, changes evidence, ranking, context length and potentially answers/writes. Extra evidence could help or distract. | Opt-in; not connected to DolphinBench. A future condition must freeze corpus, revisions, filters, settings and delivered bytes. |
| RAG deadlines and unavailable-provider handling | Implemented, local tests | If integrated, affects coverage, latency and unknown outcomes. | Document-provider deadlines only; no change or fix to DolphinBench model/judge retries. No automatic provider retry/fallback. |
| Generic MCP tools | Implemented, actual subprocess clients | Names, schemas and descriptions can alter tool selection and token use with identical backing memory. | Qualify actual clients and freeze tool inventory before scored comparison. |
| Independent action verification and per-action reporting | Implemented reporting/readback components; full attribution acceptance pending | Can change classifications/counts without changing agent behavior. | Separate report-only changes from quality changes; retain original checks, exact calls and unknowns. |
| Retrieval profiles, thresholds and context packing | Explicit bounded packing helper implemented; full qualification pending | Directly changes memories delivered; may cause recoveries and regressions. | Disabled parity first; compare one frozen candidate to unchanged baselines with memory held fixed. |
| Typed rules and guarded tool execution | Compiler/evaluator and owned proxy implemented; production activation not qualified | Directly changes allowed writes, approvals and false denials; may affect completion. | Report enforcement separately from recall. No activation from retrieval or synthetic tests alone. |
| Hermes dispatch-boundary repair | Tested isolated candidate; not installed live | With a policy, can block effects previously allowed by hook errors or post-check argument changes. | Exact host commit and policy are part of the condition. Owner runtime unchanged. |
| Review, exports and dashboard | Review/owner-export SDK and dashboard components implemented; complete consent UI pending | No intended score change alone; applied corrections change memory, and tuning with held-out examples contaminates evaluation. | Explicit review/activation and split exclusions; no unchanged-condition claim after tuning. |

## Notification and evidence

Before integrating behavior-affecting changes into a benchmark path, notify the
owner of the component, intended effect, plausible regression and condition
change. This register does not authorize a run.

Identify source commit, installed artifact, model/provider, prompts/tool schemas,
memory snapshot, RAG corpus/settings, context packing, policy, retries, verifier
and scoring version in each future condition. Do not edit pinned files during a
live run. Follow repository DolphinBench readiness prerequisites before preparing
or launching a campaign.

Offline tests demonstrate tested contracts only. They do not establish a
DolphinBench gain, preservation of a previous score or superiority over another
system. No new score is available for Spec 050.

## Additional compatibility and scoring distinctions

- The first explicit feedback mutation upgrades its evidence container to format
  4. Published 2.3.14 refuses the opted-in vault; native-only containers keep
  their old format. Freeze the upgraded storage/runtime identity in any future
  condition; do not downgrade a live campaign's evidence store.
- Evidence grant/revoke now use the existing key-transition lock, serializing
  with new admission checks. This can affect authorization timing/availability,
  but does not change native memory selection.
- A state-only readback no longer counts as a completed action in the new
  reporter. Success requires one independently correlated operation and all
  checks on that exact invocation. This is a scoring-evidence change, not an
  agent-quality improvement and not a retroactive alteration of frozen scores.
- An unknown proxy effect holds further calls to the same tool/scope even when
  a caller invents a new retry key. Reconciliation requires trusted terminal
  backend evidence; this may trade completion/availability for duplicate-write
  prevention. It is confined to the explicit new dispatcher.
- Neither new MCP tools, document sources, feedback profiles nor rules are
  connected to DolphinBench. No full or pilot run was launched for these checks.
- The new feedback profile helper authenticates even in disabled mode and binds
  a configured canonical tenant. Its selected bytes remain native when allowed;
  forged/revoked or cross-tenant sessions now deny. The ordinary native context
  API is unchanged.
- New canonical-source proposals use the existing bounded SQL authorization and
  remote sensitivity policy before loading content, with an optional exact-agent
  predicate. Default native callers do not supply that new predicate, so their
  query behavior is preserved. The new model-facing proposal response now carries
  only a receipt, which changes that opt-in tool's visible output.
- CI exposed a native Windows provider-stop CIM timeout. Process identity reads
  now have one bounded retry, and an unconfirmed exit retains its ownership PID.
  This can affect control-plane shutdown/restart availability on future provider
  campaigns; it changes no recall selection or model/judge retry policy. No live
  provider or frozen run was modified.
- The existing Hermes routing plugin now accepts an optional trusted
  `feedback_guard` binding. Its default one-argument registration and hooks are
  unchanged. Opting into the new pinned bridge adds real policy admission,
  explicit read-only exceptions and denial of unknown tools/batches. This
  materially changes tool behavior if enabled and must be a separately frozen
  future benchmark condition; it is not installed in the frozen Dolphin runtime.
- The feedback-profile helper now falls back to native deterministic retrieval
  for an engine availability error, within the candidate's configured byte
  ceiling. It records the fallback explicitly. Governance violations and stale
  sources still deny; disabled mode and ordinary native retrieval are unchanged.
- Supported Home restore/adoption changes a machine binding. Opt-in feedback
  operations refuse copied authority until explicit owner reconciliation and
  requalification; native recall and historical evidence inspection are
  unchanged. Direct database/file-copy recovery remains an operator procedure.
- Opt-in registered-copy cleanup now follows typed protocol lineage and refuses
  to purge active/qualified policy dependencies before explicit revocation. This
  changes only the new owner SDK's cleanup behavior and preserves unrelated data
  and existing guards; it changes no native recall or frozen benchmark scoring.

### Native encryption migration hardening (2026-11-10)

A Windows installed-wheel integrity failure exposed an existing migration
recovery gap. Explicit plaintext-to-SQLCipher migration now refuses a busy WAL
checkpoint and requires standalone DELETE journaling before renaming; post-rename
verification exceptions restore the source but keep runtime fail-closed pending
explicit retry. This changes the maintenance/migration failure path, not ordinary
retrieval, scoring or memory contents. No user store was migrated and no frozen
Dolphin runtime/result was edited. Root cause of the Windows HMAC failure remains
unproven until platform verification; a passing local test is insufficient.

Direct Windows testing found classic MAX_PATH could prevent creation of opt-in
feedback anchors. Extended Unicode checkpoint paths and shorter temporary names
preserve existing anchor identity/layout and access controls without a global OS
setting. Ordinary native retrieval and frozen benchmark inputs remain unchanged.

The Windows migration root cause was subsequently reproduced: a binary database
ending in 0x1A can be truncated by the old text-mode `O_RDWR` fsync open. Explicit
`O_BINARY` now preserves all bytes. This affects explicit encryption migration /
recovery maintenance and does not change retrieval/scoring. Earlier standalone
journaling changes alone did not fix the intermittent failure; see evidence log.

### T007 operational classification

The opt-in governed MCP `feedback_outcome` and `feedback_quality`, corresponding
CLI reads and dashboard action details now include scoped classification
summaries when independently checked diagnoses exist. This is additive report
metadata and leaves task-success/coverage denominators and native/default memory
retrieval unchanged. An agent consuming those enriched tools can receive new
inputs: a future scored campaign enabling this surface must declare a new
condition and satisfy fresh qualification; do not silently reuse prior receipts.
No frozen Dolphin package, runtime, data, scoring script or result was modified.

## Frozen qualification readback binding

The opt-in qualification reducer now pins the actual independent reader registry
generation and requires independently retained original input and exact trial
provenance. Previously matching action success without that provenance is now
unknown. New encrypted trial rows retain exact outcome/receipt identities and
participate in dependent cleanup. This changes only diagnostic qualification;
no DolphinBench launcher, recall defaults, scorer, published result or frozen
campaign is changed. Any future use for qualification needs a fresh manifest;
these checks do not establish production acceptance or benchmark improvement.
