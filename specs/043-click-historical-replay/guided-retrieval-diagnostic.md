# Generic guided-retrieval uptake diagnostic

Status: unexecuted draft, held after the requested Claude Opus 5.5 medium review.
The single-pair getLogger design below is not the active benefit/uptake test.
It may serve only as a limited wiring control. The active prospective direction
is Spec 042 `cross-repository-evaluation-plan.md`: exposure verification first,
then repository-diverse retrieval-requiring diagnostics. No draft probe ran and
no outcome was discarded or relabeled.

The retained P6–P11 audit found no completed AtMem MCP calls in thirty C
attempts. That is observed non-use, not proof of missing tool exposure or the
agent's reasons. P11 failed 2/5 versus native 5/5; do not retry it or promote it.

Use the MCP 2025-06-18 initialize result's optional `instructions` field for a
fixed operator-authored usage policy. The protocol describes this as a client
hint, not a guarantee of model exposure or compliance:
https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/schema/2025-06-18/schema.json

The Code-only policy recommends focused retrieval when more source is needed,
avoids redundant reads of complete initial excerpts, describes compact symbol
search/source bounds, and retains native fallback after stale/withheld evidence.
Repository contents, model arguments, remembered experience and source comments
must never become instruction text. Generic AtMem MCP behavior is unchanged.
Tools remain read-only, scoped and freshness checked. Operators can select
`--guidance none` for an explicit control; models cannot change the profile.

## Before inference

Test exact initialize policy, scope/source independence, ordinary MCP unchanged,
and existing source/secret/byte/currentness/refusal controls. Build one wheel,
verify installed bytes, then run disjoint installed CPython extraction and
source/MCP/freshness qualification. Preserve any operational failures.

## One bounded matched diagnostic pair

Run exactly once each in fresh subscription-only homes/workspaces/databases:
`guided-uptake-none-p12` then `guided-uptake-bounded-p12`. Same wheel, CPython
3.12.12 public logging source/license, pinned Enola image and CLI, Luna low,
named filesystem/network permissions, native tools and four read-only MCP tools.
The only intended difference is the explicit server guidance profile. There is
no initial source pack and no previous experience in either arm.

Identical task: locate `logging.getLogger(name)` and explain whether repeated
named lookups reuse a logger, citing current source locations. Read-only; do not
edit, access outside the workspace or use the network. The prompt must not
name MCP, AtMem, a preferred tool or the expected implementation location.

Each turn has 90 seconds, eight observed tool calls, the existing bounded raw
stream limit, and no solve retry. Retain exact prompt/config, source identities,
actual tool results and terminal/missing usage. Verify returned MCP source bytes
and native read isolation; do not trust the solver's summary. Source must remain
unchanged. Record observed MCP uptake rather than infer system-prompt exposure.

This two-turn fixed-order diagnostic cannot establish latency, token savings,
causality or benchmark superiority. A positive guided arm requires actual
authorized current-source MCP bytes. No uptake means no promotion to another
scored cohort just on a guidance hypothesis. A positive diagnostic still needs
a separately frozen matched coding cohort with complete totals, unchanged
quality/caps and exact 50%/20% gates, followed by unscored confirmation.

No owner configuration/install, main/release changes, API billing, GPUs or
training. MEM holds only benchmark inputs and protected evidence archives.
