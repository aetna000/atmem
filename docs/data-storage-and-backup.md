# Data storage and backup

Default locations:

```text
~/.atmem/memories.db
~/.atmem/memories.db.vectors.db
~/.atmem/control-plane.json
~/.atmem/migrations/<migration-id>/
```

In 2.2 development, each persistent memory database also has a derived local
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
