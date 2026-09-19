# Data storage and backup

## Portable Home (2.3.4b1)

New durable state resolves from `ATMEM_HOME`, otherwise `~/.atmem`. The Home
contains `config/`, `identity/`, `memory/`, `evidence/`, `artifacts/`,
`migrations/` and disposable `runtime/`/`indexes/` directories.
Original media is retained within the encrypted evidence boundary and artifact
vault; a host path is provenance, not a substitute for retained bytes.

```bash
atmem home status
atmem home verify
atmem restore /path/to/copied-atmem-home
```

Stop all writers before copying a Home. Keep the complete Home, including its
identity and protected key material, not just one SQLite file. On the target
computer, sign in with an Administrator from the copy. Restore opens a disposable
runtime binding; it does not silently migrate or overwrite your original Home.

For older layouts, use copy-first migration and verify before commitment:

```bash
atmem home migrate --home ~/.atmem /path/to/new-portable-home
atmem home verify --home /path/to/new-portable-home
atmem home migrate --home ~/.atmem /path/to/new-portable-home --commit
atmem home adopt --home /path/to/new-portable-home
```

Migration keeps the source. Adoption rotates sessions and changes machine-local
bindings, not historical evidence bytes. Backups retain data deleted later from
the live store; manage their retention separately. Key loss cannot be repaired
by inventing captured content.

## Legacy standalone database layouts

Older installations and explicitly selected standalone databases may use:

```text
~/.atmem/memories.db
~/.atmem/memories.db.vectors.db
~/.atmem/control-plane.json
~/.atmem/migrations/<migration-id>/
```

In 2.2, each persistent memory database also has a derived local
vector sidecar at `<memory-db>.vectors.db`. Its exact path is reported by the
dashboard storage view, and `atmem index status <memory-db>` reports its active
and retired epochs. The vector sidecar is rebuildable and never authoritative.
A canonical backup can restore memory without it, but recall may use lexical
and graph fallback until the vector generation is rebuilt.

The migration directory contains the isolated OpenClaw mirror, source snapshots, restore material and control evidence. Dashboard service metadata is separate from memory; removing the dashboard daemon does not delete memory.

Before copying a SQLite database, stop active writers or use SQLite's online
backup mechanism. Copy the database together with `-wal` and `-shm` only when
following SQLite's documented procedure. Include the derived vector sidecar
only as an optimization; do not treat it as proof of canonical backup
completeness. After restoration, run:

```bash
atmem verify /path/to/memories.db --incremental
atmem control status
```

Protect backups as personal data. A deletion from the live database does not erase independent backups; retention and backup expiry remain deployment responsibilities.
