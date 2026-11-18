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

## Website publication verified

The initial private website audit failed on Picomatch GHSA-fc5q-39xc-vjpf.
Astro's direct advisories were patched; the remaining issue was subsequently
remediated with a verified local source patch, enforced source/attack checks and
upstream advisory monitoring. The audit threshold remained unchanged. The final
PR and merged-main validation passed all build, security, docs and browser checks.

The owner merged the private PR at main commit
`86a8ff50c0283a2c5c98fc7fea289bc42f030b9f` and explicitly requested deployment.
Validation run `44305719623` succeeded for that exact main commit.
Its `validated-website` artifact checksum passed:
`552721f05a3ce39003a459113b4ebe7310a14632ffbb9ac0749ab3f91c30d814`.
Firebase CLI deployed Hosting only from the extracted validated artifact to
`atmemai`; Hosting version `28a21b10ca78ece9`.
No local rebuild, PR artifact, Firestore rule deployment or private self-merge was used.

As verified `2026-11-18T12:47:41.156295+00:00`, 18 live URLs on
https://atmem.ai and https://atmemai.web.app returned HTTP 200 and matched the
validated artifact byte-for-byte. Homepage, docs, getting started, AtFlows,
governed retrieval, Hermes, study reference, stable release and search data passed.
Both domains' live browser checks passed search-result navigation, getting-started
content/copy controls and stable release rendering without page errors.
Docs display stable 2.3.15 and immutable public source
`bca4e925fc89a3c01b6c95fba4460f59749ce8f5`. T005 is complete. The package,
owner website merge and live deployment are now independently verified.

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
