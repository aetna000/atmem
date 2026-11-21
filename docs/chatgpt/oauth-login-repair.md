# OAuth consent storage repair - 21 November 2026

The hosted plugin source is on `fix/chatgpt-account-access`, not native package
`main`. This repair is based on commit 00d107bc73de49f1e7455b0c5603108ffb3ab6d5.

The previous provider consumed the authorization request in one Firestore
transaction, then wrote its authorization code separately. A failed second write
left no code and no pending request. Retrying the sign-in then displayed
"This sign-in request has ended". This is a verified code failure path, but its
occurrence in the reported production incident is not established.

The new transaction checks the original request, expiry and account deletion
fence, stores the encrypted code, and removes the pending request together.
Failed writes leave consent available for retry. Completed consent remains
single-use. PKCE, exact callback, scopes, CSRF, account checks and expiry remain
in place. Denial consumes the request without issuing a code.

Privacy-safe OAuth logs identify pre-issuance unavailability, commit-stage
unavailability, and storage exception type. They exclude account identifiers,
request IDs, passwords, tokens and callback URLs.

Validation: five unit tests pass with a transactional Firestore test double,
including provider-level failure followed by retry with the original OAuth state
and PKCE challenge. Python compilation and git diff whitespace checks pass.
These tests do not constitute real Firestore, browser or live OpenAI verification.
Cached local dependencies were used; the deployment-pinned environment still
needs the existing emulator integration suite.

Production status: not deployed. Cloud log retrieval was blocked by DNS resolution
of oauth2.googleapis.com in the execution environment. The reported incident
therefore remains unconfirmed. Before deployment, run the real Firebase emulator
suite documented in .github/workflows/chatgpt-cloud.yml. Inspect a fresh failing
reconnect's Cloud Run request/status logs, without copying query parameters or
credentials. After deploying the tested image to the existing service, verify a
fresh Platform Reconnect completes its OAuth callback/token exchange and Rescan
updates the last-checked time. Separately verify refresh after access-token expiry.

## Actual Platform browser trace - 21 November 2026

A fresh Platform Reconnect opened a valid Connect to AtMem form. The next observed
submission returned the ended-request HTML directly from POST /connect/{nonce}.
Browser Network showed one recorded request (recording did not cover the initial
authorization GET, so it cannot exclude earlier requests or consumption).

- Response date: 2026-11-21 05:39:19 UTC (16:39:19 Sydney).
- Method/status: POST /connect/{nonce}, HTTP 400.
- Google response trace header: 6be0fc833837aee79682ad25713aa3ac.
- Origin and Referer were same-origin; response Cache-Control was no-store.
- The ended-request response was returned directly, with no callback redirect
  captured for that submission. No CSP-blocked callback error was observed.
- In inspected source, this exact page/status is returned when the initial
  repository.get_control('authorize', nonce) returns None, before reading the
  form, validating CSRF, authenticating a password or issuing a code.

This narrows the failure to pending-request availability on that POST; it does
not distinguish missing, expired, already consumed, wrong namespace or a
mismatched live deployment. Inspect the Cloud Run request matching this trace,
then correlate the preceding authorize/form GET and any earlier consent POSTs.
The browser request headers contained cookies; do not export or commit raw HAR,
request headers or form payloads. No passwords, cookies or full nonce URLs are
retained in this note. Cloud logs remain inaccessible from this task's terminal.
