import pytest
from benchmarks.code_replay.confirmation_v3_grade import complete_cases,recover_candidate,retain_dispatch
from tests.test_code_replay_confirmation_v3_lock import fixture


def test_no_early_private_grading_or_success_only_cohort():
    rows,blocks=fixture();lock={'staging_manifest':{'blocks':blocks}}
    assert len(complete_cases(lock,rows,[{'attempts_completed':76}]))==76
    with pytest.raises(ValueError):complete_cases(lock,rows[:-1],[{'attempts_completed':75}])
    with pytest.raises(ValueError):complete_cases(lock,rows,[])


def test_oversized_candidate_refused_before_access():
    with pytest.raises(ValueError):recover_candidate([],{'source_bytes':129_000_000,'receipts':[]})


def test_large_dispatch_is_lossless_and_each_event_stays_under_unchanged_limit():
    from hashlib import sha256
    import json
    from atmem.core.canonical import canonical_json
    from benchmarks.code_replay.windows_metrics import recover_stream
    events={}
    def retain(kind,payload):
        raw=canonical_json(payload).encode()
        assert len(raw)<=16_000_000
        identity=str(len(events))
        events[identity]={'object_id':identity,'envelope':{'event_type':kind,'payload':payload}}
        return {'object_id':identity,'payload_sha256':sha256(raw).hexdigest()}
    small={'slot':0,'request':{'content':'unaltered'}}
    receipt=retain_dispatch(retain,small)
    assert events[receipt['object_id']]['envelope']['payload']==small
    payload={'slot':1,'request':{'content':'x'*16_000_000},'candidate_case_run':'original'}
    receipt=retain_dispatch(retain,payload)
    index=events[receipt['object_id']]['envelope']['payload']
    assert index['full_request_retained'] and 'request' not in index
    assert json.loads(recover_stream(events,index['full_dispatch_transport']))==payload
