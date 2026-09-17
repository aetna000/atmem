# Public documentation for AtMem 2.3.3

## Scope and users
A new developer can install, store and retrieve scoped memory, select an integration,
and inspect evidence. Operators can diagnose, upgrade and recover. Contributors can
edit documentation publicly without access to private website routes or credentials.
This delivers the documentation slice of private Spec 003, not its future SaaS scope.

## Requirements
- FR-001: Publish /docs/ and getting-started, integrations, reference, examples and
  releases sections; each has useful introductory content and onward links.
- FR-002: Cover 2.3.3 installation/upgrade, CLI, Python, MCP profiles, HTTP/schema,
  OpenClaw, Pydantic AI, LangGraph, delegated providers/HMAC, AtBot, retrieval,
  graph, tasks, lifecycle, dashboard, roles, encrypted evidence, multimodal capture,
  backup/migration, troubleshooting and release limitations. Distinguish supported
  behavior from planned work; show prerequisites and authority on operational guides.
- FR-003: Public Markdown and a page manifest are the single editorial source.
  Every website page names product version, immutable source revision and source/edit links.
- FR-004: Private build accepts only explicitly listed Markdown documents; no MDX,
  scripts, raw HTML execution, arbitrary paths, symlinks or public executable build code.
  Imported content cannot replace any non-doc website route.
- FR-005: Production accepts an immutable public-main ancestor and private-main commit
  only. Owner reviews/merges both repos. PR validation has no deployment credentials.
  A failed build does not alter live hosting. Document GitHub/Firebase access prerequisites.
- FR-006: Reuse website tokens; responsive sidebar, breadcrumbs, headings outline,
  highlighted code, local search and copy controls. No-JS content/navigation remains
  complete. Mobile at 390px has no page overflow; wide tables/code scroll internally.
- FR-007: Examples provide expected results, failure explanations and cleanup.
  Browser examples are labelled synthetic and never call a visitor's local AtMem.
  Runnable quickstart is tested in isolated storage without remote models.
- FR-008: Future product release changes require docs version, release notes, coverage
  manifest and validation update; website refresh is a separate owner-reviewed main PR.
- FR-009: Preserve unrelated work and per-repository Git author identity. Never
  self-merge, bypass protections, overwrite tags or deploy a feature branch.
- FR-010: Validate content inventory, safe imports, links, rendering, search, keyboard,
  no-JS and examples. Record actual results and deployment blockers.

## Acceptance
SC-001: All six section routes and every manifest page build with source/version links.
SC-002: Invalid source paths/HTML/script payloads cannot execute or escape /docs/.
SC-003: Quickstart passes offline in temporary storage; source and release versions agree.
SC-004: At 390px and 1440px navigation and content work, including without JavaScript.
SC-005: CI refuses non-main production and unapproved upstream revisions.
SC-006: No deployment is called complete before production URLs are verified.

## Exclusions and edge cases
No product release or hosted AtMem service, live API playground, public website source,
new authentication system, universal performance claims, or reconstruction of missing
historical evidence. Missing sources fail builds; historic releases remain historic.
Local checkout preview is explicitly non-production and cannot satisfy main provenance.
