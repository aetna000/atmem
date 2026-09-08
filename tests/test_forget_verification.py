from atmem.lifecycle.maintenance import forget_with_verification
from atmem.lifecycle.service import LifecycleService
from atmem.memory import Memory
def test_forget_requires_derived_and_backup_verification(tmp_path):
    memory=Memory(tmp_path/"m.db"); result=memory.remember("s","synthetic fact",force=True); record_id=result["records"][0]["id"]; service=LifecycleService(memory.store); generation=service.inspect("s",record_id)["generation"]
    receipt=forget_with_verification(service,"s",record_id,generation=generation,actor="test",reason="requested",backup_policy={"status":"crypto_erased"}); assert receipt["fully_verified"]
    memory.close()
