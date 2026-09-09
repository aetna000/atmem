"""Scoped idempotent jobs with leases, retries, cancellation and dead letters."""
from __future__ import annotations
import time, uuid
from dataclasses import dataclass, field
from typing import Any, Callable

@dataclass(slots=True)
class Job:
    job_id: str; tenant_id: str; scope: str; idempotency_key: str; payload: dict[str, Any]; state: str = "queued"; attempts: int = 0; lease_until: float = 0; result: Any = None; errors: list[str] = field(default_factory=list)

class JobQueue:
    def __init__(self, *, max_attempts=3): self.max_attempts=max_attempts; self.jobs={}; self._keys={}
    def submit(self, *, tenant_id, scope, idempotency_key, payload):
        key=(tenant_id, scope, idempotency_key)
        if key in self._keys: return self.jobs[self._keys[key]]
        job=Job(f"job_{uuid.uuid4().hex}", tenant_id, scope, idempotency_key, dict(payload)); self.jobs[job.job_id]=job; self._keys[key]=job.job_id; return job
    def lease(self, job_id, *, seconds=60):
        job=self.jobs[job_id]
        if job.state in {"completed","cancelled","dead"} or job.lease_until > time.time(): return None
        job.state="running"; job.lease_until=time.time()+seconds; return job
    def run(self, job_id: str, worker: Callable[[dict[str, Any]], Any]):
        job=self.lease(job_id)
        if job is None: return self.jobs[job_id]
        job.attempts += 1
        try: job.result=worker(job.payload); job.state="completed"
        except Exception as exc:
            job.errors.append(type(exc).__name__); job.state="dead" if job.attempts >= self.max_attempts else "queued"; job.lease_until=0
        return job
    def cancel(self, job_id):
        job=self.jobs[job_id]
        if job.state != "completed": job.state="cancelled"
        return job
    def dead_letters(self, tenant_id): return [j for j in self.jobs.values() if j.tenant_id == tenant_id and j.state == "dead"]
