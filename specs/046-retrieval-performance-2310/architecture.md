# Source-grounded memory and closed-loop evidence discovery

## Design decision

Optimize the complete path from retained experience to a correct external action,
not the score of a single retrieval call. These are distinct failure boundaries:
source representation, candidate discovery, applicable-state resolution, evidence
assembly, host tool selection, and confirmed execution. Do not attribute every
failed action to ranking, or infer success from a plausible final answer.

### Write path: original evidence plus rebuildable understanding

Retain immutable conversations with speaker, observation/event/effective time,
scope and source ranges. Derive contextual assertions, entity aliases, explicit
instructions, observed behavior, proposed plans and confirmed outcomes. Keep
these categories distinct. Resolve pronouns and dates using source context, not
today's date. Every derived assertion links to supporting original ranges;
inferences retain their type and competing evidence. A model proposes meaning;
the existing governed formation boundary owns admission and lifecycle.

Index self-contained contextual assertions AND coherent original passages.
Keep exact matching for names, amounts and identifiers. Original evidence is
never discarded in favor of a generated summary. Semantic indexes are optional,
generation-aware derivatives, not a new authority database.

### Read path: discover before judging completeness

1. Authorize scope/lifecycle and bind a query session to the canonical generation.
2. Decompose the request into needed facts, temporal applicability and intended
   external operation. This decomposition cannot access evaluator annotations.
3. Nominate from lexical and semantic channels independently. Neither channel
   depends on the other already declaring the query sufficient.
4. Fuse bounded candidates, inspect coherent supporting ranges and resolve
   entity/temporal relationships. Preserve exclusions and contradictions.
5. Assemble complementary evidence against the actual information needs. Check
   the bytes that will be delivered, not just pre-packing candidates.
6. If needs remain, allow scoped read-only search/inspect on those needs. Return
   evidence with provenance and uncertainty; never relabel a similarity score
   as semantic proof. Stop on the shared operation/byte/time budget.
7. The host uses its configured application tools, verifies their responses and
   distinguishes completion, partial completion and failure. Local file creation
   is not proof of a successful operation in a connected application.

Read authorization and semantic sufficiency are separate. Policy rejection and
stale/revoked scope remain terminal. Authorized ambiguous evidence may be inspected
through an explicitly investigative API without changing existing V3 context
injection/status contracts. A negative statement is not by itself proof that a
user's request is contradictory. New semantic validation must test this distinction.

## Current implementation disposition

The deterministic public profile remains unchanged. The existing experimental
semantic supplement remains available for its frozen comparison, but is not the
target architecture: supplementing only already-sufficient lexical answers cannot
rescue missing lexical evidence. Its exact-vector backend is capacity-bounded and
does not satisfy the production indexed-search requirement.

Add a product-owned `EvidenceDiscoverySession` with independent nominations,
canonical reload, renewed authorization, shared budgets and exact source records.
Expose only search/inspect via MCP; do not re-enable write/capture tools or duplicate
automatic injection to obtain search. Application setup, a durable session lease,
index lifecycle integration, host wiring and installed-artifact qualification are
separate required tasks; an in-process tested primitive is not a shipped adapter.

Reuse current Mem0's contextual extraction, linked facts and semantic/keyword/entity
discovery principles after inspecting pinned source. Do not describe its current
additive extraction as the older automatic overwrite pipeline, and do not assume
its OSS configuration is identical to a hosted published benchmark system.

## Verification order

### Proposed refinement: separate provenance storage from model presentation

An evidence response must retain complete canonical provenance, but the model
need not repeatedly receive long cryptographic identifiers and hashes for every
short quotation. Measure original quotation bytes separately from response
structure, identifiers and source metadata before changing this boundary.
Detailed measurements remain private and are not task-quality or token claims.

If a separately selected compact profile is implemented, preserve every original
quotation, source ordering and meaningful offsets. Replace only repetitive opaque
identifiers in model presentation with host-owned, lease-scoped references. Retain
the exact reference-to-canonical mapping, full provenance, original package bytes
and transformed delivery bytes in authorized receipts. Resolve inspection through
that mapping and freshly recheck scope, generation, lifecycle and the same shared
budgets; an alias cannot authorize another record or reset a lease.

Use a versioned presentation contract and preserve the existing full-provenance
response by default. Do not silently truncate text, turn an inferred label into
truth, remove owner-visible provenance or confuse an alias with a canonical ID.
Mem0's pinned implementation maps existing memory UUIDs to bounded local IDs
before model extraction; reuse this design principle rather than inventing a new
model-owned identity system ([primary source](https://github.com/mem0ai/mem0/blob/94c3fe9f238f3dbf29c9ce98643bd71eb13077cd/mem0/memory/main.py#L854)).

This is a proposal, not a change to the running condition or an accepted quality
gain. Require mapping/inspection round trips, byte-exact original quotes,
revocation/restart negatives, receipt replay and separately frozen paired quality,
token and latency evaluation before promotion. Metadata byte reduction alone
does not establish model-token savings, complete evidence or better task outcomes.

The explicitly selected workflow profile may attach bounded search/inspect tools
and fixed host application-completion guidance. A semantic partial/conflicted/
contradicted result can start investigation; policy-withheld, inactive, stale and
unavailable/denied results cannot. The V3 injection/status compatibility contract
is unchanged. Discovery leases are administrator-created, generation-bound and
encrypted; operation/byte reservations persist before work, including on crashes.
Models cannot mint leases or choose scope, databases, providers or budget resets.

Application guidance is separate from memory content and preserves native tools.
It does not insert expected tool calls or answer-specific arguments. A host-only
control with the identical guidance is required to attribute memory-only benefit.
An additional explicit strict-argument host policy may reject undeclared root
arguments before forwarding an MCP call (unless additionalProperties=true is
explicit). This is intentionally stricter than JSON Schema's omitted default;
it never rewrites values, silently drops parameters or repairs a recorded action.
Both guarded and unguarded attempts remain inspectable and are distinct profiles.

### State-assessed investigative profile

An optional AtBot classifier receives only the authorized, bounded evidence and
the authenticated question. It proposes source-quoted applicability classes
(current-at-query, future-effective, historical, conditional or unresolved) and
event stages (observed, requested, proposed, accepted, completed or standing rule).
It cannot generate facts, action arguments or mutations. AtMem separately checks
the response shape, exact quote containment, source IDs, budgets and live authority.
These checks bind literal evidence; labels remain model interpretations, not a
sufficiency or truth certificate. The reader still interprets and acts.

Remote classification requires an administrator-created lease explicitly allowing
that egress, a named provider/model and a pre-egress audit. It is never a silent
fallback or an implicit default. Query-only failure keeps the original authorized
evidence with a visible assessment failure/defer status; authority failure still
withholds. The profile reserves space for annotations within the same response
byte budget and skips classification when insufficient operation time remains.
Measure its separate model calls, tokens, cost and latency against the unchanged
reader and the corresponding host/discovery controls.

### Computed temporal evidence (independent option)

The default-off `source_time_frames` option computes date-order relationships
between explicitly quoted intervals and an explicit host question timestamp.
This is a deterministic read projection, not a second semantic classifier:
`inside_quoted_period`, `not_started_at_query`, `ended_before_query`, or
`on_period_boundary`. Retain the exact interval quote, source ID, endpoints and
as-of date. A boundary does not establish inclusive/exclusive semantics; an
interval does not prove ownership, acceptance, completion or truth. Unsupported
date languages, relative dates, invalid intervals and missing question dates
remain unparsed rather than receiving an invented date.

Compute only from the already-authorized emitted source evidence, within the
same response budget and final authorization/audit boundary. Never remove the
original evidence to fit annotations. When both options are selected and space
is insufficient, visibly omit soft classifications before computed frames.
The two options remain separately configurable for attribution. Contract and
HTTP-boundary tests precede a fresh frozen scored condition; a unit-test pass
does not establish end-task benefit or unlock the full campaign.

### Atomic source bundles (independent option)

Sentence ranking is nomination, not the final presentation unit. An optional
source-bundle presentation expands nominated ranges to authorized active ranges
from the same source part, deduplicates identical ranges, orders them by source
offset, and packs each group atomically. Preserve existing unit IDs, original
text and evidence-range contracts; add group membership rather than generate a
summary. Fresh authority checks cover every expanded member. Partial authority
does not permit surrounding inaccessible ranges to be disclosed. A group is
not a whole-source, authorship, truth or semantic-completeness certificate.

Bound expansion to eight nominated source parts, 32 delivered ranges and each
operation's existing byte/time limits. Oversized groups are omitted explicitly,
not silently split into a headline without its qualifications. Exact duplicate
ranges need only one representative unit; preserve the canonical records.
The option is default-off, separately measured, and changes neither ranking
authority nor canonical formation. Tests must cover source ordering, same-part
expansion, restricted manifests, lifecycle changes, duplicate ranges, atomic
budget omission and source immutability before scored evaluation.

### Draft-to-evidence review qualification

Qualify a bounded AtBot read-only reviewer against retained application drafts
before deciding whether to integrate a host execution preflight. Supply only the
original request, already-authorized retrieved source text, and proposed tool
names/arguments. Never supply evaluator facts, criteria, expected outcomes or
grades. Findings must point to an exact source quote and, for an asserted draft
error, an exact draft quote. Return closed issue classes, not rewritten actions,
new facts, a chain of thought, confidence or an authority/approval decision.

Measure both missed errors and false alarms on successful actions. A retrospective
finding is not a repaired task or a new task-success score. No application hook,
write rejection or remote permission is enabled merely by implementing this
qualification primitive. Any later execution integration requires separate host
policy, explicit egress permission, fresh authority, bounded retries, native-agent
repair rather than payload rewriting, and a matched host-policy control. Existing
native tool behavior and deterministic defaults remain unchanged.

An exposure audit must distinguish unavailable evidence from evidence already
delivered but omitted or misapplied in the action. A historical request can be
answered incorrectly even when its sources are present: a later standing policy
does not automatically govern an earlier, episode-specific exception. Applicability
therefore includes the requested event/case and condition, not merely a date or
the newest mention. Preserve those distinctions in any later state contract;
do not repair them using benchmark-specific names, dates or expected arguments.

For retrospective qualification, include the initial packet only when its exact
bytes occur in the recorded system/developer input, then collect matched memory
tool results strictly before the recorded action decision. Do not substitute
post-action retrieval, post-action application results or evaluator annotations.
An explicitly selected later action may include earlier application results only
when matched to their original recorded calls and actually observed before that
decision. Preserve exact bytes and attribution; do not infer unobserved application
state. A final-action review is not a review of all earlier actions. Preserve the
complete bounded packet or mark the case unreviewed; no silent quote pruning.
An original host identity may accompany it only when independently observed in
the same input. Missing or ambiguous application evidence remains an explicit
review-coverage limitation. Snapshot validation witnesses before invoking an
interchangeable provider and detach returned findings from provider-owned aliases.
These controls qualify the review boundary, not its semantic accuracy.

### Evaluator-only representation controls

Before choosing a large formation rewrite, distinguish retrieval/representation
limits from the reader's action-taking ceiling. In a separate research control,
the evaluator may supply (a) the benchmark-linked original dated messages or
(b) its normalized fact statements directly to the native reader. These are
explicitly answer-informed diagnostic controls, never AtMem results, training,
memory writes, retrieval candidates, model calibration or product configuration.
Neither control may be packaged as a participant submission. Preserve original
tasks, app state, reader/grader settings and byte bounds; refuse oversized packets
rather than quietly truncate supporting evidence. Never copy these packets or
their task-to-fact mapping into product code, canonical memory or normal indexes.
Keep all generated packets, results and task mappings in ignored/private storage.
FR-007 remains unchanged for every actual product invocation; this exception is
restricted to the explicitly labelled non-product evaluator-control role.

### Native host identity parity

The official reference constructs SOUL.md using its shared template and the
persona display name from the public persona registry. Preserve this legitimate
host identity independently of memory search; do not infer names from opaque
scope identifiers or fact annotations. New explicitly selected reference-host
conditions copy the exact official identity into fresh native profiles and
record both template/registry hashes. Existing profiles are never silently
overwritten. A transport guard checks the full configured identity in actual
system/developer input before forwarding any model request or reserving spend.

Apply identical identity and application policy to candidate and comparator.
Earlier conditions without this identity retain their original results and
cannot be presented as matched to the new host setup or published hosted Mem0.
This is host-setup parity, not a new extracted memory fact, semantic model gain,
authorization by display name, or proof that the remaining failures are solved.

Before another scored candidate, explain observable failures using saved traces.
Use offline tests to build the cross-pillar foundation together where dependencies
require it; retain separately selectable components for ablation. This supersedes
the earlier requirement to wait for a quality pass before writing the next
pillar's offline code. It does not unlock paid evaluations, mark any pillar
accepted, permit answer-specific fixes, or unlock the final full run.

Require independent tests for semantic-only discovery, missing qualifications,
old-versus-current assertions, identity resolution, explicit/inferred preferences,
recovery after an incomplete first search, scope revocation, deletion and budget
exhaustion. Runtime evidence must distinguish the model seeing sufficient facts
from choosing and completing the correct application operation. No preset perfect
score is promised; each remaining failure needs an observed cause and a tested
correction rather than another unexplained aggregate score.

## Findings incorporated into the design — 2026-10-22

These are engineering dispositions, not a declaration that the quality gates
passed. Task-level evidence and scores remain in ignored `validation.md` and
private external storage under the owner's evidence-isolation requirement.

1. **Independent discovery is necessary but not the whole solution.** A lexical
   sufficiency gate cannot rescue semantic-only misses. Keep independent channels
   and bounded follow-up, then distinguish failure to locate evidence from failure
   to interpret it and failure to execute the intended application operation.
2. **Relevance is not a resolved state.** Preserve actor attribution, observation
   versus effective time, conditions, exclusions and conflicting assertions with
   their source ranges. Do not infer historical authorship from opaque identifiers
   or invent metadata missing from legacy imports. A request-specific evidence
   dossier is a design direction within the existing discovery/coverage contracts,
   not an implemented or accepted new API. It must expose unresolved needs and
   source-backed alternatives rather than generate an authoritative answer.
3. **More context or annotations are not automatically better.** Separate computed
   time, expanded source bundles and source-state interpretation in ablations.
   Faster SQL establishes a systems improvement only; it does not qualify the
   resulting evidence presentation. Retain rejected variants without promoting
   them or enabling them by default. Normalized facts alone have not established
   an advantage over coherent original evidence in the diagnostic controls.
4. **Host parity is part of the experiment.** Official identity and application
   guidance affect interpretation and execution. Match those settings across arms;
   never credit a host correction as a memory-only improvement. Changing the host
   does not retroactively repair or invalidate retained historical executions.
5. **A semantic reviewer is not yet an execution gate.** Retrospective draft
   findings included false alarms. A reviewer seeing memory alone may lack facts
   obtained through application tools, and must not label every unsupported-in-its-
   packet statement contradictory. Keep this prototype unwired pending independent
   qualification against the complete authorized evidence actually available.
6. **Completion must be operationally supervised.** Conflicting duplicate JSON
   argument keys cannot be silently normalized. Preserve exact wire evidence and
   distinguish recording/export errors from task failure and grading errors.
   Reconcile interrupted executions before resumption; do not reroll a model
   answer to hide an export problem. A dependent comparison that did not run must
   remain explicitly incomplete. Pin runtime interpreters outside ephemeral
   cleanup paths and check them before dispatch; report stopped processes instead
   of describing a queued campaign as still running.

On macOS, interpreter availability and import success are insufficient runtime
checks. Verify the controller/application executable and shared Python library
code signatures before claiming budget or starting a model request. Record the
actual interpreter, Python/OpenSSL versions and binary hashes. A failed signature
blocks dispatch; do not disable OS security or patch a running binary. Preserve
interrupted conditions and uncertain calls separately after a clean vendor-runtime
replacement; never combine the best answers across platform conditions.

No new canonical-memory mutation, automatic action approval, source pruning,
default-profile change or accepted full-run readiness follows from these findings.

### Subscription cash and resource accounting are different bounds

A qualified subscription bridge has zero incremental API cash cost, not zero
tokens or unlimited capacity. Reserve zero API dollars only for that explicitly
selected, strictly loopback transport and supported reader family. Keep native
token/output/turn constraints, exact request records and provider-reported usage.
Do not reserve a counterfactual paid-API price against its shared memory/judging
cash ledger. Paid requests retain conservative positive reservations, uncertain
charges and overrun stops. A model-supplied field cannot select the funding mode.

Record whether forwarding started when a guard rejects work. For legacy guarded
requests, prove no forwarding from the exact retained request, matching original
campaign ledger with no reservation row, actual native HTTP-402 failure witness
and pinned transport control flow. Absence of a response alone proves nothing.
Never apply this proof to a paid or already-reserved request. Retained app effects
can be graded even when the CLI stopped; they need not satisfy the task. A runtime
error is not a model answer. Preserve all original records and unknown wall-time
components, and continue only never-executed work after offline qualification.

### Source-local access order is a retrieval reliability boundary

A neighbor or query-head lookup already knows the nominated source. Seek that
source through the existing ordered-range index, then join only its generation
members, lifecycle and raw-state views. Do not let the optimizer enumerate all
generation ranges before applying the source predicate. The existing atomic
bundle lookup already uses this source-first pattern; reuse it for the two
ordinary retrieval lookups rather than introduce another cache or derived store.
Retain the same selected fields, ordinal/offset ordering and active/view filters.

Require differential result tests, explicit query-plan inspection and a bounded
VM-work regression fixture with unrelated sources. These are SQL correctness and
access-path checks, not efficacy evidence. Retain timeout outcomes unchanged;
profile saved queries outside scored measurement and freeze a new installed
candidate before attributing fewer timeouts, lower latency or higher task success
to this correction. Never extend the timeout or remove governance to conceal an
unbounded access path. This does not replace the separate indexed-vector task.

### Initial source-state assessment, not just follow-up assessment

The current optional classifier is attached to investigative search results.
That leaves the first reader packet unassessed when the native agent decides it
already has enough context. Add a separately selected product-owned initial
source-state profile. It must run before the first packet is returned, independent
of whether the agent later searches. This is an explicit experiment, not an
accepted quality improvement or a change to deterministic defaults.

Reuse the existing exact-quote source-state contract and provider boundary. Supply
only the canonical units already selected and authorized for the initial package;
do not introduce evaluator facts or silently truncate the unit list. Bound initial
assessment to 256 units and 80,000 serialized input bytes, original source context
to its existing 32,000-byte bound, interpretation to 6,000 bytes and the composed
profile to 40,000 bytes. Follow-up assessment retains its existing smaller bounds.
The interpretation emphasizes complementary source quotations, qualifications,
exclusions and query-time applicability; it does not generate an answer or approve
an application action. Actual token/latency overhead is measured, not assumed free.
Preserve source/part grouping metadata so the classifier can associate a dated
introductory unit with related quotations; do not treat a flattened list of
unlabelled fragments as a coherent chronological history. The larger input bound
is initial-profile-only; follow-up input retains its existing 50,000-byte bound.

Remote initial assessment needs an application-owned provider and explicit trusted
egress selection, never a model/body-controlled switch. Audit authorization before
egress. Recheck generation, scope, lifecycle and original bytes after the provider
returns and revalidate the binding before disclosure. Keep the original V3 package
and sufficiency determination intact; render the optional interpretation separately
alongside all its original source context. Issue a distinct preparation/exposure
receipt linking back to the original preparation and exact composed bytes.

Unavailable, malformed or over-budget interpretation produces an explicit
not-assessed notice with the unchanged authorized source packet, not another
provider call or an invented assessment. Revoked/stale source or binding authority
is terminal and must not disclose the original packet as a fallback. Independently
test initial invocation, denied egress, unsupported quotations, provider failure,
late revocation, byte bounds, unchanged sources and unchanged default behavior.

### Separately selected source dossier presentation

Do not equate additional state labels with useful evidence assembly. A second,
separately selected profile may replace the initial source presentation with a
bounded dossier of exact original quotations organized by model-proposed
information needs. This is presentation over existing authorized sources, not
source pruning, generated memory facts, canonical reconciliation or action approval.
Original records remain intact and available through the existing read-only
inspection tool, and the original preparation remains linked in the audit.

AtBot proposes at most eight information needs with at most two exact source
quotations each and four unresolved needs. AtMem independently validates every
identifier, quote, bound and live authorization, adds canonical source/part
references, and records precisely the delivered unit IDs and bytes. Need labels
are model proposals, not factual assertions. The dossier explicitly reports
investigative evidence and sufficiency not assessed; it must not inherit the
original V3 package's semantic-sufficiency claim for its smaller selection.

Use a distinct recognized SDK profile with a 16,000-byte bound. No silent source
truncation or quote rewriting is permitted. An empty, invalid, unavailable or
over-budget proposal returns the unchanged authorized source packet under the
existing 40,000-byte initial-profile fallback, visibly marked not assessed.
Revocation remains terminal. This profile requires the same explicit provider
and remote-egress selection, without enabling any new default behavior.

Evaluate complete fixed conditions, not per-task mixtures of their best answers.
Keep the annotation-only trial separate. Measure first-packet bytes, total reader
tokens, latency, task success, regressions and inspection work: a smaller first
packet does not establish lower total token usage or maintained task quality.

### Separate reader-capability diagnostic

Do not assume every failure remaining with relevant original evidence is a
retrieval defect. A separately selected reader model may test interpretation and
application-execution limits before another memory rewrite. Preserve the native
agent loop, original request, app tools, source snapshot and matched host policy.
Record the actual provider model family and reasoning effort on every request;
do not silently alias, fall back to paid API, or credit a reader change to memory.
Availability is established by a benign non-benchmark probe before scored dispatch.
Matched comparator and candidate runs use the same selected reader. Earlier
conditions remain distinct; no per-task best-model selection is permitted. This
does not change product defaults, accept any pillar or unlock the full campaign.
