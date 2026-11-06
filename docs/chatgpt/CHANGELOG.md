# Source-only plugin 0.1.0 preparation

- Added authenticated cloud MCP access through Firebase identity and scoped OAuth.
- Preserved real AtMem memory admission, retrieval, correction, deletion and audit.
- Added encrypted Firestore household persistence with generation conflicts and
  safe idempotent recovery, without changing local stores/default dependencies.
- Added independent human previews/approvals; ChatGPT is the only product UI.
- Added real engine/emulator/MCP/browser tests, development package, review cases,
  cloud deployment templates and candid publication/account readiness gates.

An owner-approved Firebase/Cloud Run pilot is hosted; see verification.md.
Not yet released on PyPI or installed/tested in the user's
ChatGPT account, submitted, verified as a publisher or approved by OpenAI.
The published AtMem 2.3.12 package does not contain this source-only extra.

- Added Firebase registration with verified-email linkage, password recovery,
  delivery throttles and account revalidation on plugin token refresh.
