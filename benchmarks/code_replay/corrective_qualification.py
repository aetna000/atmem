"""Reuse the installed real-source qualification with an explicit corrective build."""
import ast
import inspect

RUN = 'external-windows-typed-query-qualification-v1-20261018'
BUILD = 'external-windows-product-build-typed-query-v1-20261018'
ROOT = '/home/jt/atmem-benchmark-runtime-20261018/typed-query-qualification-v1/'
CONTINUATION = RUN+'-mcp-import-continuation'


def owned_state_continuation_source(original):
    """Scoped Git ownership repair for the exact retained public workspaces."""
    result = continuation_source(original)
    changes = {
        'RUN='+repr(CONTINUATION): 'RUN='+repr(RUN+'-owned-state-continuation'),
        "prior='external-windows-typed-query-qualification-v1-20261018-local-transport'":
            'prior='+repr(CONTINUATION),
        '    require_mcp_import_failure(transports,errors)':
            "    if (len(transports)!=5 or len(errors)!=5\n"
            "            or any(t['exit_code']!=1 or t['streams']['stdout']['bytes']!=0 for t in transports)\n"
            "            or any(not raw.endswith(b'returned non-zero exit status 128.\\n')\n"
            "                   or b\"'status', '--porcelain']\" not in raw for raw in errors)):\n"
            "        raise ValueError('exact five pre-database Git ownership failures required')",
        "if git('status','--porcelain'):raise ValueError('retained source is dirty')":
            "if workspace.stat().st_uid!=1000:raise ValueError('exact retained benchmark ownership required')\n"
            "os.environ.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='safe.directory',GIT_CONFIG_VALUE_0=str(workspace))\n"
            "if git('status','--porcelain'):raise ValueError('retained source is dirty')",
    }
    for before, after in changes.items():
        if result.count(before) != 1:
            raise ValueError('exact stopped continuation required: '+before)
        result = result.replace(before, after)
    ast.parse(result, feature_version=(3, 10))
    return result


def require_mcp_import_failure(transports, stderr):
    if (len(transports) != 5 or len(stderr) != 5
            or any(t['exit_code'] != 1 or t['streams']['stdout']['bytes'] != 0 for t in transports)
            or any(not raw.endswith(b"NameError: name 'Path' is not defined. Did you mean: 'path'?\n")
                   or b'line 4, in configuration' not in raw for raw in stderr)):
        raise ValueError('exact five post-extraction configuration failures required')


def continuation_source(original):
    """Keep the failed runs, recheck existing state, and finish the MCP control."""
    result = qualification_source(original)
    namespace = {'__name__': 'continuation_definition'}
    exec(compile(result, '<qualified-source-definition>', 'exec'), namespace)
    program = namespace['PROGRAM']
    if result.count(program) != 1:
        raise ValueError('exact original raw worker required')
    result = result.replace(program, reuse_completed_extraction(program))
    result = result.replace(repr(RUN), repr(CONTINUATION))
    result = result.replace(repr(ROOT), repr(ROOT.replace('-v1/', '-local-transport-v1/')))
    marker = "if __name__=='__main__':main()"
    guard = inspect.getsource(require_mcp_import_failure)+r'''
def prior_failure_guard():
    from atmem.evidence import EvidenceScope,EvidencePrincipal,EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    prior='external-windows-typed-query-qualification-v1-20261018-local-transport'
    vault=operational_evidence(EVIDENCE_ROOT,vault_id='confirmation-v1',scope=scope,writing_run=prior)
    ends=[e['envelope']['payload'] for e in vault.inspect(principal,prior)
          if e['envelope']['event_type']=='external.compatibility_qualification_completed']
    if (len(ends)!=1 or ends[0]['qualified'] is not False or ends[0]['model_calls']!=0
            or len(ends[0]['results'])!=5):raise ValueError('terminal failed qualification required')
    transports=[];errors=[]
    for identity in IDENTITIES:
        events=vault.inspect(principal,prior+'-'+identity)
        rows=[e['envelope']['payload'] for e in events
              if e['envelope']['event_type']=='external.compatibility_case_transport']
        chunks=[e['envelope']['payload'] for e in events
                if e['envelope']['event_type']=='external.compatibility_case_chunk'
                and e['envelope']['payload']['stream']=='stderr']
        if len(rows)!=1 or len(chunks)!=1:raise ValueError('exact original failed transport required')
        raw=base64.b64decode(chunks[0]['bytes_base64'],validate=True)
        if (chunks[0]['offset']!=0 or sha256(raw).hexdigest()!=rows[0]['streams']['stderr']['sha256']
                or len(raw)!=rows[0]['streams']['stderr']['bytes']):raise ValueError('original failure bytes differ')
        transports.extend(rows);errors.append(raw)
    require_mcp_import_failure(transports,errors)
'''
    result = result.replace(marker, guard+"\nif __name__=='__main__':\n    prior_failure_guard()\n    main()")
    planned = "'worker_source':PROGRAM,"
    if result.count(planned) != 2:
        raise ValueError('both full worker capture boundaries required')
    result = result.replace(planned, planned+"'configuration_source':job['configuration_source'],")
    ast.parse(result, feature_version=(3, 10))
    return result


def configuration_source(helpers):
    """Function-only runner helpers require their module imports in a new namespace."""
    required = {'configuration', 'arguments'}
    nodes = ast.parse(helpers).body
    if {n.name for n in nodes if isinstance(n, ast.FunctionDef)} != required:
        raise ValueError('exact read-only MCP helper functions required')
    return 'import json\nfrom pathlib import Path\n'+helpers


def reuse_completed_extraction(program):
    """Recheck prior state; never rebuild source or extract after MCP setup failure."""
    changes = {
        "root=Path(job['root']);root.mkdir(mode=0o711,exist_ok=False)":
            "root=Path(job['root']);assert root.is_dir() and not root.is_symlink()",
        "workspace=root/'workspace';workspace.mkdir(mode=0o700)":
            "workspace=root/'workspace';assert workspace.is_dir() and not workspace.is_symlink()",
        " target=workspace/name;target.parent.mkdir(parents=True,exist_ok=True)\n target.write_bytes(base64.b64decode(encoded,validate=True));target.chmod(0o755 if job['source']['modes'][name]=='100755' else 0o644)":
            " target=workspace/name\n if target.is_symlink() or target.read_bytes()!=base64.b64decode(encoded,validate=True):raise ValueError('retained source differs')",
        "git('init','--quiet');git('add','--force','--all');git('-c','user.name=AtMem Benchmark','-c','user.email=benchmark@invalid','commit','--quiet','-m','Public base snapshot only; no upstream history')":
            "if git('status','--porcelain'):raise ValueError('retained source is dirty')",
        "(root/'atmem-home').mkdir(mode=0o700)": "assert (root/'atmem-home').is_dir()",
        "database=root/'atmem-home/memory.db';HouseholdApplication.initialize(database,encrypted=True)":
            "database=root/'atmem-home/memory.db';assert database.is_file()",
        " prepared=lane.prepare(run_id=job['identity']+'-compatibility'":
            " from atmem.knowledge.worker import ExtractionWorker\n"
            " if lane.knowledge.index(str(workspace),ExtractionWorker(job['extractor']))['status']!='unchanged':raise ValueError('retained extraction is not current')\n"
            " prepared=lane.prepare(run_id=job['identity']+'-mcp-import-continuation'",
    }
    result = program
    for before, after in changes.items():
        if result.count(before) != 1:
            raise ValueError('exact completed extraction worker required: '+before)
        result = result.replace(before, after)
    ast.parse(result, feature_version=(3, 10))
    return result


def require_transport_only_failure(transports, stderr, roots_exist):
    """Resume only proved SSH refusal before any installed worker could start."""
    if (len(transports) != 5 or len(stderr) != 5 or any(roots_exist)
            or any(t['exit_code'] != 255 or t['streams']['stdout']['bytes'] != 0 for t in transports)
            or any(raw != b'Host key verification failed.\r\n' for raw in stderr)):
        raise ValueError('exact five pre-worker transport refusals required')


def qualification_source(original):
    """Only change build/root identities and add a foreign-scope denial control."""
    changes = {
        "RUN='external-windows-source-storage-qualification-v1-20261018'": 'RUN='+repr(RUN),
        "'external-windows-product-build-source-storage-v1-20261018','external.compatibility_build_completed'":
            repr(BUILD)+",'external.corrective_build_completed'",
        "'/home/jt/atmem-benchmark-runtime-20261018/source-storage-qualification-v1/'": repr(ROOT),
        " generation=lane.knowledge.current(str(workspace))":
            " from dataclasses import replace\n"
            " foreign=replace(lane.scope,agent_id=lane.scope.agent_id+'-unauthorized')\n"
            " try:lane.knowledge.authorize(foreign)\n"
            " except PermissionError:pass\n"
            " else:raise ValueError('foreign scope accepted')\n"
            " generation=lane.knowledge.current(str(workspace))",
        "'audit_chain_valid':True,'model_calls':0":
            "'audit_chain_valid':True,'foreign_scope_denied':True,'model_calls':0",
    }
    result = original
    for before, after in changes.items():
        if result.count(before) != 1:
            raise ValueError('qualification adapter prerequisite differs: '+before)
        result = result.replace(before, after)
    ast.parse(result, feature_version=(3, 10))
    return result
