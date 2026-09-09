# Memory extraction and updating

Turning what someone said into what an agent remembers is the step where
memory quality and memory safety are decided. AtMem separates the two roles
that step involves: intelligence may *propose*, AtMem alone *validates and
commits*. A proposer — the deterministic rule extractor or an AtBot model —
never writes to canonical storage and never sees a candidate outside its
authority scope.

Every observation produces exactly one typed outcome. There is no silent add
and no silent drop.

## The five outcomes

| Action | Meaning |
| --- | --- |
| `ADD` | A new fact, with no current value in the same slot. |
| `UPDATE` | The current value is refined — the old wording is contained in the new one. |
| `SUPERSEDE` | The current value is contradicted or explicitly corrected. |
| `NOOP` | Nothing to change: a duplicate of an active record, or no extractable claim. |
| `REJECT` | The content must not become memory: refused by policy, unsupported by its source, or built on ambiguous evidence. |

Each outcome also carries a memory class — `durable_fact`, `temporary_state`,
`episode`, `procedure`, or `non_memory` — read from the words actually used.
"My focus right now is the invoice migration" is temporary state, not a durable
fact, and non-durable classes wait for review before they are admitted.

## Evidence is exact, not approximate

Every proposal cites a source span: a `source_id`, the digest of the whole
source, byte offsets into it, and the digest of the excerpt at those offsets.
Validation re-derives all three. A proposal whose offsets or digests do not
reproduce the claimed excerpt is invalid — including one that was valid when
written and was edited afterwards.

A model claim the source does not support is refused with
`unsupported_by_source` rather than admitted on the model's say-so.

## Resolution is bounded and receipted

Pronoun and entity resolution reads a configured recent window of episodes
plus lifecycle-eligible active memory for one subject, filtered to the calling
authority scope. It cannot widen that window to resolve something, and it
records which evidence influenced the answer.

When the bounded evidence names two candidates, resolution reports
`ambiguous_referent` and the proposal waits for a person. It does not guess.

## What waits for review

`ReviewPolicy` decides admission by data rather than by code path. By default a
proposal is quarantined when it is low-confidence, sensitive, ambiguous,
non-durable, or destructive — where destructive means one proposal would retire
several current facts at once. Untrusted sources always require review; a
webpage can never produce an unreviewed mutation.

Reviewers approve, edit-and-approve, or reject. Every decision records the
actor, the time, the reason, and the resulting record ids in the hash-linked
audit log. The CLI and the dashboard call one service, so the queue, the
evidence, and the allowed actions are identical in both.

```bash
atmem proposals queue memories.db --subject user-1
atmem proposals show memories.db PROPOSAL_ID
atmem proposals decide memories.db PROPOSAL_ID approve --actor you@example.com \
    --reason "confirmed with the user"
atmem proposals lineage memories.db user-1
```

`edit_and_approve` stores the reviewer's wording, not the proposed wording, and
records a digest of what they wrote.

## Corrections keep history

A correction does not overwrite. The replacing record becomes active, the
replaced record becomes `superseded`, and a row in `memory_lineage` records the
relationship — `corrects`, `supersedes`, or `refines` — together with the
predecessor's content digest and generation. Lineage rows are immutable: a
database trigger aborts any update to one. Verifiable deletion may purge them;
nothing may rewrite them.

The result is one unambiguous current value with a complete, evidence-linked
history behind it.

## Concurrency: proposals fail closed

Every mutating proposal pins preconditions — record id, generation, status, and
content digest — for each record it would change. Records carry a `generation`
that a database trigger advances on any update that does not set it explicitly.

If the targeted memory changes between building a proposal and committing it,
the commit is refused with `stale_proposal_generation` and the older value is
left untouched. The same check runs again at review time, so a decision made
against a value that has since moved reports `stale` and commits nothing.

Two reviewers deciding the same proposal produce one decision: the store
settles it under a pending-only guard and the second decision is refused.

Resubmitting an identical proposal replays the original decision rather than
committing twice. Reusing an idempotency key with a different payload is an
error.

## Hostile and excluded content

Instructions, prompt injection, secrets, and "do not remember" signals are
detected before admission, and the content stays data:

- **Instruction-shaped content** is refused from untrusted sources. A trusted
  user turn is treated differently on purpose: "you must always use metric
  units" from the user is a preference, while the same sentence arriving inside
  a fetched webpage is an injection attempt.
- **Secret material** — private keys, API keys, credentials — is refused from
  every source, including the user.
- **Explicit exclusion** — "don't remember this", "off the record" — is honored
  from every source.

Refusals are recorded as audit events with reason codes and a digest of the
refused message; the content itself is not stored. AtBot applies the same
screen locally so hostile content never leaves the companion, but AtBot's
screening is a courtesy, not the boundary — AtMem re-screens everything.

## Deterministic fallback

The rule extractor is the fallback, and it is always available. When AtBot is
absent, times out, or returns malformed output, extraction still produces typed
outcomes with stable reason codes. Pass `fallback_reason` to record *why* the
deterministic path was used, so a run that silently degraded is distinguishable
from one that was always local.

Malformed model rows become `REJECT` with `malformed_model_output`. They never
widen what a proposer may change.

## Schema changes and rollback

The proposal, review, and lineage tables are added by the reserved bootstrap
migrations `0060`–`0063` (see `specs/integration-ownership.md`). They are
append-only: identifiers are never renumbered, reused, or replayed.

`tests/test_extract_upgrade.py` runs against real databases written by each
supported published version, kept in `tests/fixtures/upgrades/` with a digest
manifest. For every floor it proves that the upgrade preserves memory and the
audit chain, that an interrupted upgrade recovers forward on the next open
rather than needing repair, and that the schema stays readable by the version a
user would roll back to — no column changed shape, and the inserts the older
code issues still succeed.

## Limitations

- Classification is deterministic and pattern-based. It reads the sentence
  shapes people actually use; it does not understand domain vocabulary, and a
  statement it cannot parse produces `NOOP`, not a guess.
- Refinement detection treats a candidate as a refinement only when it contains
  the current value's words in order. Rewordings that mean the same thing are
  treated as contradictions and supersede instead.
- Resolution handles third-person pronouns and recent fact slots. It does not
  perform coreference across a long conversation, and it deliberately fails to
  ambiguity rather than reaching for more context.
- Evidence digests are re-derived at submission, while the raw source text is
  still in hand. AtMem does not retain that text on the proposal row, so review
  re-checks the targeted records rather than the source excerpt.
- Confidence is extractor confidence. It gates review; it never influences
  ranking, trust, or promotion.
