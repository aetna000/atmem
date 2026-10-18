"""Recover exact qualified private grader bindings before confirmation inference."""
import base64
from hashlib import sha256
import json


def qualified_grade_plan(vault,principal,identity,descriptor,image,*,event_reader=None):
    from benchmarks.code_replay.projection_evidence import verified_projection_controller
    runs=['external-windows-confirmation-public-proposal-controls-argv-v3-20261018',
          'external-windows-confirmation-public-proposal-controls-argv-v2-20261018',
          'external-windows-confirmation-public-proposal-controls-v1-20261018']
    read=event_reader or (lambda run:vault.inspect(principal,run))
    for run in runs:
        if '-argv-v3-' in run and not identity.startswith('pyvista__'):continue
        case_run=run+'-'+identity;events=read(case_run)
        ends=[e for e in events if e['envelope']['event_type']=='external.confirmation_task_checks_completed'
              and e['envelope']['payload'].get('qualified') is True]
        ds=[e for e in events if e['envelope']['event_type']=='external.confirmation_check_dispatch'
            and e['envelope']['payload']['phase']=='unchanged']
        rs=[e for e in events if e['envelope']['event_type']=='external.runtime_projection_result'
            and e['envelope']['payload']['phase']=='unchanged' and e['envelope']['payload'].get('transport_exit')==0]
        if len(ends)!=1 or len(ds)!=1 or len(rs)!=1:continue
        dispatch=ds[0]['envelope']['payload'];command=dispatch['command']
        if dispatch['source_descriptor']!=descriptor or image not in command:
            raise ValueError('qualified grader source/image differs from frozen cohort')
        worker=verified_projection_controller(events,rs[0]['envelope']['payload'])['worker']
        original=read(dispatch['prior_reference_run'])
        references=[e for e in original if e['object_id']==dispatch['prior_dispatch_object']]
        if len(references)!=1 or references[0]['envelope']['event_type']!='external.runtime_projection_dispatch':
            raise ValueError('qualified private material dispatch unavailable')
        payload=references[0]['envelope']['payload']['job']['payload']
        material={k:payload[k] for k in ('instance_id','base_commit','task_files','harness_files')}
        if material['instance_id']!=identity:raise ValueError('private material role differs')
        tests=json.loads(base64.b64decode(material['task_files']['tests.json']['content_base64'],validate=True))
        expected_f2p,expected_p2p=len(tests['FAIL_TO_PASS']),len(tests['PASS_TO_PASS'])
        marks=worker['grading']
        if (worker.get('public_base_verified') is not True or worker.get('gold_patch_written') is not False
                or marks.get('expected_f2p')!=expected_f2p or marks.get('expected_p2p')!=expected_p2p
                or marks.get('f2p_failure')!=expected_f2p or marks.get('p2p_success')!=expected_p2p
                or marks.get('p2p_failure')!=0 or marks.get('p2p_skipped')!=0):
            raise ValueError('complete unchanged private control does not match frozen expected tests')
        return {'instance_id':identity,'material':material,'command_template':command,
            'controller_program':dispatch['controller_program'],'program_sha256':sha256(command[-1].encode()).hexdigest(),
            'expected_f2p':expected_f2p,'expected_p2p':expected_p2p,'source_policy':worker['source_policy'],
            'qualified_case_run':case_run,'qualified_dispatch_object':ds[0]['object_id'],
            'qualified_result_object':rs[0]['object_id'],'private_material_reference_run':dispatch['prior_reference_run'],
            'private_material_dispatch_object':dispatch['prior_dispatch_object']}
    raise ValueError('exact completed private controls missing for '+identity)


def require_cases(rows,blocks):
    expected={(b['slot'],a):(b['instance_id'],b['repeat']) for b in blocks for a in b['order']}
    if len(expected)!=76 or len(rows)!=76 or len({(r['slot'],r['arm']) for r in rows})!=76:
        raise ValueError('all seventy-six distinct frozen cells required')
    for row in rows:
        if (expected.get((row['slot'],row['arm']))!=(row['instance_id'],row['repeat'])
                or row.get('qualified') is not True or row.get('model_calls')!=0):
            raise ValueError('frozen cell qualification differs')
    return expected
