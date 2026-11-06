# Repository and official requirements audit

Base: aetna000/atmem default main, 22d1d0f311b59958adad2ecfe1b831b13a9cdf69,
version 2.3.12. AGENTS.md and constitution reviewed. LICENSE and pyproject both
say Apache-2.0; the supplied mission's AGPL assertion does not match this source.
No legal clearance is asserted. Preserve current licence/notices and dependency
obligations; recheck if source changes.

## Existing implementation
atmem/mcp/server.py is dependency-free newline JSON-RPC over local stdio. It
advertises protocol 2025-06-18 and echoes a requested protocol. Initialization,
ping, list/call and notifications exist. Its tools expose subject_id directly,
have JSON input schemas but no structured output schemas/annotations or OAuth.
The current local trust boundary must not be exposed directly to the internet.

Relevant tools: memory_remember, memory_recall(_decision), memory_get_record,
memory_get_source, memory_list, memory_forget, memory_audit, memory_verify.
The local get_source also reads admitted frozen source files: do not expose an
arbitrary filesystem path through the cloud plugin. Tool declarations are
mechanically exported in existing-mcp-tools.json. Native correction exists in
Memory.correct_record but not as a dedicated current stdio tool.

Memory hardcodes SQLiteStore and owns authoritative transactions, record/episode
provenance, supersession, graph/FTS and audit. Provider backends are not a
substitute for this full engine. HouseholdPolicy + core/keys implement optional
SQLCipher encryption; the cloud service must require encryption explicitly.
Base Memory can be plaintext: do not present its default as encrypted. Evidence
crypto is a separate AES-256-GCM container with versioned PQ export mechanisms;
SQLCipher alone is not a post-quantum/FIPS claim. Memory.correct_record and
forget_record give exact lifecycle/audit/deletion paths. Audit hashes prove
integrity, not factual truth. Existing server/KeyAuthority is in-memory scoped
service-key rotation, not the OAuth required for public ChatGPT.

## Official OpenAI findings (checked 6 November 2026)
Source URLs and downloaded-page SHA-256 receipts: official-sources.json.
- Portable Agent Plugins 1.0 root plugin.json, skills and initial mcp.json are
  supported. Do not submit app bindings, lifecycle hooks or bundled credentials.
- Remote submission needs a stable public HTTPS MCP endpoint. A private test
  tunnel does not satisfy public submission. Local desktop MCP publication needs
  partner eligibility and organisation allowlisting, not assumed for this owner.
- Private-user data/writes require authentication. Implement OAuth 2.1/PKCE S256,
  protected-resource/authorization discovery, exact resource binding and scope
  validation. Provided clients are supported; copy actual portal callbacks,
  never guess a path or silently declare protected tools unauthenticated.
- Submission owner needs organisation/project permissions and verified individual
  identity. Package text cannot establish identity verification. Public MCP review
  also needs four appropriate public URLs, actual demo recording, synthetic
  reviewer access and exactly five positive/three negative cases.
- Tool exposure, selection, invocation and permission success require actual
  account tests. Current connection documentation does not establish this owner's
  Pro 100 access or guarantee write tools, mobile support or universal invocation.

## Cloud decision and Firebase constraints
ChatGPT is the only product interface. Minimal secure OAuth/sign-in/consent and
operation-approval pages exist only for authorization. Firebase Auth can provide
identity; Firestore can persist encrypted engine snapshots and control records.
This first backend retains the SQLite engine inside request-local working
storage; it is explicitly not a native indexed Firestore rewrite. A generation
CAS is the durable commit point. Limits and write amplification are explicit.

Firebase Hosting is static. Its Cloud Run integration requires linked Cloud
Billing/Blaze even with no-cost usage quotas. Cloud Run disk is ephemeral and
not a durable DB; Cloud Storage FUSE lacks required database/locking semantics.
No production deployment, billing change or user-memory import is authorized by
this preparation. Owner accepts public hosting when needed; any charge-capable
provisioning still needs a reviewed cost boundary.

References:
- https://firebase.google.com/docs/hosting/cloud-run
- https://docs.cloud.google.com/run/docs/container-contract
- https://docs.cloud.google.com/storage/docs/cloud-storage-fuse/overview
- https://firebase.google.com/docs/projects/billing/firebase-pricing-plans

## Package schema discrepancy
The retrieved immutable Agent Plugins 1.0 MCP transport schema sets
additionalProperties=false without a per-server extensions property. Current
OpenAI plugin documentation explicitly places OAuth under each server's
extensions.com.openai.auth. We retain the documented OAuth declaration and
validate its transport projection against the versioned schema plus explicit
extension checks. This is not full-schema or portal acceptance. The discrepancy
is recorded as a required actual portal-scan check before public readiness.

SDK 1.30.0's RevocationRequest additionally requires client_secret to be present
even for a provided public client with token_endpoint_auth_method=none. A narrow
RFC 7009 endpoint replaces that route while retaining registered-client/token
ownership checks; it does not add a credential or weaken PKCE. Regression tests
exercise secretless revocation and rejection after revocation over real HTTP.

## Existing Firebase pilot authorization
Owner confirmed atmemai Blaze hosting. Billing verified enabled, existing default
Firestore database nam5 preserved. New standard native database atmem-chatgpt in
us-central1 has no free-tier allocation. Firebase Auth initially returned
CONFIGURATION_NOT_FOUND; initialized password sign-in for invited synthetic
accounts. Runtime IAM is database-bound, not merely collection-based. See
https://firebase.google.com/docs/firestore/manage-databases#configure_per-database_access_permissions
for IAM condition semantics; verify actual allowed/denied API calls.
