# Design review — 2026-09-17

Final Claude verdict: APPROVE — no genuine blocker remains. Final review clarified
that CSS design tokens are not authentication tokens: all published docs are public.
Agreed implementation details: fail on search index exceeding 1 MiB; deterministic
heading collision suffixes; 30-day deployment artifacts; Firebase release rollback;
committed content SHA256 inventory reviewed alongside source-pin updates.
An intermediate response simulated unavailable tools and was discarded; no tool
output from that response was used as evidence.

Spec Kit analysis: 10 requirements, 10 tasks, 100% requirement coverage, no critical
or high findings, no unmapped tasks or constitutional conflicts. T010 is deliberately
gated on the owner's two main merges and configured production credentials.
Claude CLI performed a read-only proposal review (tools disabled).
Its initial concern about merging repositories was a misunderstanding: each owner
merges PRs into that repository's own main. There is no cross-repository Git merge.

Accepted recommendations:
- Split secretless import/render validation from credentialed artifact-only deployment.
- Use a small first-party search index, static section indexes as no-JS fallback.
- Validate manifest version against Python package metadata; latest-only URLs with
  immutable source links and historic release notes. Preserve routes or add redirects.
- Enforce file/count/total limits, normalized paths, no symlinks/case collisions,
  safe URL schemes and no remote images; sanitize after Markdown rendering.
- Mobile native disclosure navigation; copy controls inserted only with JavaScript.
- Add negative import tests and installed-artifact offline quickstart verification.
- Use existing shared tokens, bounded content width, keyboard focus and no backend.

Not adopted:
- Submodule: Git blob import is narrower and needs no public code execution.
- New frontmatter library and Starlight: existing Astro plus a small renderer keeps
  theme and dependency footprint consistent; manifest owns page titles/routes.
- Requiring a second reviewer for docs exemptions conflicts with sole owner policy;
  no exemption is needed for version/manifest validation.
- Broad CSP replacement would affect existing waitlist; retain its policy and add
  docs-scoped restrictions without changing unrelated routes.
