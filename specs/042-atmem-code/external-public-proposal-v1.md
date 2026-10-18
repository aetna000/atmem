# Public proposal byte-equivalence — prospective v1

The first qualified source control captured 82 files, while its verified public
Git base contains 76. The six image-only files must not enter the solver input,
but their absence from a public proposal must not be misclassified as deletion.

Implement `governed_public_proposal` as a wrapper around the existing source-only
assembler: compare candidate bytes with the verified PUBLIC original, preserve
frozen image-only runtime files, refuse collisions with those paths, and continue
to ignore candidate test edits and reject out-of-scope changes. Verify public
original bytes against the frozen pre-test base before assembly. No changes to
historical controls, upstream tests, parser or grading.

Run one evaluator-side byte-equivalence check using the protected, retained
unchanged and reference-as-proposal snapshots from the completed source control.
Project the reference proposal onto the 76 public base paths; no model sees this
projection. Require unchanged public assembly to match the previously qualified
parent assembly digest, and projected reference assembly to match the previously
qualified reference assembly digest. Require all image-only bytes preserved.

Retain the plan, actual wrapper source, input provenance and exact reconstructed
bytes in protected evidence before/after this check. No container, new upstream
test, model call, replacement task or score recomputation. Matching source bytes
is not a new test pass or a model efficacy result. Actual solver lifecycle,
public test execution and final candidate-worker integration remain open.
