# Stable 2.3.15 — verified publication and remaining handoff

The stable package is published. Public PR39 merged branch
`fix/matched-atmem-comparison` at main commit
`bca4e925fc89a3c01b6c95fba4460f59749ce8f5`; annotated `v2.3.15` remains on that
reviewed commit. This post-tag record does not move the tag or relabel a study.

[Stable release](https://github.com/aetna000/atmem/releases/tag/v2.3.15) is neither
draft nor prerelease. [Publisher 44292000170](https://github.com/aetna000/atmem/actions/runs/44292000170)
succeeded, including all four full Python suites, companion/framework/provider/
OpenClaw checks, built/installed artifacts and 19 persisted-version upgrades.
Premerge qualification had 80 successful checks; 30 cancelled duplicate push checks
were superseded. One macOS Python 3.13 job failed to acquire a runner before any test ran;
retrying only that job passed. No test, authority or audit gate was waived.

[PyPI 2.3.15](https://pypi.org/project/atmem/2.3.15/) wheel and source distribution
were downloaded and their registry SHA-256 digests verified. Wheel:
`c0f34a38046fca0c01295500c6f5c50a1c87778ca223f7a1889618fe7b812d83`.
Its complete `atmem/` runtime files match the three-platform tested candidate
byte-for-byte; packaging/archive identity remains distinct.
[OpenClaw npm 2.3.15](https://www.npmjs.com/package/openclaw-memory-atmem/v/2.3.15)
is registry `latest`; the fetched tarball integrity and internal package version
were verified. Initial cached full-registry metadata lagged publication; npm
prefer-online and no-cache checks confirmed the current tag. AtBot 0.1.1 and
AtFlows 0.1.8 remain unchanged; no new companion tag was needed.

```sh
python -m pip install --upgrade atmem==2.3.15
python -m pip check
atmem --version
```

Use `"atmem[code]==2.3.15"` for the optional SQLCipher/recipient-crypto paths. Follow
the stable release note for native Linux build prerequisites, explicit grants,
format 4 opt-in/backup/rollback and compatibility.

## Installed-user evidence

| Environment | Candidate journey | Fresh public-PyPI journey |
|---|---|---|
| Native Windows 11 Pro x64 / Python 3.12 |all six groups passed|not started: supplied SSH host became unreachable|
| Native macOS ARM64 / Python 3.12 |all six groups passed|all six groups passed, 26.82s|
| Unprivileged Debian 12 ARM64 Docker / Python 3.12 |all six groups passed|all six groups passed, 27.37s|

Candidate receipts remain windows-user.json/macos-user.json/linux-user.json.
New registry receipts are macos-pypi-user.json/linux-pypi-user.json. The publisher
also passed its exact published-artifact Windows installation/managed-Bun gate.
Do not infer an owner-host Windows registry pass from that separate gate.

Journeys exercised actual installed CLI/dependencies, fresh isolated Homes,
loopback dashboard/AtFlows HTTP, encrypted cross-process memory/integrity,
owner-scoped encrypted document search/inspection, wrong-scope denial and the
zero-model SDK contract. AtBot selected its expected unconfigured deterministic
fallback. These are operational checks, not native GUI, model quality, full host
conformance or learning evidence. Linux is a container, not a bare-metal claim.

## Website handoff remains blocked

The private source-pin PR is pushed with the immutable release-main source,
72 AtMem pages, six unchanged AI Architect guides and stable 2.3.15 metadata. Normal
import, 109-page build, all static gates, 70 docs tests and 84 browser tests passed.
The existing hosted npm audit failed. Astro was updated from 7.3.3 to 7.4.12 for its
two direct advisories; the complete functional checks passed again on that update.

Hosted validation remains blocked on
[Picomatch GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf).
As verified 2026-11-18, registry-latest 4.0.7 is affected and no patched version is
listed. The audit's ten affected package entries derive from that root advisory.
No audit threshold/exception, framework downgrade or package-name substitution
was introduced. T005 remains open. Only the owner merges the private PR; no owner
merge or live deployment occurred. The package is published; the coordinated
website rollout is incomplete. A later deployment must use the checksum-verified
artifact from validated private main, per repository instructions.

## Why this release matters and what it does not establish

Stable users gain opt-in governed retrieval/MCP, inspectable action outcomes and
reproducible, budgeted evaluation. Operators can inspect retrieved evidence,
action/readback status and failed proposals rather than treating exposure to a
lesson as success. Ordinary memory defaults and authority boundaries remain.

The learning revision failed. The separate final small actual-package comparison
scored 6/6 for no memory, original AtMem and the retained pilot. No reliable accuracy
or learning gain is demonstrated, and those historical artifacts are not a model
benchmark of the stable wheel. Broader Spec 050 production-policy/host-conformance
work remains unchecked and excluded. Specs 052/053 retain their original data and
versions; this release introduces no new paid quality experiment or model call.

Task-owned Mac fixtures/venvs and the Linux container were removed after saving
private logs and sanitized receipts. The original encrypted scientific study
Homes/artifacts are preserved. Windows temporary-fixture cleanup is pending
host availability; its task services had already stopped after the successful
journey, and the later registry recheck never started. The supplied SSH password
is not retained in source, scripts, logs or release evidence.
