# M0: Agent investigation preview — initial OpenClaw profile

**Status**: Reopened and not release-ready. The 2026-09-13 standalone full-fidelity evidence amendment invalidates the earlier hash/metadata-only release gate.

User outcome: give a fresh AtMem process only a copied encrypted AtMem evidence store after the agent, logs, workspace and providers are gone; direct storage inspection reveals no session content, while authorized AtMem recovery reconstructs the complete multimodal run from the user's exact prompt through memory/context, decisions, model exchange, tool arguments/targets, results/errors and known outcome evidence. OpenClaw is the first supported configuration; the contracts remain host-neutral.

[PR-001–PR-008](product-requirements.md) govern this slice. Core identity, full-fidelity evidence, encryption/privilege, reconstruction and feedback fixtures run without OpenClaw installed; the installed OpenClaw test is separate profile evidence. Require multiple-agent attribution, exact ordered multimodal content, concrete call/result narratives and time provenance. This slice's narrower host coverage must never become an OpenClaw requirement in core contracts or product terminology.

## Scope and prerequisites

- Identity: the non-task subset of 007 Amendment B T088, delivered independently by 007 T110: authenticated scope plus supplied session/run/turn/tool and optional explicit attempt/parent identities. Never invent a job relationship.
- Capture: 020 FR-024–FR-031 and T042–T053. Exact ordered multimodal evidence and original artifacts are durable before producer acknowledgement. Full fidelity is default; metadata-only/off is explicitly non-reconstructable. Local quotas and retention are visible, and capacity failure never silently downgrades capture.
- Findings: 021 FR-012–FR-015 and T025–T028. Reconstruct from AtMem alone and show concrete prompt/call/result evidence, not counts, hashes, generic nouns or advice to consult destroyed logs.
- Interface: 022 FR-019–FR-022 and T026–T029. Runs, Memory, Decisions, Tools and media, and Audit render the complete story and original artifacts.
- Protection: 028 FR-001–FR-017 and SC-001–SC-010. All evidence and semantic metadata is encrypted; only authorized AtMem operations reveal plaintext under Level 1 Viewer, Level 2 Investigator or Level 3 Evidence Collector, and only Level 3 may export plaintext. Spec 028 plan/tasks must exist before implementation begins.
- Preserve scoped access, installed-package compatibility and reversible adapter enable/disable behavior. Access control governs disclosure; it does not justify destroying captured evidence. Enterprise multi-user administration is not claimed.

007 T089–T106 (task focus, task links, broad locator, task UI and multi-host campaign) remain later work, except any demonstrably required shared contract must be split and named before implementation. M0 storage uses the existing control-store migration sequence under 020; it does not require canonical task-link migrations. Partial delivery does not complete the broader original task.

019 provider unification, the broader 022 application shell beyond its evidence-specific destinations, 025 Connections, task activation, embeddings, AtBot and provider SDKs are not prerequisites. Existing memory use is left unchanged; the M0 profile does not inject or migrate context.

## Technical release gates

1. Installed OpenClaw/bridge/AtMem versions and exact capture coverage are recorded. Default full-fidelity capture plus explicit metadata-only/off downgrade tests pass.
2. A multimodal run contains text, fetched page/link, file, image, audio and video plus memory/context, decisions, model exchange and successful/failed/retried tool calls.
3. Producer acknowledgement, crash/restart, backup/restore and export/import preserve every envelope and original artifact byte; hashes verify but never replace content.
4. The destructive disaster gate copies only the AtMem store, stops/removes the agent and deletes its logs, workspace, caches, original memory/provider stores and model stub. A fresh installed AtMem reconstructs the complete expected run with network denied.
5. Before authorized recovery, direct SQLite/object/archive/string/media inspection of the store, indexes, spool, backups and exports recovers zero planted content or semantic metadata. AES-256-GCM, ML-KEM-768 and ML-DSA-65 known-answer, tamper and downgrade gates pass with exact implementation/validation status recorded.
6. Exhaust submitter, Viewer, Investigator, Evidence Collector, key-custodian and unrelated-principal permissions. API, CLI, MCP and dashboard return exact evidence only through authorized AtMem operations; Level 1/2 plaintext export fails, Level 3 export requires confirmation, and every success/denial/export/rotation is audited.
7. Original images, audio, video, files and fetched resources render or download byte-identically; captions/transcripts/thumbnails remain supplemental.
8. The compact Evidence protection row and focused drawer pass desktop/mobile/keyboard tests; encryption cannot be disabled into plaintext storage.
9. Replay-manifest generation is deterministic and effect-free. Any actual re-execution is outside this preview unless separately authorized and recorded as a new linked run.
10. Publish a version-bound coverage report and limitations only after 020 T049–T053, 021 T028, 022 T029 and all future Spec 028 implementation tasks pass on installed artifacts. Human usability follows the separate declared protocol.

These gates authorize a future release candidate only after implementation; ordinary release rules still apply. No task or document here claims a release exists.

## Explicit subsequent slices

M1 adds 019 native/external governance, broader findings and resolution, 022/025 application journeys and the complete cross-domain campaign. M2 publishes the 011 third-party conformance kit and expands tested hosts; kit development may proceed earlier in parallel. M3 adds 023/024 revocation, simulation and fleet capabilities. Each slice has its own advertised scope and acceptance evidence; numeric spec completion is not a release prerequisite.
