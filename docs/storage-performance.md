# Storage backends and performance evidence

SQLite and its local semantic sidecar remain the zero-service defaults.
PostgreSQL canonical storage, pgvector, and Qdrant are explicit optional
backends. Derived backends nominate candidates only; AtMem reloads and
authorizes canonical records before delivery.

The reproducible reference profile is one million synthetic canonical records,
10 query workers, and 50 capture workers. Run:

```bash
python tools/benchmark_storage.py --records 1000000 --query-workers 10 --capture-workers 50 --output storage-report.json
```

Reports include hardware, configuration, a synthetic dataset digest, the
nearest-rank percentile method, and separate cold, warm, degraded, and capture
measurements. The release gate requires warm retrieval p95 ≤250 ms, canonical
capture p95 ≤100 ms, and degraded deterministic retrieval p95 ≤500 ms on the
published reference host. A smoke run validates the harness but is not
target-scale evidence.

Connection strings, queries, memory content, and secrets are deliberately
absent from health, query-plan, cache, and benchmark records. PostgreSQL and
remote derived backends fail closed or fall back to local deterministic recall
when their health contract reports unavailable or excessive lag.
