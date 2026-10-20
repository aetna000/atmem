"""Explicit CD3 profile over the exercised CD2 matched study, not a new stack."""
import ast
import inspect

from benchmarks.code_replay import query_nomination_screen as previous
from benchmarks.code_replay import public_selector_profile as selectors
from benchmarks.code_replay import literal_anchor_controls as controls
from benchmarks.code_replay.literal_anchor_preview import RUN as BUILD

PREFIX = 'external-windows-literal-anchor-development-'
CASE_ROOT = '/home/jt/atmem-benchmark-runtime-20261018/literal-anchor-development-stage-v1/block-'
SEED = 'atmem-literal-anchor-development-screen-20261018-v1'
CLUSTER_SEED = 'atmem-literal-anchor-cluster-audit-20261018-v1'


def reprofile(source):
    for old, new in (
        (previous.PREFIX, PREFIX),
        (previous.CASE_ROOT.removesuffix('/block-'), CASE_ROOT.removesuffix('/block-')),
        ('/sys/fs/cgroup/atmem-code-query-nomination-development-20261018',
         '/sys/fs/cgroup/atmem-code-literal-anchor-development-20261018'),
        (previous.SEED, SEED), (previous.CLUSTER_SEED, CLUSTER_SEED),
        ('query-nomination-development19-', 'literal-anchor-development19-'),
        ('atmem-query-nomination-development-execution-lock-v1', 'atmem-literal-anchor-development-execution-lock-v1'),
        ('CD2', 'CD3'),
    ):
        source = source.replace(old, new)
    ast.parse(source, feature_version=(3, 10))
    return source


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('exact exercised CD2 boundary required: '+old)
    return source.replace(old, new, 1)


def staging_source(source):
    source = reprofile(source)
    for old, new in ((repr(previous.BUILD), repr(BUILD)),
                     (repr(previous.QUALIFICATION), repr(controls.QUALIFY)),
                     (repr(previous.REPLAY), repr(controls.REPLAY))):
        source = replace_once(source, old, new)
    marker = "        slot=block['slot'];identity=block['instance_id'];source=sources[identity];plan=plans[slot]"
    source = replace_once(source, marker, marker+"\n        plan={**plan,\n"
        "            'server_template':corrected_program(plan['server_template'],role='server',validator_pair=FROZEN_VALIDATORS),\n"
        "            'public_worker_source':corrected_program(plan['public_worker_source'],role='worker',validator_pair=FROZEN_VALIDATORS)}")
    # Supplying the frozen pair avoids reading the old operator checkout's file.
    source = replace_once(source, "if __name__=='__main__':main()",
        inspect.getsource(selectors)+'\nFROZEN_VALIDATORS='+repr(selectors.validators())+"\nif __name__=='__main__':main()")
    ast.parse(source, feature_version=(3, 10))
    return source


def readiness_worker(original):
    source = replace_once(original, previous.CASE_ROOT, CASE_ROOT)
    source = replace_once(source, "'paths':[job['probe_path']]", "'paths':job['probe_paths']")
    marker = "started=time.monotonic()\nprocess=subprocess.run"
    addition = """for label,path in [('source',job['source_probe']),('traversal','../tests/test_one.py')]:
 requests.insert(2,{'jsonrpc':'2.0','id':'qualification-deny-'+label,'method':'tools/call','params':{
  'name':'run_public_tests','arguments':{'patch':job['probe_patch'],'paths':[path]}}})
"""
    source = replace_once(source, marker, addition+marker)
    source = replace_once(source, "result['qualified']=bool(public_ok and result.get('code_qualified',True)",
        "denials={r.get('id'):r.get('error',{}).get('code') for r in result['public_responses']}\n"
        "result['selector_denials_qualified']=all(denials.get('qualification-deny-'+label)==-32602 for label in ('source','traversal'))\n"
        "result['qualified']=bool(result['selector_denials_qualified'] and public_ok and result.get('code_qualified',True)")
    ast.parse(source, feature_version=(3, 10))
    return source


def readiness_source(source):
    from benchmarks.code_replay.windows_confirmation_checks import isolation_probe
    names = [n.name for n in ast.parse(isolation_probe('xarray')).body if isinstance(n, ast.FunctionDef)]
    if len(names) != 3:
        raise ValueError('three unchanged public isolation canaries required')
    namespace = {'__name__': 'cd2_readiness_profile'}
    exec(compile(source, '<original-CD2-readiness-definition>', 'exec'), namespace)
    worker = readiness_worker(namespace['worker_program']())
    source = reprofile(source)
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'worker_program')
    source = replace_once(source, ast.get_source_segment(source, node),
                          'def worker_program():\n    return '+repr(worker))
    marker = "        payload={'program':program,'case':case,'python':manifest['product_python'],"
    source = replace_once(source, marker,
        "        nested=repo=='pydata/xarray'\n"
        "        actual_probe='xarray/tests/test_atmem_public_boundary_20261018.py' if nested else PROBE_PATH\n"
        +marker)
    source = replace_once(source, "'probe_patch':probe_patch(MODULES[repo]),'probe_path':PROBE_PATH,'source_probe':probe,",
        "'probe_patch':probe_patch(MODULES[repo]).replace(PROBE_PATH,actual_probe),"
        "'probe_path':actual_probe,'probe_paths':[actual_probe+'::'+n for n in "+repr(names)+"] if nested else [actual_probe],'source_probe':probe,")
    ast.parse(source, feature_version=(3, 10))
    return source


def sources():
    old = previous.sources()
    return {name: staging_source(source) if name == 'staging' else
            readiness_source(source) if name == 'readiness' else reprofile(source)
            for name, source in old.items()}


def supporting_sources():
    return {name: reprofile(source) for name, source in previous.supporting_sources().items()}
