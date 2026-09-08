# Production service profile

Validate `ProductionConfig` before opening a public listener. Public binds need
TLS and an external secret reference; canonical storage needs an encryption-key
reference. Issue the least privileged tenant/scope key, rotate with a bounded
overlap, and revoke the old key after clients have moved. Run jobs through the
tenant-bound idempotent queue and inspect dead letters using an operator role.

Take encrypted canonical backups with `encrypted_backup`, retain the receipt,
and regularly restore into an isolated store using `verified_restore`. Compare
record, lifecycle, deletion and audit generations before promotion. Roll back
by stopping workers, routing traffic to the last verified store, revoking new
credentials, and retaining both administrative audit chains.
