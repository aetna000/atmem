# Local dashboard usability validation — 2026-09-09

Scope: Spec 022 FR-012–FR-016 / SC-006, and existing Spec 020 Black Box
projection/diagnostic amendments. This is a local working-tree improvement to
the four-tab dashboard, not a release or completion of the wider workspace plan.

## Changes

- Separate observed task completion from recording quality. Preserve underlying
  verdicts, conflicts and signed historical events. Show confirmed tool errors
  in red and missing/conflicting observations in amber.
- Identify the supported OpenClaw skill-review run/session convention as
  background work. Keep foreground status primary and offer an explicit toggle.
- Group conflicting observations by call, with time, agent, tool and links to
  each affected event. Collapse long IDs and hashes.
- Poll an inexpensive scoped revision every three seconds while visible; reload
  changed evidence, preserve inspected event expansion/scroll, and show reconnect
  status on failure. The existing host hooks supply events; no completion is
  synthesized from text or elapsed time.
- Bound initial run pages to 50. Defer optional stories and bridge inspection;
  avoid verifying the same story twice in one HTTP request.
- Move system health to Settings, collapse advanced configuration/recovery
  controls and the memory assistant, and wrap narrow-screen archive controls.
- Treat initial status loading as unknown, never a transient outage.

## Validation

Python gate:

```sh
.venv/bin/python -m pytest tests/test_blackbox.py tests/test_control_plane.py -q
```

73 tests passed, including local HTTP, revision metadata, persisted reports and
background/foreground projection checks. Local HTTP tests require permission to
bind a loopback test server.

JavaScript gate:

```sh
node --check atmem/control/assets/app.js
node integrations/openclaw/test/blackbox-diagnostics.mjs
```

Checks cover actual error reasons, missing-reason fallback, grouped conflicts,
completed outcomes, unknown response coverage, and background separation.

Browser gate (optional isolated Playwright installation):

```sh
ATMEM_PLAYWRIGHT_MODULE=/tmp/atmem-ui-validation/node_modules/playwright/index.mjs \
  node integrations/openclaw/test/dashboard-live.mjs
```

The default preview URL is http://127.0.0.1:8799/; override with
`ATMEM_DASHBOARD_URL`. Browser fixtures intercept read-only run APIs and do not
write synthetic evidence into the user's store. Cases cover delayed initial
status, automatic in-progress-to-complete updates, preserved open events, no
index reload on unchanged revisions, disconnect/reconnect, grouped conflict
links, background toggling, collapsed IDs, and all four routes at 390px width.
Desktop inspection used 1440px width.

A local overview check observed 2.364 seconds to the completed-run indicator
after the loading changes, versus 4.444 seconds in an earlier iteration. These
are individual local observations, not a controlled or published performance
benchmark.

## Limits

No fresh real-agent task or new OpenClaw lifecycle conformance is claimed by
these browser fixtures. Existing missing completion and conflicting historical
records remain unresolved evidence; display improvements do not repair them.
Background classification is limited to the known host convention and is not
a new authentication boundary. The revision response is a refresh hint, not
chain verification. No broader human usability study was performed.
