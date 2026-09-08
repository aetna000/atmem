# Production service threat model

The production profile assumes hostile networks, compromised tenant clients,
credential replay, confused-deputy scope changes, stale cache entries, worker
crashes, malicious imports, stolen backups, and operators who can make errors.
Controls are TLS for public binds, externally referenced secrets and encryption
keys, hashed expiring scoped credentials, tenant-bound repositories and jobs,
generation-bound caches, idempotency receipts, bounded leases, encrypted
verified backups, and append-chained content-free administrator audit.

AtMem cannot protect plaintext after an authorized model or external tool has
received it, cannot guarantee deletion from undeclared third-party backups, and
does not turn MCP tool-only access into exact model-boundary proof.
