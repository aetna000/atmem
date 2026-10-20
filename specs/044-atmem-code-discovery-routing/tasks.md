# Tasks — Spec 044

Tasks are dependency ordered. Checked means implemented/verified, not merely
planned. A blocked host/campaign is recorded with evidence and not promoted to a
pass; independent work may proceed where no failed prerequisite is bypassed.

## Phase 0 — Specification and review

- [x] T001 Write `spec.md` and pin active feature in `.specify/feature.json`. Covers FR-001–FR-018.
- [x] T002 Write `plan.md`, `contracts/discovery-v1.md`, `benchmark-protocol.md` and this `tasks.md`; read constitution and parent 042/043 compatibility. Covers all FR/SC.
- [x] T003 Run SpecKit prerequisites and read-only consistency/coverage review; retain review outcome in `RandD/2026-10-20-discovery-spec-review.md` only outside read-only analyze execution. Covers FR-011–FR-018, SC-001–SC-008. Resolve critical/high findings with explicit authority before implementation.

## Phase 1 — Contract and existing-authority service

- [x] T004 Implement strict navigation request/result projection in `atmem/code/discovery.py`; no source/experience bodies or model-selectable authority fields. Covers FR-001, FR-002, SC-001.
- [x] T005 Add AtMem single-backend preparation, exposure correlation, bounded pending state and fresh delivery revalidation through existing Curation in `atmem/code/discovery.py`. Covers FR-003, FR-004, FR-009, SC-002.
- [x] T006 Add independent five-host/three-OS discovery capability records in `atmem/code/discovery_hosts.py`; default unprobed and evidence-bound promotions. Initial inventory rejects all qualification claims until the real probe service exists in phase 3. Covers FR-006, FR-008, SC-003.
- [x] T007 Add `tests/test_code_discovery.py` and `tests/test_code_discovery_hosts.py` for malformed requests, no-body schemas, byte bounds, single lookup, failures, stale delivery, scope/deletion and unprobed host honesty. Covers FR-001–FR-006, FR-009, SC-001–SC-003.

## Phase 2 — Opt-in product surface

- [x] T008 Add `navigation` MCP profile and dedicated `repository_discover` to `atmem/knowledge/code/mcp.py`, with actual stream-delivery handling. Covers FR-002–FR-005, FR-009, SC-001, SC-002.
- [x] T009 Wire profile/status in `atmem/code/knowledge_setup.py`, `atmem/code/cli.py` and `atmem/code/application.py`, preserving existing settings and no automatic source injection. Existing application forwarding requires no change. Covers FR-004, FR-007, FR-010, SC-004.
- [x] T010 Expose identical inspectable discovery configuration/capability status through `atmem/code/dashboard.py` and `atmem/control/assets/app.js`; keep read-only limitations visible. Existing dashboard authorization forwards the same application result without a second state store. Covers FR-006, FR-010, SC-003, SC-004.
- [x] T011 Add compatibility, encrypted deletion/export/import and installed-artifact tests in `tests/test_code_discovery.py`, `tests/test_code_portable.py` and relevant MCP/CLI/UI tests; update `docs/atmem-code.md`. Covers FR-007, FR-010, FR-011, SC-002, SC-004, SC-008.

## Phase 3 — Real-host boundary qualification

- [x] T012 Research installed versions and official integration/auth contracts; implement `tools/qualify_discovery_hosts.py` with no real-session config mutation; retain inventory/receipts in `RandD/`. Covers FR-005–FR-008, SC-003, SC-004. Five real installed versions retained; official Claude/Codex/Copilot references checked. Native auth status is metadata only, not quota or routing qualification. Muse/Grok supported routing remains T016.
- [ ] T013 Qualify Claude navigation routing and ordinary read/edit/test/fallback using supported native interfaces in `atmem/code/adapters/claude.py` plus `tests/test_code_discovery_hosts.py`. Covers FR-005–FR-009, SC-003.
- [ ] T014 Qualify Codex navigation routing and supported subscription access through documented CLI/app-server boundary in `atmem/code/adapters/codex.py`; add matching probes/tests. Covers FR-005–FR-009, SC-003.
- [ ] T015 Qualify Copilot CLI/SDK boundary without conflating their controls or auth in `atmem/code/adapters/copilot.py`; retain matching probes/tests. Covers FR-005–FR-009, SC-003.
- [ ] T016 Qualify actual Muse and Grok product/version integration surfaces in `atmem/code/adapters/muse.py` and `grok.py`, or retain concrete optional-only/unavailable blockers without guessed flags. Covers FR-005–FR-009, SC-003.
- [ ] T017 Publish exact host/OS matrix and reversible activation guidance in `docs/atmem-code.md`; test disable/uninstall preserve prior host config. Covers FR-006–FR-008, FR-010, FR-011, SC-003, SC-004.

## Phase 4 — Comparable discovery benchmark machinery

- [x] T018 Implement controlled native lexical, actual pinned upstream Cognee and AtMem navigation backends in `benchmarks/code_replay/discovery_study.py`, with common source policy and no experience/pruning. Covers FR-012, FR-013, SC-005, SC-006. Exercised through real Click trials and a Verified qualification pilot; not stock-native CLI or full-product comparison.
- [ ] T019 Implement exact request/result/read-range capture, usage reconciliation, fallback/non-use, repeated-read coverage and paired metrics in `benchmarks/code_replay/discovery_metrics.py`. Covers FR-009, FR-016, SC-005, SC-006, SC-008.
- [ ] T020 Add tests for missing usage, duplicate/omitted attempts, native-vs-controlled separation, source isolation and comparator identity in `tests/test_discovery_study.py`. Covers FR-012–FR-016, SC-005, SC-006.
- [ ] T021 Freeze task/host/backend ordering, artifacts/prompts/caps and standalone encrypted evidence recovery via `tools/freeze_discovery_campaign.py`. Covers FR-009, FR-012–FR-016, SC-005, SC-006, SC-008.

## Phase 5 — Click diagnostic matrix

- [ ] T022 Freeze five actual historical task/grader/source snapshots under 043 controls in `specs/044-atmem-code-discovery-routing/click-manifest.json`; no future/reference history in solvers. Covers FR-014, SC-005.
- [x] T023 Run one predeclared Click task for all qualified scoring host/backend cells and retain failures/non-use/usage in encrypted campaign evidence. Covers FR-012–FR-014, FR-016, SC-005. Six optional cells completed; three Copilot cells blocked by actual account policy. Separate six-cell requested-consultation diagnostic also retained, never pooled.
- [ ] T024 Complete remaining Click cells without score-guided retries; generate exact native/Cognee/AtMem per-host comparison via `tools/report_discovery_campaign.py`. Covers FR-012–FR-014, FR-016, SC-005.

## Phase 6 — SWE-bench freeze and resource gates

- [ ] T025 Freeze official SWE-bench Verified dataset revision/license, actual full-target IDs, exposed-task exclusions and disjoint pilot/confirmation partitions in `specs/044-atmem-code-discovery-routing/swebench-manifest.json`. Covers FR-015, FR-016, SC-006.
- [ ] T026 Qualify official graders/reference controls and source/hidden-test separation; measure local CPU/RAM/disk/container timings and host subscription quota before rental. Covers FR-008, FR-012, FR-015, FR-017, SC-006, SC-007.
- [ ] T027 Implement tested whole-campaign USD 6 resource ledger, transfer/storage reserve, deadline, campaign-owned instance guard and independent teardown watchdog in `benchmarks/code_replay/discovery_campaign.py` and rental tooling. Covers FR-017, SC-007.

## Phase 7 — Subscription-backed SWE-bench execution

- [ ] T028 Calculate conservative complete-matrix estimate from measured resources and freeze final solver/backend code; publish feasible coverage before provisioning in `RandD/`. Covers FR-008, FR-015–FR-017, SC-006, SC-007.
- [ ] T029 Execute frozen qualification/held-out/full-target cells only within host qualification/quota and USD 6 rental authority; record partial outcomes instead of overspending or fabricating completion. Covers FR-012, FR-015–FR-017, SC-006, SC-007.
- [ ] T030 Collect exact evidence, stop all owned rentals/volumes at the declared cap, verify teardown and record observed credit/invoice distinction in campaign receipt. Covers FR-009, FR-017, SC-007, SC-008.

## Phase 8 — Analysis, publication and handoff

- [ ] T031 Report per-host native/Cognee/AtMem quality, total tokens, latency, discovery adoption, fallback/redundant reads, paired uncertainty and missing cells using `tools/report_discovery_campaign.py`. Covers FR-013–FR-018, SC-005–SC-008.
- [ ] T032 Verify encrypted standalone recovery and privacy/licensing; publish large artifacts to AtMem Hugging Face with immutable hashes and private keys excluded. Covers FR-009, FR-018, SC-008.
- [ ] T033 Verify product/install/compatibility/doc gates and push code/specs/small evidence to `feature/atmem-code-2.3.9`; no main/tag/release change. Covers FR-010, FR-011, FR-018, SC-004, SC-008.

## Executed checkpoint — 2026-10-20

See `RandD/2026-10-20-discovery-benchmark-results.md`. Twelve real Click attempts
in two distinct conditions and six real Verified qualification attempts are
complete. This is not completion of the full task matrix or all implementation
phases. Host transport/auth receipts exist for benchmark-only Claude/Codex;
production routed adapters, Muse/Grok routing and complete OS support remain
open. Copilot's actual account policy blocks third-party MCP. T019/T020 have
usage/delivery projections and tests, but no complete source-range accounting.
T025 has a pinned 500-ID candidate manifest, not a completed exposure/license
audit. T026 has passing base/reference grader controls on one qualification
task, not full-target eligibility/quota qualification. T027 rental safeguards
remain unbuilt and no rental was started. T029's full campaign remains gated.
Full-source traces and preparation failures remain retained; an interrupted SWE
setup stream is explicitly incomplete rather than presented as full capture.
