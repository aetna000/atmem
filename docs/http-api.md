# HTTP API and clients

AtMem exposes an additive `/v1` contract on the existing loopback control
server. Obtain the local session credential from `/api/session`, then send it
as `Authorization: Bearer …`. Agent and administrator principals receive
different operation sets; an agent cannot access audit, configuration,
migration, or destructive operations.

The authoritative contract is
[`docs/contracts/atmem-api-v1.openapi.yaml`](contracts/atmem-api-v1.openapi.yaml).
Python applications can use `atmem.client.AtMemClient`; TypeScript applications
use `@atmem/client`. Both expose timeouts and structured errors without hiding
review, authority, or deletion results.

Mutation retries require an idempotency key. Reusing it with different bytes is
a conflict. List cursors are opaque and scope-bound; a cursor from another
principal is invalid rather than revealing whether that scope exists.

The initial server is local and single-user. It is not safe to bind to a
non-loopback address. Authenticated TLS, tenant keys, quotas and production
operations are supplied only by the explicitly enabled production profile.
