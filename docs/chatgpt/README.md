# Cloud AtMem with ChatGPT access — source implementation, not a public release

The first cloud interface is the ChatGPT plugin. There is no app dashboard.
Authentication and exact-operation consent use minimal service-owned pages.
The runtime uses the real AtMem engine, not a simulated memory API. Firestore
provides durable encrypted household generations; Firebase Auth supplies human
identity. The local AtMem CLI/stdio/runtime and native stores are unchanged.

This feature is prepared from AtMem 2.3.12 main, not part of the published
2.3.12 wheel. Install the reviewed feature checkout below. The plugin is 0.1.0;
a Firebase/Cloud Run pilot is hosted separately. It has not been uploaded to the
OpenAI portal, submitted, approved or published in the directory.

## Guides
- [Install and real local integration tests](SETUP.md)
- [Architecture, permissions and threat model](ARCHITECTURE.md)
- [Operations and cloud costs](OPERATIONS.md)
- [Privacy disclosure draft](PRIVACY-DRAFT.md)
- [Terms/support drafts](TERMS-SUPPORT-DRAFT.md)
- [Submission and owner actions](SUBMISSION.md)
- [Test/platform evidence](verification.md)
- [Cloud deployment preparation](../../deploy/chatgpt/README.md)

## What a user can do
Select the connected plugin, choose personal or an owned project scope, recall
memories and inspect source/version. Ask to save, correct or forget an exact
memory. Open the returned approval link, sign in to the same registered, verified-email account (or invited pilot account),
review the exact content/scope, then approve. Return to ChatGPT for commit and
its durable receipt. A proposed or locally executed operation is not a saved
memory until Firestore commits it. The user may cancel instead.

ChatGPT selection, write availability and platform confirmation on the owner's
actual account remain untested. A public directory install may have different
permissions from a private custom connection; that must be measured, not assumed.
