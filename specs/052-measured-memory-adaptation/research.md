# Research and decision — 2026-11-18

Primary literature/code review conducted by implementation agent and an explicitly
requested Astra research review. No benchmark scores below are AtMem results.

| Source | Available code / identity | Decision |
|---|---|---|
| [Meta Self-Improving Memory](https://facebookresearch.github.io/RAM/blogs/self_improving_memory/) | [RAM b2d04794cd41c16080cbcdf950cdf640082ee8d6](https://github.com/facebookresearch/RAM/tree/b2d04794cd41c16080cbcdf950cdf640082ee8d6/projects/self_improving_memory), MIT, README and figures only | Borrow bounded LOAD/OFFLOAD proposal/selection separation. No runnable implementation or trained checkpoint found here; no reproduction claim. Their 37/44 non-improving revisions argue against broad search. Weight distillation is separate, out of scope. |
| [SoMem](https://arxiv.org/abs/2611.11929) | [8846a91616e55c382e91c2887ab402b4cfd5c6f6](https://github.com/Qi202/SoMem/tree/8846a91616e55c382e91c2887ab402b4cfd5c6f6), MIT | Retain original evidence alongside compact memory. Their public README says historical results not rerun with public recipes. Avoid another canonical store or ungoverned document editing. |
| [ACE](https://arxiv.org/abs/2510.04618) | [82709de050e1db6e6ef2f07bcb0393560b94992a](https://github.com/ace-agent/ace/tree/82709de050e1db6e6ef2f07bcb0393560b94992a), Apache-2.0 | Incremental bounded notes, reflection as proposal, train/validation/test separation. Ideas only; no code vendored or result inherited. |
| [ALMA](https://arxiv.org/abs/2602.07755) / [MemEvolve](https://arxiv.org/abs/2512.18746) | [ALMA](https://github.com/zksha/alma), [MemEvolve](https://github.com/bingreeky/MemEvolve), Apache-2.0 implementations | Executable memory-design search is too costly and broad for this first pilot. Defer arbitrary code evolution. |
| [A-Mem](https://arxiv.org/abs/2502.12110) / [Reflexion](https://github.com/noahshinn/reflexion) | MIT reference implementations | Useful organization/reflection mechanisms, but neither adding a graph nor repeating solved tasks establishes held-out improvement. |
| [CL-Bench](https://arxiv.org/html/2606.05661v1) | [5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26](https://github.com/pgasawa/continual-learning-bench/tree/5f8c50eb1e84b2eda2ef4faff757dfc812a0ea26), Apache-2.0 | Objective database task; include simple bounded transcript ICL, which outperformed dedicated memory methods in their study. No implication those results predict this pilot. |
| [AI Agents That Matter](https://arxiv.org/abs/2407.01502) | Primary evaluation-methodology paper | Freeze holdout, measure total cost, avoid best-of-many selection presented as generalization. |

## Chosen mechanism
One training-derived revision to LOAD/OFFLOAD prompts, owner-invoked inside a
sandboxed experiment. Same observed training trajectories, bounded notes, fixed
tools and runtime for every policy. Freeze both starting memory and instruction
text before final evaluation. Treat the combined intervention (different notes
and instructions) as such; do not assert it isolates retrieval from writing.
No-memory and bounded uncompressed training observations are controls in addition
to generic notes. The strongest simple baseline, not merely the weakest arm,
matters. No model-generated evaluation, weight learning or production activation.

## Dataset and evaluator hazards
Immutable HF snapshot `a0cc57eeb9a54f01c0490a1b46cb705b4e05aa19`, database
SHA256s `edf8ee80ff125de0bfd6c37a1d185efa9e3037ce28eb1bd1d32ae0829bd264a6`
and `a53d523f70604be0e4328f3722417895250ac35e1127cc504b609576aee70fad`.
Downloaded public benchmark tables derive from Amazon Reviews 2023; code is
Apache-2.0 but the HF snapshot has no dataset license card. Do not redistribute
DBs or labels or train weights. Explicit study egress covers public task/schema/
query result excerpts only, no private data. This provenance gap precludes
claiming fully licensed production benchmark qualification.

Upstream terminal feedback reveals correct answers and persists gold labels.
Keep labels exclusively in the grader; send no terminal correctness feedback to
final agents, and never offload final traces. Upstream integer/float evaluator
extracts first regex number and allows 1% float error. Our structured scalar
grader additionally enforces exact integer/finite scalar output; independently
execute gold SQL to verify dataset integrity and retain disagreement counts.
Report adapted metric, not unmodified official benchmark rank.

Training IDs1–10, validation11–15, final16–30 and drift101–105. First3 inspected
questions stay training. One shared DB with a drift snapshot gives few independent
episodes, so uncertainty remains diagnostic even with many questions. A pilot's
positive delta cannot qualify broad continual learning. Reject/unknown is a valid
result; no extra revisions or final reruns to manufacture success.
