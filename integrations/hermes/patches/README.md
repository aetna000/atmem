# Hermes final tool-policy boundary candidate

This is a tested local host fix for Spec 050, not a Hermes upstream release or
an enabled AtMem rule system. The owner runtime has not been patched.

- Base: `d0288be5b3330d2442e3907185b8e9d0958297bb`.
- Candidate: `1088e06e448bef2af736122a5d424082a57bf548`.
- Upstream source: <https://github.com/NousResearch/hermes-agent>.
- Branch: `fix/final-tool-policy-boundary` in the separate local host worktree.
- Patch digest, source hashes, environment and results: `final-tool-policy-boundary.json`.
- License: upstream MIT, reproduced in `LICENSE.hermes`; the patch retains its
  author/commit metadata.

The patch blocks outer pre-tool dispatch failures and adds a read-only
`authorize_tool_call` hook at the last instrumented dispatch boundaries. It
checks detached final arguments after transformations, supports vetoes without
overriding existing vetoes, and blocks callback/dispatcher failures, timeouts,
modifying decisions and input mutation. Errors remain ordinary tool results so
a run can retry after recovery. It does not require a model or paid service.

The new callback is idempotent and may be checked again as a wrapper resolves.
It is not a transaction, nonce consumer, memory authority or human-approval
issuer. AtMem still needs the rule/evidence service and installed-host acceptance
before any rule activation. Legacy transform hooks retain their behavior and
must migrate exact-argument policy decisions to the final hook.

## Review and reproduce in a separate checkout

Apply only on a clean branch based on the pinned base, never blindly over a
different installed version. The mail patch includes tests and documentation.

```sh
git apply --check /absolute/path/to/0001-final-tool-policy-boundary.patch
git am /absolute/path/to/0001-final-tool-policy-boundary.patch
```

Use Hermes PM to prepare the isolated test environment, following that
checkout's AGENTS.md. Run its canonical test runner:

```sh
HERMES_PYTHON=/absolute/path/to/test-environment/bin/python scripts/run_tests.sh -j 2 \
  tests/agent/test_final_tool_authorization.py \
  tests/agent/test_run_agent.py \
  tests/agent/test_tool_executor_checkpoint_paths.py \
  tests/tools/test_model_tools.py \
  tests/tools/test_connector_dispatch_policy.py \
  tests/tools/test_connector_bridge_wiring.py \
  tests/hermes_cli/test_plugins.py --tb=short
```

Observed: 467 passed on macOS / Python 3.14.7. Forty cases use real plugin
directory discovery and instrumented host dispatch with temporary local effects,
covering direct, agent, connector and connector-batch calls, rewrites, nested
argument mutation, errors, timeouts and recovery. The connector transport is a
local test double; no real remote action or model call occurs. The unfixed
dispatch implementations fail the error and rewritten-argument cases.

Windows/Linux, deployment, production capability registration, approval replay,
source-deletion races and efficacy are not certified by this patch. Do not
invoke Hermes under a fresh temporary `HERMES_HOME` as a shortcut: bootstrap can
rewrite global launchers. The canonical runner isolates the test state.
