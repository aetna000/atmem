# Selected-task public runtime binding controls

For each of the four newly source/proposal-qualified tasks, run one explicit
public-runtime plumbing probe using the configured public-test worker and its
verified public source snapshot. Bind the exact task/base/image and exact
image-only artifact digests from prior unchanged captures; keep import-layout
and Requests cache projection operator-controlled. No private evaluator
material is passed to this worker.

The probe adds `tests/test_atmem_public_runtime_control.py` solely for this
zero-model environment control. It checks that the task's public package is
actually imported from `/work/src` (Marshmallow) or `/work` (Requests/Astroid),
that the original Git object store was removed, and that no private evaluator
directory is present. Run only this explicit probe. It is an authored harness
fixture, not an upstream task test, training example or repair-quality result.

Verify exact tested candidate digest, completed test output, full output
retention, removed Git store and absence of evaluator material. Keep the
existing network-none/no-owner-mount/controller and test limits. Retain any
failed attempt without replacement, truncation concealment or favorable retry.
Use at most two concurrent workers and record bootstrap, request, fixture,
candidate digests, image/configuration and full raw streams prospectively.

Passing these probes qualifies import/source binding only. It does not claim
all original public tests pass, that optional dependencies are present, that
the common MCP service has been exercised for every task, or that AtMem saves
tokens. Upstream private grades remain the repair-quality authority.
