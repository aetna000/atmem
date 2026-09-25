# Public retail no-fault qualification

Workload: Sierra Research tau2-bench retail, commit
`b7ea9074c1cba482b30687fecdb5c8425fd6f619`, public development task 0.
The four compressed JSON files retain native public tool responses, environment
states and conversations. Upstream MIT notice is included.

The model cassette is the preserved actual native run in
`../pilot-usd20-20260925/native-task0-001/`. These are recorded real provider
responses, not fabricated responses. Replaying them verifies identical native
requests; it does not constitute four new autonomous task evaluations.

All four arms matched 18 requests, six tool calls, conversation and final state.
The original native task reward was zero; parity does not change or improve that
score. It shows the product integration does not alter this no-fault run.

`atflows-observed.json` was read from the actual authenticated observer API after
the run: 24 received tool-attempt events across 12 attempts. All 12 have missing
prices. No evaluator budget cost was inserted into the product to fill that gap.

Product artifacts were development builds, not newly published 2.3.7b2/0.1.2
releases. Exact build-003 wheel hashes are in
`../product-acceptance-20260925-003/summary.json`. Later source corrections require
their own installed gates; do not treat this bundle as proof of later code.
