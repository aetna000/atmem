# Benchmark review: decisions and research findings

Claude Code 2.1.281 completed one tools-disabled subscription review, explicitly
requesting `claude-opus-5-5` at medium effort. Returned model usage identifies
that same model. The supplied source/results and raw response are protected in
`claude-opus55-medium-review-20261017`; the verbatim response is adjacent in
`2026-10-17-claude-opus55-benchmark-review.md`. This is external-model criticism,
not independent replication, endorsement or a new experimental result.

## Adopted

- Stop further scored tuning on the five familiar Click tasks. Preserve every
  result; P9 is selected tuning evidence, not the final winning implementation.
- Do not use the still-unscored Click set to select a variant. At most it can
  later be a same-repository check on a locked candidate, never cross-repository
  confirmation by itself.
- Verify handshake, tools/list, client allowlists and observed attempts/prepared
  responses separately. No completed calls in 30 traces does not establish that
  tools were unavailable, the agent rejected them, or the model saw the tools.
- Target avoidable exploration turns and large repeated outputs, not just small
  source-pack byte reductions. Byte volumes are not provider token attribution.
- Use established authentic issue tasks and upstream grading, with repository-
  disjoint validation/confirmation, a fixed candidate budget and no mid-stage
  edits. Keep native/pack/retrieval controls distinguishable.
- Preserve scope, currentness, secret screening, isolated homes, sanitized Git,
  protected evaluator material and archive recovery. Keep total usage unknown
  if it cannot be fully measured; do not excuse failed patches as infrastructure.

## Corrections / recommendations not accepted literally

1. Graph traversal DOES participate in construction of the initial source pack:
   `pack_generation` invokes `CodeRetriever`. The 0/30 audit concerns completed
   on-demand MCP calls. It does not show all graph mechanisms were absent. A
   graph-vs-flat-retrieval ablation is needed to isolate graph contribution.
2. Model input counters must be normalized without double-counting cache reads
   already included in total input. Report cached/uncached components separately
   where supplied, retain raw fields and document provider-specific semantics.
3. The post-turn 500k audit is NOT an enforced upper bound: observed runs exceed
   it. Assigning a missing run the cap or observed arm maximum is not a rigorous
   bound. No such value enters primary results; any hypothetical sensitivity
   calculation must expose its assumptions and cannot rescue the primary gate.
4. An equal-byte placebo is a possible diagnostic, not the only valid content
   control. An equally bounded ordinary lexical/source-retrieval baseline is
   often more useful and less misleading than intentionally irrelevant text.
5. We are not adopting a non-inferiority margin or changing the owner’s equal-
   or-better quality requirement. Any different statistical gate must be an
   explicit prospective proposal, not an after-the-fact relaxation.
6. The unrun getLogger guidance pair is too weak for benefit inference. Keep it
   as an unexecuted draft; replace its planned role with exposure verification
   and repository-diverse, retrieval-requiring diagnostics.

## Other repositories and established benchmark options

Primary sources inspected on 2026-10-17:

| Source | Reuse / reason | Remaining qualification |
|---|---|---|
| [SWE-bench](https://github.com/SWE-bench/SWE-bench) | Real issue tasks and official Docker grading; retain FAIL_TO_PASS/PASS_TO_PASS distinction | Exact version, ARM image/build behavior, host/worker isolation and resources |
| [SWE-PolyBench](https://github.com/amazon-science/SWE-PolyBench) | Broader languages, task categories and verified annotations | Dataset revision, annotations, environment and extractor support; not evidence AtMem supports all languages |
| [SWE-bench-Live](https://github.com/microsoft/SWE-bench-Live) | Fresher issues and broader repositories; maintained task/environment pipeline | Pin dataset date/split and matching evaluator; newer public tasks are not guaranteed uncontaminated |
| [SWE-rebench V2 paper](https://proceedings.mlr.press/v306/badertdinov26a.html) | Broader task collection and environment-qualification methodology | Preserve authentic issue provenance; dataset and worker licenses/revisions need separate checking |

The official `SWE-bench/swe-bench-tasks` task-tree object
`39df60edb3d9e709c7f6c19516c1d4b1fa3a8d50` returned an untruncated catalog.
Metadata only was inspected: no gold patch, held-out test patch, hints or
solutions were opened. Its directory names include 9 marshmallow tasks,
44 Requests tasks, 31 Astroid tasks and 56 pydicom tasks. These are catalog
counts, NOT locally qualified counts, not necessarily one dataset split and
not performance or solvability claims.

For a practical Python-first pool, prefer the existing catalog's
`marshmallow-code/marshmallow`, `psf/requests`, and `pylint-dev/astroid` over
inventing more Click cases. They cover serialization, HTTP behavior and Python
code analysis. Candidate different-repository holdback groups include pydicom,
SQLFluff, pvlib, pytest and Sphinx, subject to explicit qualification. Do not
select tasks based on model success. Flask alone would be a weak transfer test
because of its Click/Pallets ecosystem connection.

Also inspected current metadata for attrs, packaging, HTTPX, Jinja and Rich.
They are credible repository candidates, but task availability in a suitable
frozen benchmark was not established. Do not present them as ready-to-run
benchmark tasks or infer source/license details from GitHub's `NOASSERTION`.

## Current decision

No new scored Click run, guidance-model diagnostic or external coding benchmark
has started since the review request. Guidance has passed local contract tests
but remains unqualified for performance claims. The next executable work is the
preflight in [the cross-repository plan](../specs/042-atmem-code/cross-repository-evaluation-plan.md),
not another packing tweak. The 50%/20% goal remains unachieved.

Validation: 173 local replay/MCP/packing/audit checks pass; task inventory and
tracked-file whitespace checks pass. Review, retained-trace audit and plan
snapshots are archived on MEM in `protected-review-generalization-20261017`;
three encrypted bundles round-trip and recover in a fresh process without the
vault. Private archive keys remain internal. No remote CI/publication claim.
