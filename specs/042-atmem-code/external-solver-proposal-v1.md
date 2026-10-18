# First-task solver-proposal grader — prospective v1

Extend T077 with an evaluator-only entry point accepting a stopped solver's
bounded public source snapshot. This is specific to the already qualified
Marshmallow task and immutable image, not qualification for the other tasks.
Keep private evaluator material and public proposal as distinct, exact roles.
The host supplies verified original files/modes; the model supplies neither
the baseline nor evaluator inputs. No new memory or grading algorithm.

Reuse the public-test decoder, Git base validation, source-only assembler,
descriptor-relative capture/tree installer and pinned upstream grading logic.
Preserve image-only runtime files; restore frozen tests; refuse private-runtime
collisions and out-of-scope changes before running repository code. Do not
write the unused gold patch into the private evaluator filesystem. This is
not an adversarial anti-cheating guarantee for arbitrary code inspecting its
own private test process. Solver isolation and source origin remain separately
verified by the host, not inferred from a passing test result.

Before model repair scoring, run two zero-inference Windows controls through
the new proposal endpoint: unchanged public source and the already retained
reference projected onto public source paths. The latter remains evaluator-only
and never enters model prompts, context indexes or workspaces. Require the
same original/assembled digests as the qualified prior controls, original 0/8
versus reference 8/8 target passes, all 61 regression passes in each, no skips,
no policy/worker/controller/cleanup failures. Retain raw plans, code, requests,
streams and outcomes; do not overwrite older controls or relabel references
as agent solutions. No test or token benefit claim follows from these controls.

Native/AtMem model repair attempts must subsequently bind a complete trace,
normal or interrupted usage status, stopped-workspace capture and the exact
candidate handed to this grader. Keep native and AtMem environments and limits
matched. Tool scratch belongs outside source before scoring; no retrospective
exemption, unknown-usage imputation, row dropping or historical score changes.
