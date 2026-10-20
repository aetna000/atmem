# GPU SWE-Pruner: matched short Click follow-up

Owner authorized Vast.ai with a total USD 3 ceiling, including compute,
storage and bandwidth. One owned rental at a time; retain failed preparations;
use a deadline/budget watcher and destroy the rental after evidence recovery.
No training, owner-data upload or cloud exposure of model subscription keys.

## Frozen coding comparison (before dispatch)

Same previously inspected Click task b67832c and frozen parent source/grader as
the October 19 diagnostic. Four fresh serial sessions in fixed order:
native, upstream Cognee, AtMem curated, AtMem curated + upstream SWE-Pruner.
One attempt per configuration, no task retries, checkpoint/threshold selection,
new patch hints or post-grade tuning. Prepare and qualify every configuration
before the first model invocation; grade only after all attempts terminate.

All receive the same bounded `read_source(path,start,end,goal)` tool schema
(source Python files only, at most 400 lines and 24,000 UTF-8 bytes), plus the
existing identical offline workspace command tool for search, edits and tests.
Only the fourth configuration sends source-read windows and the model's goal
to the GPU skimmer. Other configurations receive the full requested window.
Returned omissions and source digests remain explicit. Native source remains
available to recover omitted evidence. Audit read-tool usage, native read
bypasses, errors, source bytes before/after pruning and GPU inference time.

Graph tools remain optional in Cognee/AtMem configurations, with the same short
interface-specific guidance as the prior diagnostic. AtMem uses its curated
discover/fetch profile, no automatically injected source pack and no experience.
Cognee uses the pinned actual upstream SDK's deterministic CODE route through
the existing read-only SDK transport, not a substituted implementation.
No graph-consult gate. Actual zero graph calls remain a reported outcome.

Same Claude subscription model alias `claude-opus-5-5`, medium effort,
requested MAX_THINKING_TOKENS=0 (actual usage may still include thinking),
240 seconds, 30 tools, 500,000 audited input+output tokens per configuration.
Same isolated configuration, source/evaluator/network sandbox, runtime
qualification and frozen test exclusions. Retain every failure and usage
receipt; missing usage is unknown, not zero. Native commands can still read
source; report bypasses rather than assuming every source read was pruned.

## Neural execution gate

Use the public swe-pruner 0.1.1 package and original public `prune` wrapper;
no padding-trim adaptation, weight changes, learned retraining or altered
threshold. Model ayanami-kitasan/code-pruner at
863cee3198c715c9df1faa422a3490e0832bb734; backbone config at
e61197ed45024b0ed8a2d74b80b4d909f1255473. Require CUDA and active
FlashAttention-2. Record exact packages, GPU, attention backend, cold load and
original tokenizer counts separately from the coding model's actual usage.
Before coding dispatch, execute the two staged authentic pre-change Click
source windows and retain exact input/output. Transport a bounded public-source
window over a private SSH pipe; do not run the coding agent or its credentials
on the rented host. Record original 8,192-position wrapper behavior unchanged.

## Reporting and limits

Report all four configurations: task/frozen-test correctness, full cached and
uncached input/output usage, agent time including tool/network latency, indexing
and setup separately, graph/read calls and pruning errors. Raw requests,
responses, patches, grades and GPU inference traces are retained in protected
benchmark evidence; encrypted verified archives go to MEM, keys stay local.

This is one reused easy issue, not independent generalization evidence or a
SWE-bench score. Fixed order/cache effects and natural solve variation remain.
Source-window compression is not an end-to-end token-saving claim. The new
read interface changes the experiment: do not pool its results with the earlier
three-arm comparison. This benchmark adapter does not imply that native CLI
history masking or SWE-Pruner is shipped in AtMem's installation.
