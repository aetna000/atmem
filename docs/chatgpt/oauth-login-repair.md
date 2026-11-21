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
