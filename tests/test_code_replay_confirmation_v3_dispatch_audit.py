from hashlib import sha256
import pytest
from atmem.core.canonical import canonical_json
from benchmarks.code_replay.confirmation_v3_grade import retain_dispatch
from benchmarks.code_replay.confirmation_v3_dispatch_audit import recover_dispatch,bound_request


def test_full_large_dispatch_recovered_and_wrong_chunk_role_rejected():
    events=[]
    def retain(kind,payload):
        identity=str(len(events));events.append({'object_id':identity,'envelope':{
            'run_id':'grade-case','event_type':kind,'payload':payload}})
        return {'object_id':identity,'run_id':'grade-case','payload_sha256':sha256(canonical_json(payload).encode()).hexdigest()}
    full={'slot':0,'request':{'content':'x'*16_000_000}}
    retain_dispatch(retain,full)
    assert recover_dispatch(events)==(full,True)
    events[0]['envelope']['event_type']='other-role'
    with pytest.raises(ValueError):recover_dispatch(events)


def test_small_request_recovered_and_grader_changes_are_not_authorized():
    from benchmarks.code_replay.solver_proposal import proposal_request
    name='atmem-reference-control-'+'a'*32
    command=['docker','run','--name','old','image','program']
    plan={'command_template':command,'controller_program':'controller','material':{'unchanged':'private'}}
    reference={'program_sha256':sha256(b'program').hexdigest()}
    case={'slot':0,'instance_id':'repo-1','repeat':1,'arm':'native','task_run':'case'}
    source={'base_commit':'base','files_base64':{'a.py':'eA=='},'modes':{'a.py':'100644'}}
    candidate={'files_base64':{'a.py':'eQ=='}}
    request={'program':'controller','name':name,'command':[ *command[:3],name,*command[4:]],
             'payload':proposal_request(plan['material'],source,candidate['files_base64'])}
    dispatch={**{k:case[k] for k in ('slot','instance_id','repeat','arm')},'candidate_case_run':'case',
              'frozen_grader_receipt':reference,'request':request}
    assert bound_request(dispatch,case,reference,plan,source,candidate)
    assert recover_dispatch([{'envelope':{'event_type':'external.v3_grade_dispatch','payload':dispatch}}])==(dispatch,False)
    request['command'][-1]='changed program'
    with pytest.raises(ValueError):bound_request(dispatch,case,reference,plan,source,candidate)
