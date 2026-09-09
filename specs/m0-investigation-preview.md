# M0: Agent investigation preview — initial OpenClaw profile

**Status**: Planned, not released. This is the first independently releasable slice, not completion of Specs 007, 020 or 021.

User outcome: open an existing-dashboard execution, locate an observed tool failure or missing completion, inspect its exact event and understand what evidence is missing. OpenClaw is the first supported configuration; the contracts remain host-neutral.

[PR-001–PR-006](product-requirements.md) govern this slice. Core identity, findings and feedback fixtures run without OpenClaw installed, with generic agent identities; the installed OpenClaw test is separate profile evidence. Require multiple-agent attribution where supplied and clear reason, effect/uncertainty, event time, timezone and actual check age in the existing UI. This slice's narrower host coverage must never become an OpenClaw requirement in core API/model contracts or the product's default terminology.

## Scope and prerequisites

- Identity: the non-task subset of 007 Amendment B T088, delivered independently by 007 T110: authenticated scope plus supplied session/run/turn/tool and optional explicit attempt/parent identities. Never invent a job relationship.
- Capture: 020 FR-001–FR-010 only as applicable to this non-context OpenClaw profile, through 020 T018–T022. Durable events, bounded spool/replay, ordering, observed errors, gaps, scoped projections and retention are mandatory.
- Findings: 021 FR-001/002/004/009 and evidence-preserving reconciliation from FR-006, through 021 T018–T020. Reuse verified-flight evidence and translate through the terminology table. Keep unknown external outcomes explicit.
- Interface: extend existing Activity/Evidence views, under existing shell ownership. Render timestamp, elapsed time, exact event, uncertainty and evidence-linked inspection advice. No new navigation is required.
- Preserve baseline privacy, access, installed-package compatibility and reversible adapter enable/disable behavior. Use the existing local deployment trust boundary; enterprise multi-user administration is not claimed.

007 T089–T106 (task focus, task links, broad locator, task UI and multi-host campaign) remain later work, except any demonstrably required shared contract must be split and named before implementation. M0 storage uses the existing control-store migration sequence under 020; it does not require canonical task-link migrations. Partial delivery does not complete the broader original task.

019 provider unification, external context, 022 navigation, 025 Connections, task activation, embeddings, AtBot and provider SDKs are not prerequisites. Existing memory use is left unchanged; the M0 profile does not inject or migrate context.

## Technical release gates

1. Installed OpenClaw/bridge/AtMem versions are recorded. An explicit opt-in and disable/restore test passes on that configuration.
2. A virtual 40-minute trace and a separately recorded real-host run exercise successful work, tool error, missing completion, recovered retry and capture restart. Supplied parent/retry links are preserved; absent hooks stay unknown.
3. Restart/replay loses zero acknowledged events; duplicate payloads do not create duplicate logical events. Conflicts, capacity loss and missing hooks are visible.
4. Scoped lookup and evidence pivots work in the existing UI; cross-scope requests disclose no inaccessible data. No default transcript, secret or chain-of-thought capture is added.
5. Findings point to exact observed events; a recovered error is not presented as an unresolved failure, and timeout after dispatch is not proof of no side effect. No executable retry or remediation is offered by this slice.
6. Publish a version-bound coverage report and limitations; complete affected regression, migration and installed-artifact gates in 020 T022 and the technical UI gate in 021 T020. Human usability follows the [declared protocol](usability-protocol.md) in independent 021 T024; preview availability does not require that later claim gate.

These gates authorize a future release candidate only after implementation; ordinary release rules still apply. No task or document here claims a release exists.

## Explicit subsequent slices

M1 adds 019 native/external governance, broader findings and resolution, 022/025 application journeys and the complete cross-domain campaign. M2 publishes the 011 third-party conformance kit and expands tested hosts; kit development may proceed earlier in parallel. M3 adds 023/024 revocation, simulation and fleet capabilities. Each slice has its own advertised scope and acceptance evidence; numeric spec completion is not a release prerequisite.
