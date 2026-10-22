"""Execute a frozen private Dolphin task slice through the unchanged harness.

No task semantics, extraction, ranking or grading logic lives in this runner.
Product-owned engine selection is explicit; history and native app tools match
the saved baseline. Never packages a partial run as a 600-task submission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

from benchmarks.dolphinbench.adapter import AtMemAdapter
from benchmarks.dolphinbench.gateway import Gateway,save_new
from benchmarks.dolphinbench.judge import openrouter_judge
from benchmarks.dolphinbench.recording import BudgetLedger
from scripts.openrouter_azure_sol import load_key
from .dolphin_sample import select
from .grade_run import claim_budget,settle_budget
from .protocol import digest


def verify_checkpoint_retry(adapter,persona,checkpoint):
    """Retry only a read-only authority-lock collision, never a model call."""
    deadline=time.monotonic()+120
    while True:
        try:
            return adapter.verify_checkpoint(persona,checkpoint)
        except RuntimeError as exc:
            if str(exc)!='Hermes authority is busy; retry the operation' or time.monotonic()>=deadline:
                raise
            time.sleep(.5)


def resume_selection(parent_role,child_role,frozen,selected,*,expand_working_set=False):
    """Explicit fixed18 -> fixed60 continuation, never answer re-execution."""
    if type(expand_working_set) is not bool:
        raise ValueError('explicit working-set expansion flag required')
    if not expand_working_set:
        if parent_role!=child_role:raise ValueError('resume sample role changed')
        return None
    if (parent_role,child_role)!=('recurring-18','working-60'):
        raise ValueError('only fixed recurring18 to fixed working60 expansion is permitted')
    expected=set()
    for persona,ids in selected.items():
        if list(ids)!=list(frozen['working_60'][persona]):
            raise ValueError('child selection differs from frozen working set')
        source=frozen['recurring_stage_18'][persona]
        if not set(source)<=set(ids):raise ValueError('parent selection is not a frozen subset')
        expected.update((persona,str(task).zfill(3)) for task in source)
    if not expected:raise ValueError('nonempty frozen continuation required')
    return expected


def run(sample: Path, output: Path, env_file: Path, *, full: bool=False,
        variant: str='balanced-pools-v1',index_directory: Path|None=None,persona_filter: str|None=None,
        discovery: bool=False,application_workflow: bool=False,resume_from: Path|None=None,
        strict_application_contracts: bool=False,state_assessment: bool=False,source_time_frames: bool=False,
        source_bundles: bool=False, cap_usd: float|None=None, reference_soul: bool=False,
        initial_state_assessment: bool=False,app_python: Path|None=None,
        runtime_root: Path|None=None,initial_state_presentation: str='annotated-source',
        reader_model: str='openai/gpt-5.6-luna',expand_working_set: bool=False) -> None:
    from benchmarks.dolphinbench.subscription_service import subscription_reader_model
    subscription_reader_model(reader_model)
    if type(expand_working_set) is not bool or (expand_working_set and (not full or resume_from is None)):
        raise ValueError('working-set expansion requires full selection and a retained parent')
    if os.environ.get('ATMEM_HOME')!='/Volumes/AtMemDolphin/v3-full-r2-product-home':
        raise ValueError('original encrypted source home required')
    output=output.resolve()
    if not any(output.is_relative_to(p) for p in
               (Path('/Volumes/AtMemDolphin'),Path('/Volumes/AtMemBenchRuntime'))):
        raise ValueError('output must remain on a dedicated private benchmark volume')
    if output.exists():
        raise ValueError('fresh output required; completed executions are never rerolled')
    if initial_state_presentation not in {'annotated-source','dossier'}:
        raise ValueError('unknown initial evidence presentation')
    if initial_state_presentation=='dossier' and not (initial_state_assessment and discovery):
        raise ValueError('dossier presentation requires initial assessment and read-only inspection')
    upstream=Path('/Volumes/AtMemDolphin/upstream')
    app_python=app_python or Path('/private/tmp/atmem-dolphin-apps-v3-20261021/bin/python')
    runtime_root=runtime_root or Path('/private/tmp/atmem-dolphin-runtime-v3-20261021')
    if not app_python.is_file():raise ValueError('application interpreter is unavailable')
    from benchmarks.dolphinbench.python_runtime import qualify_python,qualify_application,qualify_application_repair
    python_runtimes={'controller':qualify_python(sys.executable),
                     'application':qualify_python(app_python)}
    application_packages=qualify_application(app_python)
    subprocess.run([str(app_python),'-c','import encodings,pydantic,mcp'],check=True,
                   stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    sys.path.append(str(upstream))
    from harness.runner import Runner,run_lock,save
    from harness.submission import read_release
    release=read_release(upstream)
    frozen=json.loads(sample.read_text())
    for key,value in select(release).items():
        if frozen[key]!=value:
            raise ValueError('task selection differs from frozen ID-only selector')
    if digest(release)!=frozen['corpus_digest']:
        raise ValueError('source corpus identity changed')
    selected=frozen['working_60' if full else 'recurring_stage_18']
    if persona_filter is not None:
        selected={persona_filter:selected[persona_filter]}
    souls,host_identity={},None
    if reference_soul:
        from .reference_host import reference_souls
        souls,host_identity=reference_souls(upstream)
        if set(selected)-set(souls):raise ValueError('selected persona lacks official host identity')
    if variant=='source-coherent-v1':
        if index_directory is None or any(not (index_directory/(p+'-ready.json')).is_file() for p in selected):
            raise ValueError('all selected persona semantic caches must be ready before dispatch')
    cap=(8 if state_assessment else 5) if persona_filter is not None else (24 if state_assessment else 10)
    if cap_usd is not None:
        if type(cap_usd) not in (int,float) or not math.isfinite(cap_usd) or not 0<cap_usd<=cap:
            raise ValueError('explicit child cap must be finite, positive and no larger than the profile limit')
        cap=cap_usd
    identity={'format':'private-dolphin-stage-v1','cap_usd':cap,'user_total_ceiling_usd':250,
        'source_commit':frozen['upstream_commit'],'corpus_digest':frozen['corpus_digest'],
        'sample_sha256':hashlib.sha256(sample.read_bytes()).hexdigest(),
        'sample_role':'working-60' if full else 'recurring-18',
        'context_engine_variant':variant,'original_frozen_histories':True,
        'read_only_discovery':discovery,'application_workflow':application_workflow,
        'strict_application_contracts':strict_application_contracts,
        'source_time_frames':source_time_frames,
        'source_bundles':source_bundles,
        'initial_state_assessment':initial_state_assessment,
        'initial_state_presentation':initial_state_presentation,
        'reference_host_identity':host_identity,
        'state_assessment':({'model':'openai/gpt-5.6-sol','reasoning':'medium',
                              'role':'AtBot source-state classification, not reader or grader',
                              'explicit_remote_egress':True,'output_token_cap':4000} if state_assessment else None),
        'discovery_budget':({'max_operations':8,'max_bytes':96000,'max_response_bytes':16000,
                              'lease_seconds':900,'per_operation_ms':120000} if discovery else None),
        'host_policy_changed_not_memory_only_comparison':bool(application_workflow or strict_application_contracts or reference_soul),
        'selected_personas':list(selected),
        'execution_paths':{'app_python':str(app_python),'runtime_root':str(runtime_root)},
        'python_runtimes':python_runtimes,
        'application_packages':application_packages,
        'agent':{'model':reader_model,'reasoning':'high','max_turns':60,'context_length':1050000},
        'judge':{'model':'gpt-5.6-sol','reasoning':'medium','transport':'Azure-only OpenRouter'},
        'product_source':{p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in Path('atmem').rglob('*.py')},
        'companion_source':{p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in Path('packages/atbot/src').rglob('*.py')},
        'source_execution_not_release_artifact':True,'ready_for_600':False}
    inherited=[]
    if resume_from is not None:
        resume_from=resume_from.resolve()
        if not any(resume_from.is_relative_to(p) for p in
                   (Path('/Volumes/AtMemDolphin'),Path('/Volumes/AtMemBenchRuntime'))):
            raise ValueError('resume evidence must remain on a private benchmark volume')
        parent=json.loads((resume_from/'stage-manifest.json').read_text())
        if parent.get('companion_source')!=identity['companion_source']:
            raise ValueError('resume companion source changed')
        expected_parent=resume_selection(parent.get('sample_role'),identity['sample_role'],
            frozen,selected,expand_working_set=expand_working_set)
        if expand_working_set:
            if (not (resume_from/'result.json').is_file()
                    or not (resume_from/'costs-final.json').is_file()
                    or (resume_from/'failure.json').exists()):
                raise ValueError('expansion requires a terminal complete parent, not an interrupted attempt')
            if parent.get('companion_source')!=identity['companion_source']:
                raise ValueError('resume companion source changed')
        if parent.get('strict_application_contracts',False)!=strict_application_contracts:
            raise ValueError('resume application argument policy changed')
        if parent.get('state_assessment')!=identity['state_assessment']:
            raise ValueError('resume state assessment profile changed')
        if parent.get('source_time_frames',False)!=source_time_frames:
            raise ValueError('resume temporal frame profile changed')
        if parent.get('source_bundles',False)!=source_bundles:
            raise ValueError('resume source bundle profile changed')
        if parent.get('reference_host_identity')!=host_identity:
            raise ValueError('resume native host identity changed')
        if parent.get('initial_state_assessment',False)!=initial_state_assessment:
            raise ValueError('resume initial assessment profile changed')
        if parent.get('initial_state_presentation','annotated-source')!=initial_state_presentation:
            raise ValueError('resume initial evidence presentation changed')
        legacy_paths={'app_python':'/private/tmp/atmem-dolphin-apps-v3-20261021/bin/python',
                      'runtime_root':'/private/tmp/atmem-dolphin-runtime-v3-20261021'}
        previous_paths=parent.get('execution_paths',legacy_paths)
        if previous_paths!=identity['execution_paths']:
            if previous_paths['runtime_root']!=str(runtime_root):
                raise ValueError('resume native runtime changed; use a fresh qualified condition')
            identity['application_runtime_repair']=qualify_application_repair(
                previous_paths['app_python'],app_python)
        for key in ('source_commit','corpus_digest','sample_sha256',
                    'context_engine_variant','original_frozen_histories','agent','judge',
                    'product_source','read_only_discovery','application_workflow'):
            if parent[key]!=identity[key]:raise ValueError('resume source/config changed')
        if list((resume_from/'tests').rglob('*.inflight')):
            raise ValueError('uncertain parent execution; reconcile before resuming')
        for path in (resume_from/'tests').rglob('*.json'):
            persona,task_id=path.parent.name,path.stem
            original=next((i for i in selected.get(persona,()) if i.zfill(3)==task_id),None)
            if original is None:raise ValueError('parent task outside frozen selection')
            grade_path=resume_from/'grades'/persona/path.name
            grade=json.loads(grade_path.read_text())
            if not grade['checks'] or any(type(c['passed']) is not bool for c in grade['checks']):
                raise ValueError('invalid saved parent grade')
            inherited.append({'persona':persona,'task_id':original,
                'passed':all(c['passed'] for c in grade['checks']),
                'inherited_from':str(resume_from),
                'execution_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'grade_sha256':hashlib.sha256(grade_path.read_bytes()).hexdigest()})
        if not inherited:raise ValueError('resume requires completed retained executions')
        if expected_parent is not None:
            observed={(r['persona'],r['task_id'].zfill(3)) for r in inherited}
            if observed!=expected_parent or len(observed)!=len(inherited):
                raise ValueError('all fixed parent executions must be inherited exactly once')
            if json.loads((resume_from/'result.json').read_text()).get('tasks')!=len(expected_parent):
                raise ValueError('parent completion denominator differs from fixed subset')
            identity['selection_expansion']={'from':'recurring-18','to':'working-60',
                'all_parent_executions_reused':True,'parent_actions_reexecuted':False}
        identity['inherited_executions']=inherited
    master=Path('/Volumes/AtMemDolphin/retrieval-2310-budget.db')
    claim_budget(master,output.name,cap_usd=str(cap))
    output.mkdir(mode=0o700)
    token=secrets.token_urlsafe(32)
    os.environ['ATMEM_SUBSCRIPTION_PROXY_TOKEN']=token
    options={'campaign_identity':identity,'env_file':str(env_file), 'memory_engine':'context-v3',
        'ingestion_mode':'source-episode','memory_delivery':'native-product-api',
        **({'context_engine_variant':variant} if variant!='deterministic-control' else {}),
        'read_only_discovery':discovery,'application_workflow':application_workflow,
        'strict_application_contracts':strict_application_contracts,
        'source_time_frames':source_time_frames,
        'source_bundles':source_bundles,
        'initial_state_presentation':initial_state_presentation,
        'native_souls':souls,
        **({'context_index_directory':str(index_directory)} if index_directory is not None else {}),
        'baseline_memory_root':'/Volumes/AtMemDolphin/campaign-atmem-v3-full-r2-20261021/memory',
        'app_python':str(app_python),
        'runtime_root':str(runtime_root),
        'subscription_endpoint':'listener-pending'}
    listener=output/'subscription/listener.json'
    service=Path(__file__).resolve().parents[2]/'benchmarks/dolphinbench/subscription_service.py'
    adapter=None
    gateway=None
    process=None
    assessment_gateway=None
    initial_assessment_gateway=None
    with (output/'subscription.log').open('x') as log:
        try:
            adapter=AtMemAdapter(options,output)
            # Runner must initialize its identity before model attempts exist.
            with run_lock(output):
                runner=Runner(release,output,adapter,identity=adapter.identity(),release_root=upstream,allow_paid=False)
                runner.allow_paid=True
            save_new(output/'stage-manifest.json',identity)
            BudgetLedger(adapter.ledger,cap_usd=cap,identity=identity).close()
            process=subprocess.Popen([
                '/Users/javadtaghia/.hermes/tools/python-3.14.7+20260901-darwin-arm64/bin/python3.14',
                '-I',str(service),'--output',str(output/'subscription'),
                '--listener-file',str(listener),'--reasoning-effort','high','--model',reader_model],
                cwd='/Volumes/AtMemDolphin/tmp',env={**os.environ,'HERMES_HOME':'/Users/javadtaghia/.hermes',
                'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError('subscription unavailable; no API fallback')
                if listener.exists():
                    options['subscription_endpoint']=json.loads(listener.read_text())['endpoint']
                    break
                time.sleep(.25)
            else:
                raise RuntimeError('subscription startup timed out')
            checkpoint_root=Path('/Volumes/AtMemDolphin/campaign-atmem-v3-full-r2-20261021/checkpoints')
            if state_assessment or initial_state_assessment:
                if state_assessment and not discovery:raise ValueError('state assessment requires explicit discovery')
                from .assessor_provider import AtBotStateAssessor,AtBotInitialStateAssessor,AtBotSourceDossierAssessor
                if state_assessment:
                    assessment_gateway=Gateway(key=load_key(env_file),output=output/'assessment-calls',
                        ledger_path=adapter.ledger,campaign_identity=identity,cap_usd=cap,phase='state-assessment',
                        model='openai/gpt-5.6-sol',input_per_million=5,output_per_million=30,output_token_cap=4000).start()
                    options['state_assessor']=AtBotStateAssessor(assessment_gateway)
                if initial_state_assessment:
                    initial_assessment_gateway=Gateway(key=load_key(env_file),output=output/'initial-assessment-calls',
                        ledger_path=adapter.ledger,campaign_identity=identity,cap_usd=cap,phase='initial-state-assessment',
                        model='openai/gpt-5.6-sol',input_per_million=5,output_per_million=30,output_token_cap=4000).start()
                    selected_assessor=(AtBotSourceDossierAssessor if initial_state_presentation=='dossier'
                                       else AtBotInitialStateAssessor)
                    options['initial_state_assessor']=selected_assessor(initial_assessment_gateway)
            for persona in selected:
                verify_checkpoint_retry(adapter,persona,json.loads((checkpoint_root/f'{persona}.json').read_text()))
            gateway=Gateway(key=load_key(env_file),output=output/'judge-calls',ledger_path=adapter.ledger,
                campaign_identity=identity,cap_usd=cap,phase='judge',model='openai/gpt-5.6-sol',
                input_per_million=5,output_per_million=30,output_token_cap=8000).start()
            results=list(inherited)
            completed={(r['persona'],r['task_id']) for r in inherited}
            with openrouter_judge(gateway),run_lock(output):
                for persona,ids in selected.items():
                    for task in release[persona]['tests']:
                        if str(task['id']) not in ids:
                            continue
                        if (persona,str(task['id'])) in completed:
                            continue
                        evidence=runner._execute('tests',persona,task)
                        grade=runner._grade(task,evidence)
                        save(runner._path('grades',persona,str(task['id']).zfill(3)),grade)
                        verify_checkpoint_retry(adapter,persona,json.loads((checkpoint_root/f'{persona}.json').read_text()))
                        row={'persona':persona,'task_id':str(task['id']),
                             'passed':all(c['passed'] for c in grade['checks'])}
                        results.append(row)
                        save_new(output/'progress'/f'{len(results):03d}.json',row)
                        print(json.dumps({'completed':len(results),'total':sum(map(len,selected.values())),
                                          'passed':sum(r['passed'] for r in results)}),flush=True)
            save_new(output/'result.json',{'tasks':len(results),'passed':sum(r['passed'] for r in results),
                'results':results,'ready_for_600':False,'partial_run_not_submission':True})
        except BaseException as exc:
            save_new(output/'failure.json',{'type':type(exc).__name__,'detail':str(exc)[:300],
                                           'all_evidence_preserved':True})
            raise
        finally:
            if gateway is not None:
                gateway.stop()
            if assessment_gateway is not None:
                assessment_gateway.stop()
            if initial_assessment_gateway is not None:
                initial_assessment_gateway.stop()
            if adapter is not None:
                adapter.stop()
            if process is not None:
                process.terminate()
                try: process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=5)
            if (output/'budget.db').exists():
                book=BudgetLedger(output/'budget.db',cap_usd=cap,identity=identity)
                try:
                    save_new(output/'costs-final.json',book.totals())
                    amount=book.connection.execute("SELECT COALESCE(SUM(CASE WHEN state IN ('completed','overrun') THEN actual WHEN state='reserved' THEN reserved ELSE 0 END),0) FROM calls").fetchone()[0]
                    settle_budget(master,output.name,amount)
                finally: book.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sample',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--env-file',type=Path,required=True)
    parser.add_argument('--full-working-set',action='store_true')
    parser.add_argument('--variant',choices=('deterministic-control','balanced-pools-v1','source-coherent-v1'),default='balanced-pools-v1')
    parser.add_argument('--index-directory',type=Path)
    parser.add_argument('--persona',choices=('alex','morgan','riley'))
    parser.add_argument('--discovery',action='store_true')
    parser.add_argument('--application-workflow',action='store_true')
    parser.add_argument('--resume-from',type=Path)
    parser.add_argument('--expand-working-set',action='store_true')
    parser.add_argument('--strict-application-contracts',action='store_true')
    parser.add_argument('--state-assessment',action='store_true')
    parser.add_argument('--source-time-frames',action='store_true')
    parser.add_argument('--source-bundles',action='store_true')
    parser.add_argument('--cap-usd',type=float)
    parser.add_argument('--reference-soul',action='store_true')
    parser.add_argument('--initial-state-assessment',action='store_true')
    parser.add_argument('--app-python',type=Path)
    parser.add_argument('--runtime-root',type=Path)
    parser.add_argument('--initial-state-presentation',choices=('annotated-source','dossier'),default='annotated-source')
    from benchmarks.dolphinbench.subscription_service import READER_MODELS
    parser.add_argument('--reader-model',choices=READER_MODELS,default=READER_MODELS[0])
    args=parser.parse_args()
    run(args.sample,args.output,args.env_file,full=args.full_working_set,
        variant=args.variant,index_directory=args.index_directory,persona_filter=args.persona,
        discovery=args.discovery,application_workflow=args.application_workflow,resume_from=args.resume_from,
        strict_application_contracts=args.strict_application_contracts,state_assessment=args.state_assessment,
        source_time_frames=args.source_time_frames,source_bundles=args.source_bundles,cap_usd=args.cap_usd,
        reference_soul=args.reference_soul,initial_state_assessment=args.initial_state_assessment,
        app_python=args.app_python,runtime_root=args.runtime_root,
        initial_state_presentation=args.initial_state_presentation,reader_model=args.reader_model,
        expand_working_set=args.expand_working_set)


if __name__=='__main__': main()
