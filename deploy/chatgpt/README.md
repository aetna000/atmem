# Cloud deployment preparation — ChatGPT is the only product UI

The owner approved using the existing `atmemai` Blaze project on 6 November
2026. The isolated pilot uses Cloud Run `atmem-chatgpt` in `us-central1`, a new
Firestore database `atmem-chatgpt`, and a dedicated runtime service account with
an IAM condition permitting that database only. Existing `(default)` waitlist
data, Hosting and security rules are preserved. No native memories are imported.
The deny-all rules supplied here apply only to the demo emulator project.
**Never deploy them over the website rules.**

This is an invitation-only pilot, not a public plugin listing. The owner approved
lightweight hosting; no separate numeric budget was specified. Min instances 0,
max instances 1 and request billing limit idle compute, not total spending. The
additional named database has no free-tier allocation. Record actual cost and
usage before widening access. No paid model calls are part of this integration.

## Smallest supported Google design

Cloud Run (Python MCP + minimal OAuth/approval pages), Firebase Auth (invited
synthetic/user accounts), Firestore (encrypted generation snapshots and encrypted
OAuth control records), Secret Manager (operator-controlled master key/config).
There is no application dashboard or Firestore browser SDK access. Cloud Run
scratch disk is explicitly ephemeral; Firestore is the durable commit point.

Cloud Run needs linked Cloud Billing/Blaze even with a free usage quota. Free
quota is not a spending cap. Snapshot reads/writes are proportional to account
DB size, including audit reads; do not describe this as free or highly scalable.
Current caps: 8 MiB packed snapshot, 1000 active records/scope, 50 scopes/account,
20 pending actions, 120 requests/minute per observed network peer, one instance,
512 MiB suggested memory, zero minimum instances and no LLM calls. These are
pilot configuration values, not measured production capacity or hard spend caps.

## Deployment controls and remaining public-release decisions

1. Existing project/billing approval is recorded above. Do not change the linked
   billing account, buy domains or broaden this pilot. Establish a numeric
   monthly budget/alert response before general availability.
2. Inspect the isolated Firestore database and Firebase Auth; choose sign-in/access policy (initial
   pilot is invitation-only). Create a dedicated synthetic reviewer account.
   Set its actual UID in allowed_firebase_uids. Reviewers must have no real data.
3. Set server-only Firestore IAM and deny browser access to the namespace.
   Firebase rules do not constrain the server SDK; IAM is essential. Avoid
   running the service as project owner/editor and isolate it from other apps.
4. Generate a new random 256-bit master key and hold a recovery copy separately.
   Store it in Secret Manager, inject through key_env, never an image/ZIP/source.
   Current operator owns keys; this is not end-to-end/zero-knowledge encryption.
   Rotation requires offline decrypt/reseal/re-encrypt migration and tests; do
   not replace a key on a running store or claim transparent rotation support.
5. Build/review Docker image from exact source commit and test Linux/Cloud Run.
   The supplied Dockerfile/template have not yet been production-deployed.
6. Use the actual owned HTTPS service origin and exact portal-provided OAuth
   client/callback. Configure TLS/proxy host handling and any required OpenAI
   mTLS verification; test actual headers end to end. Do not guess callback URLs.
   Start with private invocation until auth/issuer/config are ready, then expose
   only the authenticated MCP and required discovery/sign-in/approval endpoints.
7. Configure Firestore TTL on control expires_at, explicit backup/PITR retention,
   orphan cleanup and monitoring. Auth expiry denies access immediately but TTL
   deletion is asynchronous. Pending action text expires lazily on the next
   successful household operation; do not promise an immediate global purge.
8. Validate signed-in OAuth, permissions, exact resource, consent, revocation,
   snapshot conflict/restart, size/latency limits and privacy-safe logging using
   synthetic users against the actual public endpoint. Then test ChatGPT account.

## Deploy/rollback discipline

Use cloudrun.service.example.yaml/config.production.example.json only after
replacing and reviewing every SET_ value. Never deploy the emulator settings.
Pin image and secret/config versions. Deploy this service only, not the website
or unrelated Firebase rules. Record image digest, commit, auth/schema version,
Firestore namespace and actual URL. Keep the previous compatible image/config
for rollback. Do not roll back to a version that ignores a new snapshot schema.
Snapshot format v1 is explicit; an unknown format fails closed.

Stop service traffic before maintenance. Export only encrypted snapshots plus
required key custody and metadata, verify engine/audit integrity in a separate
isolated environment, and test recovery before relying on a backup. Cleanup of
obsolete generations is separate from provider backups/PITR. Inspect the returned
obsolete_chunks_removed flag; never claim complete forgetting from that flag.

References checked 6 November 2026:
- https://firebase.google.com/docs/hosting/cloud-run
- https://docs.cloud.google.com/run/docs/container-contract
- https://docs.cloud.google.com/storage/docs/cloud-storage-fuse/overview
- https://firebase.google.com/docs/projects/billing/firebase-pricing-plans

## Build context privacy

Use the Dockerfile-specific ignore file when building with
`docker build -f deploy/chatgpt/Dockerfile .`; it excludes unrelated user state,
benchmarks, temporary files and Git history from the Docker context. Before
remote Cloud Build, prepare and inspect an equivalent allowlisted staging
context; gcloud uploads do not automatically inherit Docker's ignore rules.
Never send the working repository's untracked directories or service keys to a
remote builder. An allowlisted remote build may incur build/artifact storage charges within the
owner-approved pilot. Record its build ID and image digest in verification.md.

For the actual portal ownership challenge, set optional openai_domain_challenge
in approved config to the exact portal token. The service serves only that plain
text at /.well-known/openai-apps-challenge; without a token the route returns 404.
Do not invent a token or overwrite another plugin's existing challenge. Verify
its actual HTTPS hostname/response before completing the portal step.
