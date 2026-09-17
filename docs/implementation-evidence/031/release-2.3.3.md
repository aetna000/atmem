# Stable 2.3.3 release validation

## Approved scope

On 2026-09-17 the owner explicitly approved moving the 2× full-preparation target
to future work and publishing stable 2.3.3. Existing retrieval defaults remain
unchanged; core fusion/scoped graph and matrix reuse are developer opt-ins.
The release does not claim comparative superiority or full Spec 031 completion.
AtBot source is unchanged from the 2.3.2 release and remains published 0.1.0.

## Local preflight

- Isolated AtMem Home, Python 3.12: 1,588 passed, 15 skipped, 133.82 seconds.
  This workspace run includes separately untracked benchmark tests; the clean
  release candidate is validated separately by the publication workflow.
- AtBot: 17 passed.
- Version/documentation checks after alignment: 24 passed, including a new
  package/lockfile/plugin/installer/companion/release-note consistency test.
- OpenClaw 2.3.3: typecheck, build, hooks, setup, tool observation, spool,
  task/delegated conformance and smoke passed against locked host 2026.8.1.
  Delegation includes 3 positive and 20 negative/stateful contract vectors.
- Archive browser layout: 2048, 1280, 900 and 390 px passed containment,
  non-overlap and no horizontal page overflow checks with synthetic evidence.
- Deterministic memory benchmark: 24 cases passed; quality digest
  `sha256:426d3bdcdced658514839fce61a705a008892fea8de554d5fb8c373488087f88`.
- All 218 tracked Markdown files scanned: zero missing local path targets.
  Existing documentation tests also pass. External URLs and every fragment anchor
  are not certified by that local-path scan.
- Active README, status, roadmap, bridge guide, release note and runtime pins
  identify stable 2.3.3 / bridge 2.3.3 / AtBot 0.1.0. Immutable benchmark manifest
  names and historical releases keep their original version labels.

## Publication gates

The complete [pre-tag workflow](https://github.com/aetna000/atmem/actions/runs/35186097845)
passed for source commit `64312964ba4065c8f2c3dd8f59d717e460792649`.
All Python 3.10–3.13, companion, optional framework/provider, bridge, build,
installed-wheel and six persisted-upgrade profiles succeeded. Publication jobs
were intentionally skipped for this workflow-dispatch run. A separate local
installed-wheel dependency check, HMAC/delegated smoke and authentic 2.3.2-to-2.3.3
upgrade also passed. The wheel rebuilt from the source distribution successfully.
NumPy cache tests ran locally with NumPy installed: 10 passed.

Local clean-build artifacts (not the registry artifact identities):

- Wheel SHA-256: `b66dcf475658776b83ea0500f8b204ac86552024d7359f20603bbaaeff6780c6`.
- Sdist SHA-256: `c04887add984a2c86f041eb54c6205d29cba01f47d6561320235d6ee019b5d56`.

This evidence-only update does not change runtime code. The final documentation
commit must pass preflight as well before the tag is created.

The `publish` workflow must pass on the clean candidate before tagging, covering
Python 3.10–3.13, optional framework/provider dependencies, companion/bridge,
build/sdist/metadata, installed wheels and persisted upgrades including 2.3.2.
Publication is not established by this source note: verify the `v2.3.3` workflow,
GitHub stable release, PyPI 2.3.3 and npm bridge 2.3.3 after tagging. No new AtBot
tag is required because its source and exact compatibility pin are unchanged.

The workspace's unrelated research and MemoryBench adapter files are excluded
from this release. Candidate creation and publication use a clean worktree, not
a wheel built from those unrelated untracked files. Ordinary safety/artifact gates
are unchanged by the approved performance-target deferral.
