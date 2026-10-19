# Spec 044 — Replace repository discovery, preserve the coding agent

## Overview and governing scope

Extend AtMem Code (Spec 042), using the replay/evidence machinery of Spec 043,
so AtMem can serve a repository-navigation request instead of appending source
context before the agent repeats its native exploration. AtMem remains a memory
and evidence service, not a new coding model. Native agents retain source reading,
editing, testing, their supported subscription authentication and model selection.

Implementation is on `feature/atmem-code-2.3.9`; `main`, Laya work, published
versions/tags and native default configurations are not changed. This request
does not authorize a package release. Existing 042/043 requirements remain in
force except where this separately named discovery experiment changes a
benchmark condition. Existing historical evidence is never overwritten.

Requested agent inventory: Claude Code, Codex, GitHub Copilot CLI, Muse Code,
Grok Code. Requested efficacy comparisons: Claude, Codex and Copilot, each with
native, pinned upstream Cognee, and AtMem. Do not infer that support for capture
or MCP in 042 establishes discovery-routing support in 044.

## User scenarios

1. An owner opts into discovery routing for one project/host. A qualified agent
   asks where an implementation lives; AtMem returns bounded source locations
   and structural references. The agent reads original source and edits/tests
   normally. No automatic source pack or experience detail precedes that request.
2. An owner checks a five-agent capability matrix. Each cell distinguishes an
   optional discovery tool from verified routing of a host's discovery boundary.
   An unavailable boundary is shown as blocked, not represented as implemented.
3. An agent searches an exact pattern. The search keeps its native semantics;
   ranked graph candidates are never presented as exhaustive grep results.
4. An index becomes stale or the service fails. The agent receives an explicit
   fallback/withhold result and can inspect current authorized source. It is not
   trapped in a deny/retry loop or silently switched to a paid provider.
5. An investigator compares all attempts, including failed tasks and unused
   treatments, from encrypted AtMem evidence without a live agent or provider.

## Functional requirements

- **FR-001 — Typed intent.** Define a versioned host-neutral discovery request
  with opaque request/turn identity, bound project/scope/revision, natural-language
  navigation query, bounded result count and UTF-8 byte budget. Discovery means
  ranked, non-exhaustive navigation, never source reading, editing, exact search
  or authorization. Reject unknown fields, nonfinite/invalid numbers and malformed
  identifiers before invoking a backend. A model cannot choose root, database,
  scope, provider credentials or arbitrary filesystem paths.
- **FR-002 — Discovery-only response.** A bounded response identifies serving
  backend, ranked locations/identifiers, freshness/coverage, explicit omissions
  and native fallback availability. It contains no source body, generated code,
  instructions from repository text, full experience observation or execution
  output. Any advertised structural relationship must reference authorized source
  evidence; absence of results does not prove absence of implementation.
- **FR-003 — Reuse authority.** Use existing project authorization, source policy,
  scope binding, generation checks and encrypted Code evidence. Recheck authority
  and freshness before delivery. Provider failure never broadens access. A
  discovery response cannot mutate canonical memory. No parallel authority DB.
- **FR-004 — Route, do not prepend.** In a qualified session, one explicit
  navigation request is served by one configured backend. Do not auto-inject a
  code/source pack, invoke multiple competing discovery backends, or require
  discovery when a task already names its implementation. Reads remain original
  source, and experience remains an optional index/details workflow outside this
  discovery-only comparison.
- **FR-005 — Preserve native semantics.** Exact text/regex search, path listing,
  read, edit and test operations are not silently rewritten as ranked discovery.
  Broad shell commands cannot be assumed interceptable or safely classified.
  Supported host controls may explicitly select tools, but must not disable
  ordinary source verification merely to improve token measurements.
- **FR-006 — Five honest adapters.** Inventory installed host/version and the
  actual supported integration boundary for each requested agent. Distinguish
  `unprobed`, `optional_discovery`, `routed_discovery`, `unavailable`. Promotion
  requires captured positive and negative boundary probes; configuration or a
  binary on PATH alone is not a pass. Probe macOS first; Windows/Linux remain
  separate cells, never inferred from macOS or earlier hook qualification.
- **FR-007 — Explicit activation.** Probe new integration surfaces without
  influencing an owner's real session, then require explicit activation. This is
  not a customer shadow mode. Keep machine config changes reversible, project-
  scoped and free of credential copies. Existing setup/disable/capture semantics
  remain unchanged; disabling automatic Code memory still stops automatic capture
  and recall, not explicit authorized lookup.
- **FR-008 — Subscription-first.** Preserve supported subscription sign-in and
  account/provider selection. No copied OAuth files, unofficial token extraction,
  assumed third-party entitlement or automatic API-billing fallback. A custom
  harness is optional only if its actual supported authentication and tool-control
  boundary are qualified. AtMem does not require a new hosted account.
- **FR-009 — Trace replacement.** Retain requested intent, selected backend,
  exact authorized request/response/error, source digests, serving latency,
  fallback, downstream tool calls, source-window reads and repeated overlaps.
  Separate prepared/written/host-observed/model-input-observed assurance. Mark
  unobservable native reads and missing model usage as unknown, never zero.
  Receipt hashes supplement, not replace, full encrypted evidence.
- **FR-010 — Inspectability.** CLI and dashboard use the same authority state.
  Expose mode, host capability/version, backend, activation, evidence coverage,
  fallback and current index state. A capability limitation is visible before
  launch. No wrapper is a prerequisite for existing Code features.
- **FR-011 — Backward compatibility.** Routing is additive and opt-in, with no
  normal-install Torch/CUDA/SWE-Pruner, hosted SDK or new default network egress.
  Preserve Python 3.10–3.13 and existing deterministic 2.3.8 APIs. Persisted changes
  require versioned upgrade/export/import/deletion tests; avoid a schema migration
  when the existing encrypted Code document boundary suffices.
- **FR-012 — Matched comparator.** Use pinned actual Cognee extraction/query
  code, never AtMem's incorporated fork as the competing system. Record extractor,
  license, configuration and coverage. Keep authorized source, model/effort,
  task, budgets, read/edit/test tools, test grading and subscription accounting
  matched within each host. Compare hosts separately, not as interchangeable
  model replicates. Native agents retain their legitimate capabilities.
- **FR-013 — Experiment separation.** Run a controlled discovery-backend study
  with the same request contract/tool inventory and native/Cognee/AtMem backends;
  distinguish it from a stock-native product comparison with differing tools.
  Do not claim the former measures an untouched native CLI. Optional and required
  consultation conditions, or changed tool schemas/prompts, are separate studies.
- **FR-014 — Click screen.** Freeze five authentic historical Click tasks,
  parent commits, issue requirements, source/extraction policies, reference-only
  graders and artifact hashes before dispatch. Existing inspected tasks are
  diagnostic, not held-out confirmation. No target's reference commit, hidden
  test or future history reaches the solver, index or experience. Keep one
  predeclared attempt per cell initially; failures and treatment non-use remain.
- **FR-015 — SWE-bench campaign.** Default full target is the complete pinned
  SWE-bench Verified test split, not the original SWE-bench full dataset or a
  pilot renamed full. Record actual IDs/count/license from the pinned manifest.
  Freeze a small disjoint qualification pilot and held-out confirmation split
  before tuning. Promotion to the remaining full target uses frozen code and
  thresholds. Preserve all splits and report pilot separately; exposed Click
  results cannot support held-out generalization. The requested final matrix is
  three hosts by three discovery backends, with explicit unsupported cells.
- **FR-016 — Honest metrics.** Primary metrics are executable task resolution
  and end-to-end input/output tokens including cache, with paired task deltas.
  Also report cold/warm indexing separately, agent/preparation/grading wall time,
  p50/p95 and sample counts, discovery use, native fallback, repeated reads,
  context/output bytes, failures, cost and usage coverage. Do not infer causality
  from a single win, pool changed protocols, treat skimmer tokens as model tokens,
  or claim savings from compressed outputs without total usage improvement.
- **FR-017 — Bounded spending and compute.** Owner authorized **USD 6 total**
  rental spend on 2026-10-20, including storage/transfer. Use local resources first;
  measure grader requirements before choosing CPU/GPU. Vast.ai is permitted, not
  mandatory GPU inference. Preflight price, balance, storage, transfer reserve,
  deadline and teardown watchdog; scope deletion to campaign-owned instance IDs.
  No paid API fallback. Do not launch the full matrix unless its conservative
  estimate fits remaining funds/quota. If it cannot fit, stop paid dispatch,
  destroy rentals and publish explicitly partial coverage. Budget limits override
  pressure to achieve a favorable score or complete every cell.
- **FR-018 — Publication.** Retain exact encrypted source evidence, preserve
  privacy-redacted readable derivatives with their own digests, exclude owner
  credentials/keys and label reduced capture. Publish code/specs/reports/small
  manifests to the existing GitHub feature branch and large evidence to the
  AtMem Hugging Face organization, with licenses, immutable revisions and verified
  uploads. Publication is not a package release or permission to alter `main`.

## Acceptance and measurable criteria

- **SC-001:** Contract tests reject every malformed/unknown intent before backend
  invocation; navigation results contain zero source-body/experience-output fields.
- **SC-002:** Scope, deletion, stale revision, secret, budget, delivery-race and
  provider-failure fixtures cannot expose unauthorized/stale content or mutate
  memory; original authorized reads remain possible through the native boundary.
- **SC-003:** A five-host, three-OS matrix names tested versions, exact boundary,
  authentication route and evidence coverage; every routed claim has real probes.
- **SC-004:** Install, opt-in, disable, uninstall and upgrade preserve existing
  settings/data and never contact a provider or download a model without authority.
- **SC-005:** A completed Click report has 45 planned cells (5 tasks × 3 hosts ×
  3 backends), or an explicit missing/blocked denominator. No retry substitutes
  for a failed task. Complete declared traces/usage are required for a token claim.
- **SC-006:** SWE-bench completion means every frozen full-target cell is accounted
  for; partial coverage is prominently labeled, with paired outcomes, coverage,
  uncertainty, runtime/index costs and all failed attempts retained. Positive
  efficacy requires equal-or-better aggregate resolution and lower paired total
  input-token usage on held-out tasks, with uncertainty and harm cases; no preset
  percentage is promised and no repeated tuning on confirmation data is allowed.
- **SC-007:** Simulated budget exhaustion/provisioning failure cannot launch an
  over-budget rental; teardown retains local evidence and verifies zero remaining
  campaign rentals. Public expenses distinguish observed credit delta from invoice.
- **SC-008:** Source plus archived AtMem evidence reconstructs attempts after
  fixture agent/workspace removal. Published archives download with matching
  hashes; private keys and actual credentials are absent from public derivatives.

## Non-goals and edge cases

No new Laya model/training, graph truth guarantee, arbitrary shell interception,
native conversation-history rewriting, forced deny/retry behavior, tool suppression
that hides needed code, subscription-limit bypass, unrelated disk cleanup, or
automatic release. Empty query, no match, oversized request, stale generation,
branch/worktree switch, missing host, unsupported hook, runtime death, quota
exhaustion, missing receipts and inaccessible archives are explicit test cases.
