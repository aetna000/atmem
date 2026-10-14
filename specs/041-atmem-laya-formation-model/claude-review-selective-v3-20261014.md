# Claude read-only review: selective single-call V3

Date: 2026-10-14  
Reviewer: Claude Code CLI, Sonnet, medium effort  
Mode: read-only (`Read`, `Grep`, and `Glob` only; editing and shell tools denied)

## Findings returned

1. **Critical — conflicting live requirements.** FR-006b/FR-006c still
   normatively required the rejected sequential Noul/Choice/Score plan while
   FR-040 required one joint Choice call.
2. **High — weak-supervision claim wording.** SC-010/T082 omitted the mandatory
   machine-weak-supervision label already present for the same sealed evidence
   in SC-009/T072.
3. **High — joint option cardinality.** Four relational operations crossed with
   targets could exceed Choice's 255-option ceiling because the V3 amendment
   did not cap targets or define option-overflow handling.
4. **Medium — train/serve parity.** V3 tasks did not explicitly require the
   byte-identical runtime/training packer fixtures required for the earlier
   contract.
5. **Medium — compute ceiling ambiguity.** The USD 8 Vast and USD 11 Hugging
   Face ceilings did not state whether they were cumulative across Spec 041 or
   renewed for V3.
6. **Low — model publication lineage.** The publication tasks did not define a
   V3 repository/revision policy or require the rejected V2 card to be marked
   superseded.

Claude found the authority boundary, selective routing invariant, authentic
data requirements and leakage-task coverage consistent.

## Remediation applied after review

- FR-006b is explicitly superseded research behavior; FR-006c names the V3
  single response.
- SC-010 and T082 require machine-weak-supervision wording unless the entire
  sealed set receives independent exact-contract human annotation.
- FR-040 caps authorized targets at 32, requires a final option count no greater
  than 255 and sends unrepresentable required targets to review without a model
  call.
- FR-046/T075 require byte-identical candidate/alias/option/serialization/token/
  overflow train-serve fixtures.
- FR-022/T079 define the provider ceilings as cumulative and require ledger
  reconciliation before another instance is launched.
- T083 defines separate V3 lineage and requires a rejected/superseded notice on
  the V2 model card.

## Additional maintainer correction

Claude reported no release-version issue from the supplied specification, but
the repository contains the immutable published `v2.3.9b1` tag. The target was
therefore corrected to a new post-`2.3.9b1` beta selected only after the V3 gate;
the existing tag must not move or be represented as containing V3.
