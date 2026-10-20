import base64
from hashlib import sha256
import json
from types import SimpleNamespace

from atmem.core.canonical import canonical_json
from benchmarks.code_replay.projection_evidence import verified_projection_controller
from benchmarks.code_replay.result_transport import encode_result
from benchmarks.code_replay.retained_control import retain_control


def test_complete_protected_transport_is_recoverable_after_inline_projection():
    worker={'original_files_base64':{'code.py':'x'*3100000},'grading':{'pass':True}}
    raw=encode_result(worker,compression='lzma-v2')
    controller={'exit_code':0,'reason':None,'raw_output_truncated':False,
                'raw_output_base64':base64.b64encode(raw).decode(),'output_bytes':len(raw)}
    events=[]
    def save(kind,payload):
        identity='obj-'+str(len(events))
        event={'object_id':identity,'envelope':{'event_type':kind,'payload':payload,'run_id':'fixture'}}
        events.append(event)
        return {'object_id':identity,'run_id':'fixture','payload_sha256':sha256(canonical_json(payload).encode()).hexdigest()}
    row=retain_control(save,'task-1','unchanged',SimpleNamespace(returncode=0,
        stdout=json.dumps(controller).encode(),stderr=b''))
    assert 'original_files_base64' not in row['controller']['worker']
    assert verified_projection_controller(events,row)['worker']==worker


def test_terminal_failure_bytes_are_preserved_not_treated_as_worker_results():
    saved=[]
    def save(kind,payload): saved.append(payload);return {'object_id':'fixture'}
    row=retain_control(save,'task-1','public',SimpleNamespace(returncode=1,stdout=b'',stderr=b'failure'))
    assert row['transport_exit']==1 and 'controller' not in row
    assert base64.b64decode(saved[0]['bytes_base64'])==b'failure'
