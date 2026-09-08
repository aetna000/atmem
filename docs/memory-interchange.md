# Neutral memory interchange and Mem0 migration

AtMem's line-delimited JSON archive begins with an
`atmem-memory-archive-v1` manifest followed by individually digested neutral
records. Each record carries an explicit tenant, subject, workspace and agent
scope, lifecycle state, source metadata, evidence and supported history.

Mem0 mapping preserves source IDs, content, metadata and source timestamps.
Unknown vendor fields are counted in `unsupported_fields`; vectors, graphs,
credentials and undocumented fields are never trusted as canonical data.
Missing scope is an error, not a broad default.

Imports always start with deterministic `dry_run()`. Conflicts and sensitive
records require explicit review. Commits use atomic batches, stable source IDs,
canonical generation changes and durable checkpoints. An interruption resumes
after the last acknowledged batch, while an exact replay returns the same run
receipt. Rollback tombstones only record IDs created by that run.

Exports reapply current authorization and lifecycle at execution time. Their
receipt binds the archive bytes and record-set digest. Back up canonical state
before a large migration; rollback does not restore foreign fields listed as
unsupported in the mapping report.
