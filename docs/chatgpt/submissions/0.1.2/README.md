# AtMem ChatGPT 0.1.2 submission record

The owner reported submission for review on 7 November 2026 (Australia/Sydney).
Approval/publication has not been independently verified. This is an archive of
an existing submission, not a new package release or production deployment.

## Authoritative artifacts

- `AtMem-ChatGPT-0.1.2.zip`: exact owner-supplied upload, unchanged.
- `SHA256SUMS`: archive integrity hash.
- `package/atmem-chatgpt/`: exact readable package source extracted from that ZIP.
- `record.json`: source commit, Cloud Build ID, immutable image digest, deployment revision and private configuration references.

The backend source is commit `bf326ae8f79dee74f6b8a21faa163aabc612efc6` on
`feat/chatgpt-memory-plugin`. The development plugin manifests on that branch
are not the submitted package. Use the archived package source above when
preparing a future update, and increment its plugin version deliberately.
Do not confuse the plugin version 0.1.2 with the AtMem Python package version.

The live server configuration uses Secret Manager `atmem-chatgpt-config` version 3.
That update enabled the exact OpenAI ownership challenge without changing the
server image. The owner reported the submission was completed after this update.

## Reviewer and user access

Reviewer credentials are preserved in Google Secret Manager
`atmem-chatgpt-reviewer-access` version 1 in project `atmemai`; do not copy their
values into Git, public docs, issues, screenshots or walkthroughs. The reviewer
account contains synthetic sample data; the sample editor is Vim.

Start from ChatGPT > AtMem > Connect. Existing reviewers sign in on AtMem and
choose Sign in and allow. New users choose Create account, use a password of
at least 12 characters, acknowledge the cloud-storage notice, verify their email,
then sign in and allow. Restart Connect if the linking session expires.
Changes to memories require separate signed-in approval. No automatic chat capture.

## Listing and review material

The exact listing, support/privacy/terms URLs, five positive and three negative
review cases and release notes are in the archived `plugin.json`. Commerce is
false in that package. The current package does not implement subscription billing.
The final local walkthrough is `AtMem-0.9x.mp4` in this chat's outputs; it is not
committed to Git. The public walkthrough URL, portal submission ID, selected
publisher/countries and final portal field values were not supplied to this chat.
Capture those separately from the portal before claiming this is a full portal export.

## Security and recovery

No live Firebase configuration, master encryption key, reviewer password, account
session or database contents belong in the package or repository. Secret references
and public endpoint/project identifiers are not credentials. Firebase client API
keys are public client identifiers, but do not export live configuration into Git.
Keep service-account keys, OAuth tokens, private signing material, Firebase CLI
sessions and memory exports out of version control. Recover runtime configuration
through authorized Secret Manager access, not from this archive. Never replace
existing Firebase project rules as part of restoring this plugin.

The cloud image and source commit identify code; they are not a backup of user
memories. This archival task does not change Firestore backup/retention policy.
