# Plan — stable 2.3.15

Reuse existing implementation and encrypted authority boundaries; this release
introduces no canonical memory schema or new learning algorithm. Build one stable
wheel/sdist from the isolated source tree, align bridge metadata, and test the same
wheel digest in isolated venvs on native Windows11/Python3.12, native macOS ARM64
and pinned Debian12/Python3.12 ARM64 Docker. Add a portable user-journey tool that
uses installed CLI/SDK APIs, ephemeral ports, local fixture documents and its own
Homes. Capture content-free receipts while keeping bootstrap credentials private.
The existing Windows user's Home and dirty source worktrees remain untouched.

Reconcile Spec050 as the broader unfinished roadmap: default core memory remains
supported; new RAG/MCP/outcome surfaces are explicit opt-ins; production policy
qualification, broad Hermes interception and reliable learning remain unqualified.
Spec052 describes its four-arm experiment; Spec053 describes the actual installed
three-arm diagnostic. Their frozen evidence is not a stable-wheel benchmark.
Spec054 owns the stable release decision and operational acceptance, replacing
the unpublished beta delivery target. Normalize current docs and keep historical
preregistrations/candidate pins intact. No new model calls.

Run meaningful journey failures to ground any fixes, then relevant regression tests
and all release gates. Consolidate the public PR against main, merge normally,
tag the exact reviewed source and wait for publisher jobs. Verify GitHub stable/
PyPI/npm and install the published artifact, not only the local wheel. Then pin
the public merge in the private site and prepare its tested owner-review PR using
the existing SSH remote/author. No private self-merge or local feature deployment.

Evidence: specs/054-stable-cross-platform-release/evidence.md plus content-free
platform receipts. Secrets and detailed installer logs remain owner-private in the
external task directory. Every publication state is verified independently.

Post-tag status: package and registries verified. The original private website
dependency audit blocker was remediated with a tested local source patch and
additional source/advisory gates. All private main validation passed. The owner
merged the PR and explicitly authorized Hosting publication; the checksum-verified
main artifact was deployed and both live domains were verified. No audit waiver,
private self-merge or local feature-branch deployment occurred. See publication.json.
