"""Actual public isolation and private proposal controls; never invokes a solver."""
import base64
import ast
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import zlib
from types import SimpleNamespace
from uuid import uuid4

from atmem.core.canonical import canonical_json
from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.derived_runtime import local_worker_command
from benchmarks.code_replay.eligibility_binding import bound_worker_source
from benchmarks.code_replay.projection_evidence import verified_projection_controller, recover_projection_stream
from benchmarks.code_replay.program_transport import compact_program
from benchmarks.code_replay.public_test_control import public_bootstrap, public_request, success
from benchmarks.code_replay.retained_control import retain_control
from benchmarks.code_replay.run_evidence import operational_evidence
from benchmarks.code_replay.runtime_projection_control import projected_control_source
from benchmarks.code_replay.solver_proposal import solver_bootstrap, proposal_request, proposal_controls_qualified
from benchmarks.code_replay.source_policy import SourcePolicy
from benchmarks.code_replay.windows_confirmation_exports import RUN as EXPORTS, BOUNDARIES, recover_export
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
from benchmarks.code_replay.windows_transport import framed_command, framed_input, worker_program
from benchmarks.code_replay.external_qualification import worker_command

RUN = 'external-windows-confirmation-public-proposal-controls-v1-20261018'
PROBE_PATH = 'tests/test_atmem_public_boundary_20261018.py'
MODULES = {'pallets/flask':'flask', 'mwaskom/seaborn':'seaborn', 'pydata/xarray':'xarray',
           'pylint-dev/pylint':'pylint', 'pyvista/pyvista':'pyvista'}


def isolation_probe(module):
    if module not in set(MODULES.values()):
        raise ValueError('fixed public source module required')
    return ("from pathlib import Path\nimport importlib,socket\n"
        "def test_current_source_import():\n"
        " module=importlib.import_module("+repr(module)+")\n"
        " assert Path(module.__file__).resolve().is_relative_to(Path('/work'))\n"
        "def test_private_artifacts_absent():\n"
        " assert not Path('/testbed/.git').exists()\n"
        " assert not Path('/opt/atmem-evaluator').exists()\n"
        " assert not Path('/mnt/c/Users/user/.codex/auth.json').exists()\n"
        "def test_external_network_denied():\n"
        " with socket.socket() as channel:\n"
        "  channel.settimeout(0.2)\n"
        "  try: channel.connect(('1.1.1.1',443))\n"
        "  except OSError: return\n"
        "  raise AssertionError('external network available')\n")


def retained_grader(plan):
    """Use the actual qualified program, not a rebuilt registration ordering."""
    found=[]
    for node in ast.parse(plan['program']).body:
        if (isinstance(node,ast.For) and isinstance(node.target,ast.Tuple)
            and [part.id for part in node.target.elts if isinstance(part,ast.Name)]==['name','source']):
            for name,source in ast.literal_eval(node.iter):
                if name=='atmem_external_control': found.append(source)
    if (len(found)!=1 or sha256(found[0].encode()).hexdigest()
        !=plan['projection_registration']['projected_worker_sha256']):
        raise ValueError('exact embedded qualified grading worker required')
    return found[0]


def main():
    global RUN
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--argv-v2',action='store_true',help='Only proved pre-Docker argv failures; reuse completed grades')
    parser.add_argument('--pyvista-argv-v3',action='store_true',help='Only three zero-worker compact-program guard failures')
    args=parser.parse_args()
    prior_run=RUN
    if args.pyvista_argv_v3:args.argv_v2=True
    if args.argv_v2:RUN=RUN.replace('-v1-','-argv-v3-' if args.pyvista_argv_v3 else '-argv-v2-')
    scope = EvidenceScope('benchmark','local-operator','click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault = operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    if vault.inspect(principal,RUN):
        raise ValueError('controls already retained; inspect original handle')
    cache = {}
    def events(run):
        if run not in cache: cache[run]=vault.inspect(principal,run)
        return cache[run]
    def save(kind,payload):
        return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    if args.argv_v2:
        prior=[e for e in events(prior_run) if e['envelope']['event_type']=='external.confirmation_checks_completed']
        if len(prior)!=1:raise ValueError('all original checks must be terminal before explicit argv repair')
    ends=[e['envelope']['payload'] for e in events(EXPORTS) if e['envelope']['event_type']=='external.confirmation_exports_completed']
    if len(ends)!=1: raise ValueError('terminal source exports required')
    descriptors={r['instance_id']:r for r in ends[0]['results'] if r['qualified']}
    if args.pyvista_argv_v3:
        expected={'pyvista__pyvista-4311','pyvista__pyvista-4329','pyvista__pyvista-4853'}
        stopped_run=prior_run.replace('-v1-','-argv-v2-')
        endings=[e['envelope']['payload'] for e in events(stopped_run)
                 if e['envelope']['event_type']=='external.confirmation_checks_completed']
        if len(endings)!=1:raise ValueError('terminal argv-v2 batch required')
        failures={r['instance_id']:r for r in endings[0]['results'] if r['instance_id'] in expected}
        if set(failures)!=expected or any(r.get('failure')!='ValueError: compressed program argv budget exceeded' for r in failures.values()):
            raise ValueError('exact three compact-program guard failures required')
        preflight=events('external-windows-pyvista-program-encoding-preflight-v1-20261018')
        proofs=[e['envelope']['payload'] for e in preflight
                if e['envelope']['event_type']=='external.program_encoding_preflight_completed']
        if (len(proofs)!=1 or proofs[0].get('qualified') is not True or len(proofs[0]['rows'])!=9
            or proofs[0]['encoder_sha256']!=sha256(Path(__file__).with_name('program_transport.py').read_bytes()).hexdigest()):
            raise ValueError('exact nine-program bounded encoding preflight required')
        for identity in expected:
            before=events(stopped_run+'-'+identity)
            dispatched=[e for e in before if e['envelope']['event_type']=='external.confirmation_check_dispatch']
            completed=[e for e in before if e['envelope']['event_type']=='external.runtime_projection_result']
            if (len(dispatched)!=1 or len(completed)!=1
                or dispatched[0]['envelope']['payload']['phase']!='public_isolation'
                or completed[0]['envelope']['payload']['phase']!='public_isolation'):
                raise ValueError('guard correction requires exactly one completed public phase and no private dispatch')
            verified_projection_controller(before,completed[0]['envelope']['payload'])
        descriptors={i:r for i,r in descriptors.items() if i in expected}
    selection=json.loads(Path('preflight/selection.json').read_bytes())
    metadata=json.loads(Path('preflight/metadata.json').read_bytes())
    _,registration=bound_worker_source(selection,metadata)
    plans={};top={}
    for run in BOUNDARIES:
        plans[run]=next(e['envelope']['payload'] for e in events(run) if e['envelope']['event_type']=='external.runtime_projection_planned')
        end=next(e['envelope']['payload'] for e in events(run) if e['envelope']['event_type']=='external.runtime_projection_completed')
        retained_grader(plans[run])
        top.update({i:run for i in end['qualified_identities']})
    def phase_record(run,identity,phase):
        found=[e for e in events(run) if e['envelope']['event_type'] in {
            'external.runtime_projection_result','external.runtime_projection_reused_result'}
            and e['envelope']['payload'].get('instance_id')==identity and e['envelope']['payload'].get('phase')==phase]
        if len(found)!=1: raise ValueError('exact prior phase required')
        event=found[0];row=event['envelope']['payload']
        if event['envelope']['event_type'].endswith('_reused_result'):
            old=next(e for e in events(row['prior_run']) if e['object_id']==row['prior_object_id'])
            if sha256(canonical_json(old['envelope']['payload']).encode()).hexdigest()!=row['prior_payload_sha256']:
                raise ValueError('prior phase receipt differs')
            return phase_record(row['prior_run'],identity,phase)
        dispatch=next(e for e in events(run) if e['envelope']['event_type']=='external.runtime_projection_dispatch'
            and e['envelope']['payload']['instance_id']==identity and e['envelope']['payload']['phase']==phase)
        return run,event,dispatch
    save('external.confirmation_checks_planned',{'driver_source':Path(__file__).read_text(),
        'exports_run':EXPORTS,'identities':sorted(descriptors),'max_workers':4,'model_calls':0,
        'public_control':'fixed three-test source/import/private-artifact/network probe; not full public-suite claim',
        'private_control':'unchanged and reference public proposals with unchanged declared grading',
        'product_changed':False,'final_model_manifest_frozen':False,'argv_repair_of':prior_run if args.argv_v2 else None})
    jobs=[]
    for identity,descriptor in sorted(descriptors.items()):
        source=recover_export(events(descriptor['export_run']),descriptor)
        run,event,dispatch=phase_record(top[identity],identity,'reference_as_proposal')
        previous=verified_projection_controller(events(run),event['envelope']['payload'])['worker']
        task={'instance_id':identity,'base_commit':source['base_commit'],'image_extras_sha256':source['image_extras_sha256']}
        source_roots,test_roots=registration['source_profiles'][identity]
        policy=SourcePolicy(tuple(source_roots),test_roots=tuple(test_roots))
        candidate={name:value for name,value in previous['candidate_files_base64'].items()
                   if name in source['files_base64'] or policy.source(name)}
        prior=dispatch['envelope']['payload']['job']
        image=next(s for s in prior['command'] if s.startswith('swebench/') or (s.startswith('sha256:') and len(s)==71))
        material={k:prior['payload'][k] for k in ('instance_id','base_commit','task_files','harness_files')}
        expected=json.loads(base64.b64decode(material['task_files']['tests.json']['content_base64']))
        repo=source['repository'];probe=isolation_probe(MODULES[repo])
        if PROBE_PATH in source['files_base64']: raise ValueError('probe filename collision')
        public_candidate={**source['files_base64'],PROBE_PATH:base64.b64encode(probe.encode()).decode()}
        public_program=public_bootstrap(task,operator_registration=registration,
            runtime_manifest=source['runtime_manifest'],result_transport='lzma-v2')
        private_program=solver_bootstrap(retained_grader(plans[top[identity]]),task,operator_registration=registration,
            runtime_manifest=source['runtime_manifest'],result_transport='lzma-v2')
        phases=[('public_isolation',public_program,public_request(source,public_candidate,paths=[PROBE_PATH])),
                ('unchanged',private_program,proposal_request(material,source,source['files_base64'])),
                ('reference_as_proposal',private_program,proposal_request(material,source,candidate))]
        jobs.append({'identity':identity,'source_descriptor':descriptor,'prior_reference_run':run,
            'prior_reference_object':event['object_id'],'prior_dispatch_object':dispatch['object_id'],
            'image':image,'phases':phases,'expected_f2p':len(expected['FAIL_TO_PASS']),
            'expected_p2p':len(expected['PASS_TO_PASS']),'source_roots':tuple(source_roots),'test_roots':tuple(test_roots)})
    # All inputs are reconstructed and bound before starting test workers.
    if args.argv_v2:
        for item in jobs:
            item['previous_events']=events(prior_run+'-'+item['identity'])
            if args.pyvista_argv_v3:
                item['completed_public_events']=events(prior_run.replace('-v1-','-argv-v2-')+'-'+item['identity'])
    def execute(item):
        identity=item['identity'];task_run=RUN+'-'+identity
        target=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=task_run)
        if target.inspect(principal,task_run): raise ValueError('task controls already dispatched')
        def retain(kind,payload):return target.capture(run_id=task_run,kind=kind,principal=principal,payload=payload)
        results={}
        for phase,program,payload in item['phases']:
            if args.argv_v2:
                reuse_run=prior_run+'-'+identity
                before=item['previous_events']
                if args.pyvista_argv_v3 and phase=='public_isolation':
                    before=item['completed_public_events']
                    reuse_run=prior_run.replace('-v1-','-argv-v2-')+'-'+identity
                byid={e['object_id']:e for e in before}
                rows=[e for e in before if e['envelope']['event_type']=='external.runtime_projection_result'
                      and e['envelope']['payload']['phase']==phase]
                dispatches=[e for e in before if e['envelope']['event_type']=='external.confirmation_check_dispatch'
                            and e['envelope']['payload']['phase']==phase]
                if len(rows)!=1 or len(dispatches)!=1:raise ValueError('exact prior phase and dispatch required')
                prior=rows[0]['envelope']['payload'];dispatch=dispatches[0]['envelope']['payload']
                original_program=dispatch['command'][-1]
                if args.pyvista_argv_v3 and phase=='public_isolation':
                    # V2's successful public command used the prior zlib argv
                    # wrapper. Its source payload was verified before dispatch;
                    # compare the untouched original dispatch as well.
                    original_dispatch=next(e['envelope']['payload'] for e in item['previous_events']
                        if e['envelope']['event_type']=='external.confirmation_check_dispatch'
                        and e['envelope']['payload']['phase']==phase)
                    original_program=original_dispatch['command'][-1]
                    assignments=[n for n in ast.parse(dispatch['command'][-1]).body
                        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_source' for t in n.targets)]
                    if len(assignments)!=1:raise ValueError('exact retained compressed program assignment required')
                    encoded=ast.literal_eval(assignments[0].value.args[0].args[0])
                    decoder=zlib.decompressobj()
                    restored=decoder.decompress(base64.b64decode(encoded,validate=True),4_000_001)
                    if (restored!=program.encode() or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail):
                        raise ValueError('reused public argv does not restore the original program')
                if (original_program!=program
                    or dispatch['payload_sha256']!=sha256(canonical_json(payload).encode()).hexdigest()):
                    raise ValueError('argv repair changed qualified code or input payload')
                if prior.get('transport_exit')==0:
                    results[phase]=verified_projection_controller(before,prior)
                    retain('external.confirmation_check_reused',{'phase':phase,'prior_run':reuse_run,
                        'prior_object_id':rows[0]['object_id'],'prior_payload_sha256':sha256(canonical_json(prior).encode()).hexdigest(),
                        'new_test_execution':False})
                    continue
                stderr=recover_projection_stream(byid,prior['streams']['stderr'])
                stdout=recover_projection_stream(byid,prior['streams']['stdout'])
                if (prior.get('transport_exit')!=1 or stdout or not stderr.endswith(b"OSError: [Errno 7] Argument list too long: 'docker'\n")):
                    raise ValueError('only proved pre-Docker argv failures may execute again')
                retain('external.confirmation_argv_failure_preserved',{'phase':phase,'prior_run':prior_run+'-'+identity,
                    'prior_object_id':rows[0]['object_id'],'tests_previously_not_started':True})
            name='atmem-reference-control-'+uuid4().hex
            factory=local_worker_command if item['image'].startswith('sha256:') else worker_command
            command=factory(item['image'],name,compact_program(program) if args.argv_v2 else program)
            job={'program':worker_program(),'name':name,'command':command,'payload':payload}
            retain('external.confirmation_check_dispatch',{'phase':phase,'command':command,
                'controller_program':job['program'],'payload_sha256':sha256(canonical_json(payload).encode()).hexdigest(),
                'source_descriptor':item['source_descriptor'],'prior_reference_run':item['prior_reference_run'],
                'prior_reference_object':item['prior_reference_object'],'prior_dispatch_object':item['prior_dispatch_object'],
                'probe_source':isolation_probe(MODULES[identity.rsplit('-',1)[0].replace('__','/')]) if phase=='public_isolation' else None})
            try:
                proc=subprocess.run(framed_command(),input=framed_input(job),capture_output=True,timeout=205)
            except subprocess.TimeoutExpired as exc:
                proc=SimpleNamespace(returncode=None,stdout=exc.stdout or b'',stderr=exc.stderr or b'')
            row=retain_control(retain,identity,phase,proc)
            if proc.returncode is None: row['transport_failure']='transport_timeout'
            retain('external.runtime_projection_result',row)
            results[phase]=row.get('controller',{}) if not row.get('decode_failure') else {}
        public_ok=success(results['public_isolation'])
        proposal_ok=proposal_controls_qualified({p:results[p] for p in ('unchanged','reference_as_proposal')},
            expected_f2p=item['expected_f2p'],expected_p2p=item['expected_p2p'],
            source_roots=item['source_roots'],test_roots=item['test_roots'])
        summary={'instance_id':identity,'public_isolation_qualified':public_ok,'private_proposals_qualified':proposal_ok,
            'qualified':bool(public_ok and proposal_ok),'task_run':task_run,'model_calls':0,
            'phase_summaries':{p:{'exit_code':r.get('exit_code'),'reason':r.get('reason'),
                'worker_exit':r.get('worker',{}).get('exit_code'),'grading':r.get('worker',{}).get('grading')} for p,r in results.items()}}
        retain('external.confirmation_task_checks_completed',summary)
        return summary
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(execute,item):item for item in jobs}
        for future in as_completed(futures):
            try: result=future.result()
            except Exception as exc:
                result={'instance_id':futures[future]['identity'],'qualified':False,'model_calls':0,
                        'failure':type(exc).__name__+': '+str(exc),'not_automatically_retried':True}
            save('external.confirmation_task_checks_result',result)
            results.append(result);print(json.dumps(result),flush=True)
    save('external.confirmation_checks_completed',{'results':results,'model_calls':0,
        'qualified':sum(r['qualified'] for r in results),'final_model_manifest_frozen':False})


if __name__=='__main__': main()
