# Data Model: AtMem Context Engine

## Canonical entities

### SourceEpisode

- `episode_id`, `scope`, `agent/session/run/turn`, actor and timestamps
- ordered `SourcePart` references
- lifecycle and retention identity
- source digest and immutable generation

### SourcePart

- stable `part_id`, ordinal, media kind and content/reference identity
- original protected bytes or text retained once
- source offsets/coordinates and integrity digest

### EvidenceViewGeneration

- profile/version, producer/model identity, source generation and policy digest
- state: building, shadow, active, stale, failed, retired
- category storage accounting and completeness receipt

### EvidenceUnit

- stable `unit_id`, kind and compact kind payload
- one or more exact `EvidenceRange` links
- authority/lifecycle inherited from source and independently revalidated
- searchable projection; never an independent source of truth

Kinds: `raw_state`, `state_transition`, `atomic_fact`, `entity_link`,
`procedure`, `durable_rule`, `failure_gotcha`, `premise_constraint`.

`raw_state` includes a reserved `source episode` / `source statement` schema
whose value is one exact sentence or bounded clause and whose evidence range
is the identical immutable-source substring. Schema labels are structural, not
claims that those words appeared in the source. These units make individual
requirements independently retrievable and removable without duplicating
canonical authority.

### HistoryImportReviewReceipt

- proposal, source, subject, agent and workspace identity
- configured operator principal and assurance
- frozen `history_import:review` authorization identity
- additional `procedure:review` authorization for action-bearing units
- imported source identity, granularity and audit event; pending semantic or
  action proposals retain their ordinary single-use review receipts
- no evaluator requirement, answer, task or grader fields

### FormationCoverage

- source-region inventory
- represented/rejected/unsupported regions and reason codes
- proposal/admission counts by kind
- unsupported media/tool surface
- processing and representation completeness as separate fields

## Query entities

### EvidenceObligation

- entity/surface, relation/action, requested value/form
- polarity, temporal target and applicability condition
- ordered-step or comparison-side identity
- required/optional and satisfaction rule

### QueryPlan

- plan/profile identity and original-query digest
- obligations plus per-view queries/limits
- planner/model identity and fallback state

### RetrievalManifest

- authorized trajectory/source summaries and counts
- no source bodies beyond the declared compact manifest budget
- canonical generation and scope binding

### NavigationReceipt

- searched views, inspected source ranges and followed links
- submitted ranges, operation/byte/time usage and exhaustion
- model/provider identity when applicable

### SufficiencyDecisionV2

- `sufficient`: every required obligation has current source-backed support
- `partial`: some required obligations are covered and some remain open
- `conflicted`: authorized current evidence supports incompatible values
- `contradicted`: positive evidence establishes that the query premise is false
- `stale`: matching evidence exists but is not current for the requested time
- `not_found_within_budget`: declared views were searched to the recorded limit;
  this is not proof that the evidence or fact does not exist
- `withheld_by_policy`: relevant evidence cannot be disclosed under current
  authority
- obligation coverage and missing/contradicting evidence
- canonical source/record identities and reason codes

### ContextPackageV3

- bounded serialized evidence and media references
- selected units/ranges in reader order
- sufficiency, action constraints and exclusions
- total-input accounting, generation, expiry and audit identity

## Lifecycle rules

1. Canonical source admission precedes all view construction.
2. A view generation is invisible until its coverage/integrity checks pass.
3. Activation atomically switches the derived profile pointer; canonical source
   and governance state do not migrate or change authority.
4. Source lifecycle changes invalidate affected units, manifests, caches and
   prepared packages before subsequent delivery.
5. Retired derived generations remain available only for bounded comparison;
   rollback rebuilds the legacy derived state from current canonical source and
   lifecycle state before it may serve traffic.
6. FTS indexes use contentless/external-content storage. Vector indexes are
   encrypted under the household key/profile and are included in storage
   amplification and stolen-store tests.
7. Sentence-granularity source observations are opt-in. Automated settlement
   additionally requires host-asserted binding and a configured, scope-bound
   history-import principal; otherwise observations remain in review.
