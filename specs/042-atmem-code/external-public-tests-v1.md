# Public development-test execution — prospective v1

Qualify only the first fixed Marshmallow task, pinned image and verified
76-file public base. Zero model calls, no hints/problem statement/reference or
hidden test input. This is not a scored task repair or a product candidate.

Fresh containers receive a new, exact allowlisted public request: public base,
base modes, candidate bytes and constrained pytest options. Never forward an
evaluator envelope or provider credentials. Use existing no-network/no-mount,
cap-drop/no-new-privileges, 1 CPU/1 GiB/128 PID, 64 MiB tmpfs, 8 GiB host-free
guard, 180-second outer controller and bounded-output/cleanup behavior. No pull.

Verify source against the pinned image Git blobs and current base bytes. Allow
only the six original package egg-info metadata files as image-only repository
artifacts. Verify a standalone /testbed/.git and no external Git object alternates.
Remove ONLY that exact disposable container-overlay Git directory before running
any repository code. The cached image and owner filesystem are untouched.
Refuse known evaluator artifacts. Materialize the candidate under fresh /work
using the existing source writer and executable modes; use /work/src imports.
The old /testbed source/runtime metadata and installed dependencies remain
available, but its target Git object store is absent. No claim about arbitrary
other dependency/package knowledge or public pretraining decontamination.

Development pytest may use candidate tests. Hidden grading NEVER uses them.
Disable ambient plugin/user-site/addopts inheritance; execute fixed Python
pytest argv, no host shell or user-selected image/command/environment. Public
test runs are capped at 120 seconds/4 MB output with partial-output retention;
timeout/truncation/cleanup errors fail qualification, not silently retry.

Fixed sequence: three trusted isolation-fixture checks first (candidate-source
import, no target Git/evaluator directory, actual host-canary read refusal and
external-network refusal), then the unchanged project's full public tests.
The second phase is withheld if the isolation phase fails. The probe is only
plumbing evidence, never training data or a real-task quality result. Public
test execution requires actual nonzero passed-test output and clean exit.

Retain exact requests, code, argv, output, source digest and failure before/after
each dispatch in protected evidence. No mid-run code/policy change or task swap.
This qualifies public test execution only, not a live agent, current-workspace
atomicity, final candidate grading, usage, AtMem efficacy or another task.
