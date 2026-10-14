# Authentic conversation training policy

This policy is a blocking contract for the replacement AtMem Laya memory
understanding model.

## Eligible conversation content

Every training conversation must be a source-licensed record of an actual
human–AI interaction with human-authored user turns. Assistant turns may be
model responses from that interaction; they are context and never independent
proof of a user fact. Controlled human studies are eligible when their
collection method and license are recorded. Production-origin public
conversation is eligible only after privacy, license and provenance gates pass.

The following conversation content is ineligible:

- generated or simulated dialogue, including LoCoMo;
- model-generated continuations added to an authentic conversation;
- synthetic or hand-authored scenarios and paraphrases;
- translations created to fill a language quota;
- private AtMem/OpenClaw user histories; and
- benchmark questions, answers or evaluation conversations.

Machine labels do not change source authenticity. Codex CLI and Claude CLI may
attach dispositions, structured meaning, evidence links, uncertainty and audit
reasons to eligible source rows. Those fields are weak-supervision annotations,
not human ground truth and not replacement conversation text.

## Understanding target

The model proposes a structured interpretation and state transition, not a text
dump. Each accepted label contains:

- outer disposition: `STORE`, `UPDATE`, `DUPLICATE`, `DO_NOT_STORE`, `FORGET`
  or `REVIEW`;
- memory class and durable normalized meaning in the original language;
- subject/entity, predicate or intent type, value and applicable scope;
- temporal validity and durability;
- exact supporting source turns;
- relation to earlier understanding: adds, refines, contradicts, supersedes,
  repeats or removes; and
- calibrated uncertainty and review need.

AtMem independently validates evidence, scope, policy and target identity before
it may apply the proposal to canonical memory. Earlier states and their source
provenance remain auditable when understanding evolves.

## Required final-manifest gates

Training and publication must reject a corpus unless its immutable manifest
proves all of the following:

1. target 100,000 accepted authentic-conversation rows; never fewer than 20,000,
   with the exact achieved count and evidence-bound stop reason recorded;
2. zero generated, translated, synthetic or hand-authored conversation rows;
3. the frozen final language allocation;
4. global exact and multilingual semantic duplicate clustering before splits;
5. a complete Codex first pass and, unless authenticated CLI allowance is
   exhausted, an independent Claude first pass; the exact labeling mode is public;
6. completed self-review passes for duplicate clusters, same-scope chronology,
   strata and contradiction/outlier searches;
7. frozen judge histories before cross-judge comparison;
8. resolved agreement/adjudication status for every accepted row; and
9. source, license, privacy, leakage, schema and digest validation.

The earlier `atmem/atmem-laya-formation-v1` dataset and
`atmem/atmem-laya-formation-model-v1` checkpoint fail this policy because their
conversation content was synthetic. They are permanently superseded for this
feature and cannot satisfy a dataset, model, release or benchmark gate.
