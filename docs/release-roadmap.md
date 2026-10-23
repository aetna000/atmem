# AtMem release roadmap

## Current stable: 2.3.10

AtMem 2.3.10 promotes bounded evidence discovery to a stable, opt-in SDK/host
integration, retaining shared coding memory, source-backed structure,
inspectable experience and portable project bundles. Its matching OpenClaw
bridge is 2.3.10; AtBot is pinned to stable 0.1.1 and AtFlows to stable 0.1.4.
Use the [release note](releases/v2.3.10.md) and [Code guide](atmem-code.md).
Host support is bounded by installed-version qualification, not a promise that
every coding CLI exposes equivalent hooks or full-fidelity capture.

## Stable promotion from tested 2.3.10b1

The [stable release note](releases/v2.3.10.md) and
[promotion qualification](releases/v2.3.10-qualification.md) track this release.
It packages explicit SDK/host evidence discovery with scoped read-only tools,
bounded leases and source quotations, optional semantic nominations and
source-state interpretation, and lifecycle-safe encrypted derived caches.
Ordinary deterministic memory, Code and integration defaults are retained.
Windows privacy and transport qualification is a release requirement, not a
reason to bypass permission checks. No Laya training/model is included.

| Stage | Required outcome |
| --- | --- |
| Review and correct | Aligned specification, capability matrix, versions, dependencies and user instructions |
| Qualify artifacts | macOS/Windows regression and installed/upgrade gates; Linux/CI matrix; AtBot/OpenClaw/security and browser checks |
| Prepare website | Current stable instructions; separate owner-reviewed source-pin handoff |
| Publish stable | Verify existing stable AtBot 0.1.1/AtFlows 0.1.4, publish AtMem and bridge 2.3.10 |
| Freeze and evaluate | Exact artifacts, dependencies, models, configuration and complete attempt/accounting records for the separately approved 600-task campaign |
| Promote | Version-only mapping to 2.3.10 plus installed/upgrade/equivalence checks; behavioral/dependency/configuration changes require affected reevaluation |

Source preparation, package publication, owner website merge and live deployment
are separate states under [release coordination](release-coordination.md).
The completed [600-task run](https://huggingface.co/datasets/atmem/atmem-2.3.10b1-dolphinbench)
passed 390/600 (65.0%) on the original 2.3.10b1 artifact. Its
[submission PR](https://github.com/mem0ai/dolphinbench/pull/10) retains the tested
version and is self-tested, not independently verified. Stable promotion does
not rename that evidence or establish superiority over Mem0. Research acceptance remains under
[Spec 046](../specs/046-retrieval-performance-2310/spec.md).

## Separate and deferred work

Checked-experience learning remains a separate evaluation-first roadmap. It is
not delivered by 2.3.10. Laya training/model work is also excluded. Broader memory-health,
shared-space, enterprise deployment, new host profiles and registry publication
need their own confirmed scope and gates; no version is promised here.

[Historical planning](release-roadmap-history-20261021.md) is retained without
rewriting prior release evidence. Historical experiments and their version pins
are not current install commands or independently reproduced quality claims.
