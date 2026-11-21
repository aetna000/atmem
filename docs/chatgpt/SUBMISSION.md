# Public release preparation and precise owner steps

Status: implementation and development package preparation plus an owner-approved
Firebase pilot. See verification.md for actual endpoint status. No ChatGPT account
installation, draft upload, review submission or approved release exists.
A local ZIP is not submission readiness. Only the user's own verified individual
publisher may be selected; no borrowed business/publisher identity is used.

## 1. Approve cloud pilot configuration and cost boundary

Review deploy/chatgpt/README.md. The owner approved existing atmemai Blaze for
a small isolated pilot in us-central1. Set a numeric budget/usage response and
confirm invited users and actual backup/PITR/log/TTL policy before general access. Cloud Run requires Cloud Billing even
within usage quotas. Existing atmem.ai Hosting/waitlist is not the memory server.
Do not replace that project's rules or import the owner's native memory.

The first adapter persists encrypted real-engine snapshots; it does not replace
AtMem semantics with Firestore documents. Start small and measure actual costs,
latency, conflicts and quotas. Production/Linux/container/managed TLS/mTLS and
provider logs must be verified on the deployed service before public submission.

## 2. Verify intended publisher and account rights

In the actual OpenAI Platform organization/project, confirm the user has owner
or required Apps Management Write access and complete individual verification.
Use its exact verified personal name. Repository author Javad Taghia is known;
OpenAI identity verification and this account's publishing entitlement are not.
Select actual supported countries and decide commerce/payment behavior; these
fields are intentionally not invented in the ZIP. Have the owner complete legal,
policy, data/brand-rights attestations. Current source licence is Apache-2.0.

## 3. Establish actual endpoint and synthetic reviewer access

Hosting approval is recorded; directory publication remains separate. Use its real stable public HTTPS origin/MCP
path and exact portal callback/client values. Configure OAuth provided PKCE,
Firebase Auth, invited UID list, IAM/keys and ownership challenge. Do not reuse
loopback development client values, hard-code bearer tokens, relabel writes as
reads, or declare private memory tools unauthenticated. A private tunnel can be
a development route if actually available; it is not a public-submission endpoint.
Local desktop publication additionally requires partner allowlisting, not assumed.

Create an invited reviewer account containing only synthetic data. Credentials
and login URL/instructions go in secure dashboard reviewer fields, never the ZIP,
public issue, listing or video. The reviewer must not need the owner's mailbox,
phone or personal account. Test sign-in, read/write/delete permissions and all
cases. Keep that account available for future reviews. Test fixtures here create
and remove emulator accounts; they do not leave a production reviewer provisioned.

## 4. Publish actual policy/support materials and record a real demo

Drafts: PRIVACY-DRAFT.md and TERMS-SUPPORT-DRAFT.md. Resolve actual operator,
retention/backup/log, residency, account eligibility and support decisions, then
publish appropriate plugin-specific pages at owner-controlled HTTPS URLs:
websiteURL, supportURL, privacyPolicyURL, termsOfServiceURL. Current website
analytics/privacy copy is not automatically a cloud-memory policy. These URLs
are omitted rather than guessed. A 200 response alone is not content verification.

Demo rehearsal in a real selected-plugin ChatGPT chat:
1. Show the connected synthetic account, current plugin and discovered tools.
2. Ask the seeded editor question; show actual read/source result.
3. Save unique sample codename copper-heron; show proposal, separate human sign-in
   and preview, platform confirmation if any, durable commit receipt and persisted
   state check. Hide passwords/tokens throughout.
4. Start a new chat, select the plugin and read the saved codename.
5. Correct the sample editor and forget the codename; show native/cloud receipts
   and the empty subsequent recall. Include one cancellation or unavailable case.
6. Record actual prompts/results on the intended host, then play back to verify
   legibility, completion and absence of secrets. Host the real recording where
   reviewers can play it without login. Set review.demo_recording_url only after
   verifying that recording. This script and local screenshots are not a demo.

## 5. Run actual account evaluations (Pro 100 is user-reported, unverified)

Use the exact positive/negative cases in plugin.json. Five positive cases cover
read/provenance, save, project isolation, correction and exact deletion. Three
negative cases cover background capture, other users/secrets and cloud spending.
Keep their manifest expectations separate from executed result evidence.

Record plan/account type, web/desktop/mobile surface, UTC time, discovery and
actual tool-call arguments/results/rejections and confirmations. Classify:
- not exposed: missing tool from actual discovery;
- not invoked: tool available but no call occurred;
- permission rejected: actual account/platform authorization blocked it;
- backend failure: service/transport rejected or failed the call.

On the actual account, none of these outcomes has been measured yet. Do not call
that a plan restriction. If writes are blocked, finish permitted read tests,
retain the functioning backend writes and record the exact rejection. A public
install may differ from a private custom connection; verify rather than promise.
Mobile/Desktop availability and universal invocation remain unverified.

## 6. Finalize and inspect public package

Source: plugins/atmem-chatgpt, version 0.1.0. Development mcp.json includes its
real implemented loopback MCP route and OAuth settings in the initial bundle.
The runtime is deployed separately from the plugin ZIP; skills/metadata/icons are
included. Use scripts/package_chatgpt_plugin.py --readiness to list gaps.

Current official OpenAI docs place OAuth under server.extensions.com.openai;
the current published Agent Plugins 1.0 MCP schema lacks that extensions property.
The build validates a strict transport projection and explicit OpenAI fields,
not unchanged full-schema acceptance. Resolve the actual portal scan and preserve
its diagnostics. Never omit OAuth to make a schema-only check green.

Supply --metadata JSON with verified interface listing fields and real recording,
and actual mcp configuration. For a public build, --verification-record must
record true only after these checks actually pass:
verified_individual_publisher, organization_project_access,
public_endpoint_oauth_tested, domain_ownership, policy_urls_reviewed,
recording_playback_verified, synthetic_reviewer_access_verified,
actual_chatgpt_read_write_results_recorded.
The schema-extension portal scan is an additional dashboard gate after candidate
upload; it is not required before building the initial upload candidate.
These are operator-recorded evidence gates, not automatic identity verification.
The portal itself is authoritative for identity/scans/review. A valid ZIP alone
cannot approve itself. Rebuild after every change; inspect final ZIP, all case
counts, references, versions, URLs, icon dimensions and absence of secrets.

## 7. Owner-controlled portal action, after separate authorization

Upload the ZIP with its initial MCP connection as a draft under the intended
organization/project and verified person. Inspect imported metadata and OAuth
settings; complete domain challenge, connection, scans and reviewer access.
Compare the exact saved version and cases. Have the owner make required
attestations. Upload, submit for review and publish an approved release are
three different actions; none has happened in this task. Do not promise approval.

## Current official references (recheck immediately before submission)

- https://developers.openai.com/plugins/deploy/submission
- https://developers.openai.com/plugins/plugin-guidelines
- https://developers.openai.com/plugins/deploy/desktop-only
- https://developers.openai.com/plugins/build/auth
- https://developers.openai.com/plugins/deploy/connect-chatgpt
- https://developers.openai.com/plugins/build/plugins
- https://agent-plugins.org/schemas/1.0.0/plugin.schema.json
- https://agent-plugins.org/schemas/1.0.0/mcp.schema.json

Dated SHA-256 source receipts: specs/049-chatgpt-memory-plugin/official-sources.json.
