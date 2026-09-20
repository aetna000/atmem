# Implementation plan

## Context

Python CLI and stdlib HTTP dashboard; AtFlows is a separate Bun-backed Python package. Preserve separate data stores and existing delegated-auth contract. No new dependency.

## Design

1. Keep a private AtMem-managed process record keyed by AtFlows instance ID; detect independent processes read-only. Start/restart only owned instances and report real loopback ports.
2. Make init resumable for fresh and existing homes, and report each component independently. Status compares installed vs running versions and bridge metadata.
3. Expose a sanitized, running loopback AtFlows URL to authenticated AtMem UI; hide link otherwise. Align header mark/wordmark to website reference.
4. Keep release docs honest about 2.3.4; prepare new version notes only after gates and reviewed release scope.

## Verification

Fresh/upgrade isolated CLI tests, external-process test, URL-validation/UI test, full Python suite, package build, companion/OpenClaw tests, installed-artifact smoke. Publication follows AGENTS.md and is not part of spec completion.
