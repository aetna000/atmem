# Delegated request authentication v1

Status: Normative AtMem 2.2.6b10 transport profile.
Applies to any compatible local provider, including Storizon. Request/result
JSON and Ed25519 response signatures remain unchanged. Loopback is required;
HMAC supplies caller authentication, not encryption or isolation from another
process able to read the current user's credential files.

## Credential provisioning

Each installation generates a random 32-byte request secret (CSPRNG), stored as
canonical standard base64 in an owner-only regular file, mode 0600. Never reuse
an Ed25519 private key or a published fixture secret. Register only its absolute
file reference and a request key ID; the provider holds the matching key. Key
IDs are separate from the response signing key ID. Python accepts no unsigned
HTTP fallback. Existing registrations without credentials require migration.

## HTTP profile

POST `/v1/delegated-context` and GET `/health` require exactly one occurrence of
each header below (header names are case insensitive):

| Header | Value |
| --- | --- |
| X-AtMem-Profile | `atmem-hmac-sha256-v1` |
| X-AtMem-Provider | Registered provider ID |
| X-AtMem-Instance | Registered provider instance ID |
| X-AtMem-Key-Id | Request credential key ID |
| X-AtMem-Issued | Unix UTC seconds, decimal, no leading zero |
| X-AtMem-Expires | Unix UTC seconds, decimal, no leading zero |
| X-AtMem-Nonce | 32 fresh random bytes as 64 lowercase hex characters |
| X-AtMem-Signature | HMAC-SHA256 as 64 lowercase hex characters |

IDs match `[A-Za-z0-9_.:-]{1,256}`. Timestamps contain 1–12 decimal digits.
The HTTP Host header appears exactly once. No Transfer-Encoding is supported.
POST requires one Content-Length, one application/json Content-Type and at most
150,000 body bytes. Health has an empty body. Request bodies have a five-second
read timeout. Malformed framing is rejected without provider access.

The MAC input is ASCII, these eleven lines in order, joined by LF **with a final
LF**. No spaces, CR, URL decoding, case folding, JSON reserialization or other
normalization is performed:

```text
atmem-hmac-sha256-v1
HTTP_METHOD
EXACT_HOST_HEADER
EXACT_REQUEST_TARGET
PROVIDER_ID
INSTANCE_ID
REQUEST_KEY_ID
ISSUED
EXPIRES
NONCE
LOWERCASE_SHA256_OF_EXACT_BODY_BYTES
```

For example, Host includes the port (`127.0.0.1:8788`); an IPv6 Host includes
brackets (`[::1]:8788`). The target is the path and query as transmitted; current
provider routes accept only the two exact paths above. Method is `POST` or `GET`.
For health the body digest is SHA256 of zero bytes. All signed components are
nonempty printable ASCII with no spaces. Compute HMAC using the decoded 32-byte
secret and compare signatures in constant time. The companion JSON contains a
fixed synthetic test vector and negative/stateful vector definitions.

## Verification and replay ordering

1. Bound HTTP framing/size and reject duplicate or missing authentication headers.
2. Require the profile, exact configured provider/instance, and an accepted key.
3. Require `issued < expires <= issued + 30`, `issued <= now + 5`, and `now < expires`.
4. Verify the MAC over the received bytes and exact HTTP components.
5. Atomically reserve `(provider_id, instance_id, nonce)` in durable storage.
6. Only then call runtime request parsing/provider logic, or disclose health.

The body deadline is still checked before provider.decide. Authentication
failures return HTTP 401 with only `request_authentication_rejected`. No provider
identity, secret, query or validation details are returned. Provider health
includes `transport_profile`, `provider_id`, and `instance_id` only after success.

The ledger must survive restart and serialize concurrent reservations. The AtMem
implementation uses a private SQLite database with at most 100,000 live nonces,
expiry pruning and a persisted clock high-water mark. Clock rollback, capacity,
corruption or storage failure rejects access. Startup validates the existing schema
without repairing it; an owner-only initialization marker detects a missing ledger.
Do not delete or restore an older
ledger while credentials remain usable; recovery from ledger loss requires fresh
credentials and revocation of old credentials. Only identity, nonce and expiry
metadata is persisted, never body bytes, signatures or secrets.

An identical HTTP retry returns 401 and invokes no callback. A caller may send a
new nonce for a new transport attempt; this is not business-operation idempotency.
AtMem's acceptance of the exact same signed result remains idempotent and its
cross-turn response nonce protection is unchanged.

## Rotation and migration

Managed providers reload a private keyring on every request. Rotation generates
a fresh secret/key ID, atomically activates it and accepts the immediately previous
key for 0–300 seconds (default 30). At most two keys are accepted. Expired or revoked
keys are rejected even for fresh nonces; rotation never clears replay history.
Revocation affects subsequent authentication decisions, not callbacks already
authorized. Response-signing keys are independent and unchanged.

For an existing AtMem-managed provider:

```bash
atmem provider stop INSTANCE
atmem provider auth-init INSTANCE --json
atmem provider start INSTANCE
# Use the request_key_id and request_secret_file returned above:
atmem delegated set-request-auth PROVIDER:INSTANCE \
  --request-key-id REQUEST_KEY_ID --request-secret-file /absolute/private/request.key
atmem delegated doctor --json
atmem delegated enable PROVIDER:INSTANCE
```

Old provider/config files remain readable. A legacy enabled registration without
a usable credential stays blocked and produces migration guidance; it never
silently routes to native memory, even with a prior fallback setting. Explicit
`atmem delegated disable PROVIDER:INSTANCE` restores native operation. Replacing
client credential references disables the registration until explicit enablement.

```bash
atmem provider auth-rotate INSTANCE --overlap-seconds 300 --json
atmem delegated set-request-auth PROVIDER:INSTANCE \
  --request-key-id NEW_KEY_ID --request-secret-file /absolute/private/new.key
atmem delegated doctor --json
atmem delegated enable PROVIDER:INSTANCE
atmem provider auth-revoke INSTANCE --request-key-id OLD_KEY_ID
```

No command accepts literal secret bytes. Provider auth-init configures a managed
AtMem provider; it does not modify a separate Storizon installation. Storizon must
implement this profile at its endpoint, provision its own secret and print the
credential references alongside its existing installation-specific public key:

```bash
atmem delegated register --provider-id storizon --provider-version 0.2.0a1 \
  --instance-id local --key-id primary --public-key-file /absolute/storizon/public.key \
  --endpoint http://127.0.0.1:8788/v1/delegated-context \
  --request-key-id REQUEST_KEY_ID --request-secret-file /absolute/storizon/request.key \
  --workspace WORKSPACE --agent AGENT --user USER
atmem delegated doctor --json
atmem delegated enable storizon:local
```

The Storizon demo public key remains test-only Ed25519 material; it is neither
a shared production trust root nor an HMAC secret. Full private Storizon service
acceptance requires its maintainer to run these shared transport vectors and the
live delegated turn after adopting this profile.
