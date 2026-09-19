# AtMem vs Mem0: Market Plan

**Created**: 2026-09-19. Branch: `doctor`.
**Status**: Market plan. Every asset named below already exists in the repository; this is packaging and aiming, not new construction.
**Scope**: Five working days.

**Through-line**: Mem0 is where agent memory gets stored. AtMem is where it gets
governed, explained, and proven.

---

## 1. The core play — govern Mem0, do not replace it

`atmem provider init memory-provider --kind mem0 --mode oss` already runs a
user's existing Mem0 as a context authority underneath AtMem's governance.

This makes switching cost zero. A Mem0 user keeps every line of their Mem0 code
and gains provenance, audit, evidence, lifecycle, and deletion on top. Nobody is
asked to migrate — they are asked to add a layer. Once AtMem is the layer that
answers "why did my agent remember that," the store underneath becomes the
interchangeable part.

**Pitch**: Keep your memory stack. Add the control plane.

## 2. The credibility weapon — a comparison that refuses to be unfair

`atmem/benchmark/external.py` will not compare two runs unless dataset identity,
case IDs, scoring format, and model configuration all match. Otherwise it raises
`not a fair comparison`. The benchmark tool enforces its own methodology.

Every memory-benchmark number in this space gets argued about precisely because
configurations do not match. AtMem can publish a comparison the tool itself
certifies as fair, and invite Mem0 to run it. Whoever declines a fair comparison
loses the argument.

Paired assets: the `integrations/memorybench` overlay pinned to commit
`94e2af54b661d90e77dddbd8fa4fa5b28c07a24e`, and `locomo-smoke.ts`.

**Headline**: not "we beat Mem0 by X%" but **the first agent-memory comparison
you can actually reproduce**.

## 3. The category — memory health

Mem0 sells memory storage. Nobody sells memory health, and the phrase is
unclaimed. AtMem Doctor owns it.

Spec 026 already defines the detectors — expired, stale, contradictory,
duplicate, time-dependent — so the category and the implementation plan already
line up. Storage is a commodity race entered late. Health is a category defined
first, and it makes Mem0 a prerequisite rather than a competitor: the more Mem0
anyone runs, the more memory health they need.

## 4. The engine — velocity pointed outward

Two releases a week is roughly 100 shipping events a year. Each is a content
artifact when pointed outward: a changelog entry with a before/after, a short
capture of the dashboard showing a real finding, one line on X.

Visible shipping cadence is the primary marketing for Bun, Zed, and Supabase —
the cadence itself signals a project that is alive and compounding. This
attaches an output to work already happening.

---

## Five working days

### Day 1 — The wrap demo

Prove the core play in one page and one capture.

- Existing Mem0 application, three lines added, now every memory carries
  provenance and an audit trail.
- 60-second terminal or dashboard capture; before and after on the same data.
- One page: `docs/mem0-governance.md`, ending in the exact commands.
- Ship it as a normal release.

**Gate**: a Mem0 user can read the page and see what they get without installing.

### Day 2 — The fair benchmark

- Run MemoryBench with AtMem and Mem0 under identical configuration.
- Publish results, the exact reproduction commands, and the pinned harness
  commit.
- Lead with the fairness guarantee, not the delta. Show the
  `not a fair comparison` guard as part of the claim.
- Invite Mem0 to reproduce.

**Gate**: a third party can rerun it from the published commands alone.

### Day 3 — Doctor v0 against Mem0 data

- Point the Spec 026 detectors at a Mem0 store, read-only.
- Start with the two cheapest classes: duplicates and contradictions.
- Emit findings in the `atmem/incidents/detect.py` shape — evidence-linked, with
  explicit `assurance` and `external_outcome: unknown`.
- Run it against one real store and record which findings a human agrees are
  real.

**Gate**: at least one finding a human confirms is a genuine problem.

### Day 4 — The support matrix

- Publish the framework table: OpenClaw, MCP, Pydantic AI, LangGraph, OpenAI
  Agents, Microsoft Agent Framework — one memory layer, one audit trail.
- State per row what is verified versus declared, following the existing
  coverage-manifest convention.

**Gate**: the table is a page Mem0 cannot put on their site.

### Day 5 — Package and publish

- One release that bundles Days 1–4.
- Release notes leading with the wrap play and the reproducible benchmark.
- Four content artifacts from work already done: wrap demo, benchmark result,
  first Doctor finding, support matrix.
- Post the benchmark reproduction commands where Mem0 users already are.

**Gate**: every artifact links to something runnable.

---

## What to verify as this runs

- Whether the Mem0 provider path covers a real user's existing store, or needs a
  read adapter for the common deployment shapes.
- Whether MemoryBench under identical configuration produces a stable result
  across repeat runs.
- Which two Doctor detectors survive contact with real Mem0 data.

Findings from Day 3 belong in `tests/fixtures/product/026/`, where Spec 026 T003
already expects them.
