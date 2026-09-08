import threading
from atmem.control.manager import ControlPlaneManager
from atmem.service import APIPrincipal,AtMemApplication,APIError
def test_scoped_concurrent_idempotency_has_one_mutation(tmp_path):
    manager=ControlPlaneManager.start(host="generic",state_path=tmp_path/"s.json",control_root=tmp_path/"c",memory_db=tmp_path/"m.db")
    principal=APIPrincipal("p","agent",manager.state().subject_id); app=AtMemApplication(manager); values=[]
    def call():
        try: values.append(app.create_memory(principal,"synthetic value",idempotency_key="same"))
        except APIError as exc: values.append(exc.code)
    threads=[threading.Thread(target=call) for _ in range(2)]
    for t in threads:t.start()
    for t in threads:t.join()
    assert len(values)==2 and sum(isinstance(v,dict) for v in values)>=1
