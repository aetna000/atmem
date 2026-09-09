from atmem.server.admin_audit import AdminAudit
from atmem.server.jobs import JobQueue
from atmem.server.observability import health
def test_jobs_are_idempotent_retryable_and_tenant_bound():
    q=JobQueue(max_attempts=2); one=q.submit(tenant_id="a",scope="ws",idempotency_key="x",payload={}); two=q.submit(tenant_id="a",scope="ws",idempotency_key="x",payload={}); assert one is two
    q.run(one.job_id,lambda _: (_ for _ in ()).throw(RuntimeError())); assert one.state=="queued"
    q.run(one.job_id,lambda _: (_ for _ in ()).throw(RuntimeError())); assert q.dead_letters("a")==[one]
def test_redacted_health_and_chained_admin_audit():
    assert health(authenticated=True,dependencies={"store":"ok"})["status"]=="ok"
    audit=AdminAudit(); audit.append("p","rotate","digest"); assert audit.verify()
