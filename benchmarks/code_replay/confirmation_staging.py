"""Freeze the amended cohort and stage independent installed-product cases."""
import base64
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from atmem.core.canonical import canonical_json
from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
from benchmarks.code_replay.confirmation_design import select_tasks,paired_blocks,SEED
from benchmarks.code_replay.confirmation_issues import issue_blob
from benchmarks.code_replay.eligibility_binding import bound_worker_source
from benchmarks.code_replay.public_test_bridge import patch_bootstrap,server_bootstrap
from benchmarks.code_replay.run_evidence import operational_evidence
from benchmarks.code_replay.windows_confirmation_exports import RUN as EXPORTS,recover_export
from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
from benchmarks.code_replay.windows_first_pair import STAGE
from benchmarks.code_replay.windows_operator_host import PYTHON
from benchmarks.code_replay.windows_transport import framed_command,framed_input

RUN='external-windows-confirmation-amended19-staging-v1-20261018'
CHECKS='external-windows-confirmation-public-proposal-controls-argv-v2-20261018'
PYVISTA_CHECKS='external-windows-confirmation-public-proposal-controls-argv-v3-20261018'
CASE_ROOT=Path('/home/jt/atmem-benchmark-runtime-20261018/confirmation-stage-v1')
EXTRACTOR='sha256:62e15650d96e24eb4c5adce548ee711425e4a91f1a87ab9f9a8772a78ed724f3'


def stage_program():
    source=STAGE.replace('import base64,json,os,subprocess','import base64,json,os,subprocess,zlib')
    source=source.replace("arm=='atmem'","arm!='native'")
    old='generation=lane.knowledge.current(str(workspace));scope=lane.scope.to_dict()'
    if source.count(old)!=1:raise ValueError('review known installed staging program')
    source=source.replace(old,"generation=base64.b64encode(zlib.compress(json.dumps(lane.knowledge.current(str(workspace))).encode())).decode();scope=lane.scope.to_dict()")
    source=source.replace("'generation':generation","'generation_zlib_base64':generation")
    source=source.replace("run_id='windows-first-repair-atmem'","run_id=job['block_id']+'-tools'")
    source=source.replace("'windows-first-repair-'+arm","job['block_id']+'-'+arm")
    return source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--continue-unattempted',action='store_true',help='Preserve failed block; stage only untouched remaining blocks')
    args=parser.parse_args()
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=RUN)
    existing=vault.inspect(principal,RUN)
    if existing and not args.continue_unattempted:raise ValueError('staging already dispatched; inspect original handle')
    if args.continue_unattempted and not existing:raise ValueError('no retained staging stop to continue')
    cache={}
    def events(run):
        if run not in cache:cache[run]=vault.inspect(principal,run)
        return cache[run]
    def only(run,kind):
        found=[e['envelope']['payload'] for e in events(run) if e['envelope']['event_type']==kind]
        if len(found)!=1:raise ValueError('terminal prerequisite required: '+run+' '+kind)
        return found[0]
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    a=only(CHECKS,'external.confirmation_checks_completed')
    b=only(PYVISTA_CHECKS,'external.confirmation_checks_completed')
    if {r['instance_id'] for r in b['results']}!={'pyvista__pyvista-4311','pyvista__pyvista-4329','pyvista__pyvista-4853'}:
        raise ValueError('exact explicitly repaired PyVista checks required')
    checks={r['instance_id']:r for r in a['results']}
    checks.update({r['instance_id']:r for r in b['results']})
    selection=json.loads(Path('preflight/selection.json').read_bytes())
    metadata=json.loads(Path('preflight/metadata.json').read_bytes())
    eligibility={row['instance_id']:checks.get(row['instance_id'],{'qualified':False,'reason':'prior_source_or_environment_gate'})
                 for row in selection['selected']}
    chosen=select_tasks(selection,eligibility);blocks=paired_blocks(chosen)
    exports=only(EXPORTS,'external.confirmation_exports_completed')
    descriptors={r['instance_id']:r for r in exports['results'] if r['qualified']}
    _,registration=bound_worker_source(selection,metadata)
    sources={i:recover_export(events(descriptors[i]['export_run']),descriptors[i]) for i in chosen}
    issues={}
    selected_metadata={row['instance_id']:row for row in selection['selected']}
    for identity in chosen:
        item=json.loads(Path('public-issues',identity+'.json').read_bytes())
        raw=issue_blob(item['public_tree'],item['public_blob'])
        if (item['instance_id']!=identity or sha256(raw).hexdigest()!=item['sha256']
            or item['task_tree']!=selected_metadata[identity]['task_tree']
            or item['public_tree'].get('sha')!=item['task_tree'] or item['public_tree'].get('truncated') is not False
            or base64.b64decode(item['content_base64'],validate=True)!=raw):
            raise ValueError('exact pinned public issue bytes required')
        issues[identity]=raw.decode()
    # Image identity is recovered from the exact successful check dispatch.
    images={}
    for identity in chosen:
        source_run=PYVISTA_CHECKS if identity.startswith('pyvista__') else CHECKS
        case_run=source_run+'-'+identity
        rows=events(case_run)
        dispatches=[e['envelope']['payload'] for e in rows if e['envelope']['event_type']=='external.confirmation_check_dispatch']
        if not dispatches:
            original='external-windows-confirmation-public-proposal-controls-v1-20261018-'+identity
            dispatches=[e['envelope']['payload'] for e in events(original)
                        if e['envelope']['event_type']=='external.confirmation_check_dispatch']
        image_set={s for row in dispatches for s in row['command']
                   if s.startswith('swebench/') or (s.startswith('sha256:') and len(s)==71)}
        if len(image_set)!=1:raise ValueError('unique qualified image per task required')
        images[identity]=image_set.pop()
    program=stage_program();lane=Path('benchmarks/code_replay/history.py').read_text()
    manifest={'format':'atmem-confirmation-amended19-v1','seed':SEED,'tasks':chosen,'blocks':blocks,
        'eligibility':eligibility,'source_descriptors':{i:descriptors[i] for i in chosen},'images':images,
        'issues':issues,'stage_program':program,'lane_source':lane,'product_python':PYTHON,
        'wheel_sha256':'9900aa70371a1ec911b7215532711cbdc83da726198ca0eacf85bbf6054146c8',
        'max_context_bytes':4096,'extractor':EXTRACTOR,'model_calls':0,'inference_authorized_by_staging':False,
        'readiness':'prospective cohort lock; installed staging and bridge readiness remain mandatory; no task substitution on failure'}
    completed=set();blocked=set()
    if args.continue_unattempted:
        locks=[e['envelope']['payload'] for e in existing if e['envelope']['event_type']=='external.confirmation_manifest_frozen']
        stops=[e['envelope']['payload'] for e in existing if e['envelope']['event_type']=='external.confirmation_staging_stopped']
        staged=[e['envelope']['payload'] for e in existing if e['envelope']['event_type']=='external.confirmation_block_staged']
        if (len(locks)!=1 or canonical_json(locks[0])!=canonical_json(manifest) or len(stops)!=1
            or stops[0]['block']['slot']!=7 or stops[0].get('model_calls')!=0
            or len(staged)!=7 or {r['block']['slot'] for r in staged}!=set(range(7))):
            raise ValueError('only exact seven-success one-failure zero-model prefix may continue')
        if CASE_ROOT.is_symlink() or not CASE_ROOT.is_dir():raise ValueError('exact existing benchmark case root required')
        completed=set(range(7));blocked={7}
        save('external.confirmation_unattempted_continuation_planned',{'driver_source':Path(__file__).read_text(),
            'completed_blocks_not_repeated':sorted(completed),'failed_blocks_preserved':sorted(blocked),
            'stage_program_unchanged':True,'lane_unchanged':True,'model_calls':0,'inference_permitted':False})
    else:
        save('external.confirmation_manifest_frozen',manifest)
        CASE_ROOT.mkdir(mode=0o711,exist_ok=False)
    for block in blocks:
        identity=block['instance_id'];slot=block['slot'];source=sources[identity]
        if slot in completed or slot in blocked:continue
        task_run=RUN+'-block-'+str(slot)
        target=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=task_run)
        if target.inspect(principal,task_run):raise ValueError('block already staged')
        def retain(kind,payload):return target.capture(run_id=task_run,kind=kind,principal=principal,payload=payload)
        task={'instance_id':identity,'base_commit':source['base_commit'],'image_extras_sha256':source['image_extras_sha256']}
        worker=patch_bootstrap(task,operator_registration=registration,runtime_manifest=source['runtime_manifest'],result_transport='lzma-v2')
        placeholder='/dev/shm/ATMEM_CONFIRMATION_PRESET_PLACEHOLDER'
        server=server_bootstrap(placeholder,task,operator_registration=registration,runtime_manifest=source['runtime_manifest'],
            local_image_id=images[identity] if images[identity].startswith('sha256:') else None,
            result_transport='lzma-v2',compact_argv=True)
        thin_source={k:source[k] for k in ('base_commit','files_base64','modes')}
        preset={'image':images[identity],'worker_source':worker,'worker_sha256':sha256(worker.encode()).hexdigest(),
                'source':thin_source,'run_id':'operator-replaced','evidence_root':'operator-replaced'}
        job={'program':program,'root':str(CASE_ROOT/('block-'+str(slot))),'source':thin_source,
            'issue':issues[identity],'order':block['order'],'block_id':'confirmation19-'+str(slot),
            'extractor':EXTRACTOR,'lane_source':lane,'public_preset':preset,
            'server_template':server,'preset_placeholder':placeholder}
        retain('external.confirmation_stage_planned',{'block':block,'source_descriptor':descriptors[identity],
            'job_sha256':sha256(canonical_json(job).encode()).hexdigest(),'server_template':server,
            'public_worker_source':worker,'root':job['root'],'manifest_run':RUN,'model_calls':0})
        payload={'program':"import subprocess,sys;p=subprocess.run([job['python'],'-I','-c',\"import sys,json;job=json.load(sys.stdin);exec(job['program'])\"],input=job['stage_json'].encode());sys.exit(p.returncode)",
                 'python':PYTHON,'stage_json':json.dumps(job)}
        proc=subprocess.run(framed_command(),input=framed_input(payload),capture_output=True,timeout=300)
        streams={}
        for name,raw in [('stdout',proc.stdout),('stderr',proc.stderr)]:
            receipts=[]
            for offset in range(0,len(raw),3_000_000):
                receipts.append(retain('external.confirmation_stage_chunk',{'stream':name,'offset':offset,
                    'bytes_base64':base64.b64encode(raw[offset:offset+3_000_000]).decode()}))
            streams[name]={'bytes':len(raw),'sha256':sha256(raw).hexdigest(),'receipts':receipts}
        retain('external.confirmation_stage_transport',{'exit_code':proc.returncode,'streams':streams})
        if proc.returncode:
            save('external.confirmation_staging_stopped',{'block':block,'task_run':task_run,'exit_code':proc.returncode,'model_calls':0})
            if args.continue_unattempted:
                blocked.add(slot)
                print(json.dumps({'slot':slot,'instance_id':identity,'staging_failed':True,'model_calls':0}),flush=True)
                continue
            raise ValueError('installed staging failed; retained, no inference')
        value=json.loads(proc.stdout)
        cases={arm:{k:v for k,v in case.items() if k!='generation_zlib_base64'} for arm,case in value['cases'].items()}
        if (set(cases)!={'native','tools'} or not cases['tools']['database'] or not cases['tools']['atmem_home']
            or cases['native']['database'] is not None or cases['native']['atmem_home'] is not None
            or cases['native']['initial_commit']!=cases['tools']['initial_commit']):
            raise ValueError('paired source/home descriptors differ')
        result={'block':block,'task_run':task_run,'cases':cases,'transport':streams,'model_calls':0}
        save('external.confirmation_block_staged',result)
        completed.add(slot)
        print(json.dumps({'slot':slot,'instance_id':identity,'staged_blocks':len(completed),'model_calls':0}),flush=True)
    save('external.confirmation_staging_completed',{'blocks':len(completed),'cases':2*len(completed),'model_calls':0,
        'blocked_slots':sorted(blocked),'all_38_blocks_ready':not blocked and len(completed)==38,
        'public_mcp_and_sandbox_readiness':'pending; do not infer qualification from staged files'})


if __name__=='__main__':main()
