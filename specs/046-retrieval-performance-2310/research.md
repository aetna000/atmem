# Corpus qualification research — 2026-10-21

Initial structural screening used remote metadata. Subsequently, bounded pinned
source downloads were stored on MEM: RHELM 38,730,154 bytes and REALTALK 3,313,725
bytes, with Git-blob verification and SHA-256 receipts. No new paid model calls.
Corpus-wide semantic/privacy/egress and redistribution qualification remains
incomplete; no confirmation or full benchmark dispatch is approved.

| Corpus | Immutable source commit | Inspected structure | Role / constraint |
| --- | --- | --- | --- |
| microsoft/RHELM | `5e170da7a2db96b4d222620a2aaaddb031cb8098` | 1,305 QA, 10 persona files, no empty supporting-evidence lists | Generated published stress evaluation; not authentic production conversations |
| danny911kr/REALTALK | `48b3ab884a34baf659243d3188df478dd401a70a` | 728 QA, 10 conversation files, two empty evidence lists; conversation JSON totals 3,295,494 bytes | Human-conversation transfer; missing evidence quarantined pending adjudication |
| bowen-upenn/PersonaMem-v3 | `ad80a3b1b322129fb0585ead33b129a87bb4e387` | Code MIT; published data card CC-BY-NC-4.0 | Conditional; generated worlds grounded in behavioral signals, not raw production chats |

RHELM categories observed by structural counting: fact 207, aggregation 192,
temporal 185, attachment 249, mixed 210, hallucination 197, misleading 65.
The repository contains about 51.5 MB of blobs; no full checkout is needed.
References existing is not proof that referenced evidence resolves or supports
the answer. Actual source-reference and temporal validation is still required.

REALTALK observed numeric categories: 1:301, 2:319, 3:108. Map meanings from pinned
evaluation code before reporting category scores. Entire repository blobs total
about 635 MB; raw spreadsheets and duplicated LoCoMo files are unnecessary for
the initial QA adapter. Exclude `data/locomo/` from this campaign.

Repositories contain MIT (RHELM) and Apache-2.0 (REALTALK) license files. Review
data-specific notices, human-data privacy/consent, approved external processing and
redistribution separately before egress/public upload; a code license alone is
not a blanket authorization for every data use.

## Prior content exposure

- REALTALK `data/Chat_1_Emi_Elise.json`: beginning of QA inspected for quality;
  reserve its full participant/evidence connected component for development.
- RHELM `data/QA_final/low_score_qa_David_Reyes_all_validated.jsonl`:
  first question `fact_67f4ee` inspected; its persona cluster is development-only.
- Counts/schema only inspected for remaining QA during screening; no further
  answer text printed. Public data may have model pretraining exposure.

## Quality rubric before inclusion

Require original unmodified conversation, source-resolvable support, unambiguous
answer at query time, memory dependence and a matching pillar. Record exclusions
before candidate scores. Preserve ambiguous/missing-evidence examples as excluded
records, not silently repaired labels. No generated replacement conversations.
Do not add fabricated tool actions to a QA benchmark and call them official tasks.

REALTALK recurring filenames suggest connected participant groups: Emi/Elise/
Kevin/Paola; Nicolas/Nebraas/Vanessa; Akib/Fahim/Muhhamed. Verify identities from
the data; do not assume anonymized names map perfectly. Limited independent
groups constrain statistical claims and the number of fresh confirmation shards.

## Primary sources

- [RHELM repository](https://github.com/microsoft/RHELM/tree/5e170da7a2db96b4d222620a2aaaddb031cb8098)
- [RHELM construction paper](https://arxiv.org/html/2605.31086v1)
- [REALTALK repository](https://github.com/danny911kr/REALTALK/tree/48b3ab884a34baf659243d3188df478dd401a70a)
- [PersonaMem-v3 data card](https://huggingface.co/datasets/bowen-upenn/PersonaMem-v3)
- [DolphinBench provenance](https://huggingface.co/datasets/mem0ai/dolphinbench)

## Initial compatibility findings

040 already requires bounded navigation, source-backed sufficiency and optional
model proposals: reuse/extend these rather than claim they never existed.
040 FR-014 disallows similarity/confidence as proof of sufficiency. The semantic
checker therefore proposes needs/ranges, with governed validation.
040 historical sample/hardware prescriptions do not silently become this new
campaign's requirements. Preserve them as historical evidence.
044 FR-005 retains native tools: adding AtMem search cannot disable unrelated
agent tools. 044's USD 6 coding budget is independent of this USD 250 campaign.
045 is missing in this worktree, but its uncommitted specification was read in
the separate learning worktree. Its reviewed SHA-256 is
`10cc2a51cc49a7885d93e7ac1b84f337d90a82455d648cb35169b065a993785b`.
It owns checked-lesson promotion; 046 does not implement or replace that scope.
Recheck that digest/source alignment before merge; global review is still pending.

## Completed development characterization

Execution artifacts are kept in ignored/private storage. These are inspected conversation probes,
not independent confirmation or a completed pillar acceptance decision.

- RHELM structural v2: 1,296 resolvable records, 3 future-evidence references,
  1 unresolved conversation reference and 5 unresolved external references.
  Existence checks do not establish answer support.
- REALTALK structural v2: 655 reference-resolvable records, 2 missing-reference
  records and 71 unresolved records. Explicit list/range normalization accounts
  for the improvement over the retained first structural report.
- Chat_1 source aliases need conversation evidence: the speaker labelled Emi
  explicitly introduces herself as Kate. A label/QA-name mismatch alone is not
  an annotation error. Annotated evidence lists may omit alias-linking context
  and are not a proven necessary-and-sufficient evidence set.
- The approximate index lost relevant exact-vector neighbours. A native exact
  vector diagnostic identifies that loss, but is not an accepted scalable index.
- Ninety QA reader requests completed through the existing subscription with no
  paid fallback, no transport errors and complete usage receipts. Independent
  correctness grading remains outstanding. No Mem0 superiority is inferred.
