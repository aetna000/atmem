# Troubleshooting

## No memory reaches the model
Check shadow versus active mode, authenticated scope, record lifecycle, support
checks and provider registration. Memory search can find a record without authorizing
injection. Inspect the recorded decision and exact delivery confirmation.

## A valid local bearer credential is required
The service is reachable but the supplied credential was missing or invalid.
Dashboard local-account sessions and API credentials are distinct.
Do not solve this by disabling authentication or exposing the loopback service.
Read [HTTP authentication](../http-api.md).

## Cannot see exact text or media
Check [your evidence role](evidence.md) and capture coverage. Viewer access is
intentionally metadata-only. An uncaptured original cannot be recovered from hashes.
Supported OpenClaw capture does not imply every host exposes the same media bytes.

## Companion or model unavailable
Review [AtBot setup](atbot.md), endpoint and selected model. Retrieval fallback must
not grant additional access. Do not paste provider secrets into issue reports.

## AtFlows says Bun is missing
In AtMem 2.3.7b2, rerun `atmem init`. If compatible Bun is absent, AtMem
announces the official pinned download, verifies its SHA-256, and keeps the
runtime private under `~/.atmem/runtime/bun` without changing global `PATH`.
Pip installation alone does not download Bun. If initialization reports a
network error, allow HTTPS access to the pinned GitHub release or install Bun
1.1+ independently, then rerun `atmem init`.

## Upgrade did not change the running version
Restart dashboard and host processes after installing into the correct environment.
Use the [2.3.6 upgrade checklist](../releases/v2.3.6.md).

## Report a bug
Include package/bridge versions, host, failing command, expected/actual behavior and
a synthetic reproducer. Never upload your Home, session payloads or credentials to
a public issue without reviewing exactly what they contain.
