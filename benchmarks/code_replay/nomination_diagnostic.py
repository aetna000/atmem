"""Reusable recorded source-chain replay for the next query nomination change."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import sys

PREFIX = 'external-windows-corrective-development-'
RUN = PREFIX+'reference-diagnostic-v1-20261018'
LAYOUT = PREFIX+'layout-diagnostic-v1-20261018'
LOCATOR_RUN = PREFIX+'source-location-diagnostic-v1-20261018'


def call_delta(previous, candidate):
    nodes = [n for n in ast.parse(candidate).body if isinstance(n, ast.FunctionDef) and n.name == '_query_call_names']
    if len(nodes) != 1: raise ValueError('one bounded call-reference helper required')
    helper = ast.get_source_segment(candidate, nodes[0])
    old = '    bare = set(re.findall(r"(?<![\\w.])\\b([A-Za-z_]\\w*)\\s*\\(", task))'
    new = '    bare = _query_call_names(task)'
    if previous.count(old) != 1 or candidate.count(new) != 1:
        raise ValueError('exact bare-call binding required')
    if candidate.replace(helper+'\n\n', '', 1).replace(new, old, 1) != previous:
        raise ValueError('only call helper and bare-call binding may differ')
    return helper


def locator_delta(previous, candidate):
    nodes = [n for n in ast.parse(candidate).body if isinstance(n, ast.FunctionDef) and n.name == '_query_source_locations']
    if len(nodes) != 1: raise ValueError('one bounded source-location helper required')
    helper = ast.get_source_segment(candidate, nodes[0])
    changes = [
        ('    candidates = []', '    locations = _query_source_locations(task, sources)\n    candidates = []'),
        ('                           "class": isinstance(node, ast.ClassDef), "node": node})',
         '                           "class": isinstance(node, ast.ClassDef), "node": node,\n'
         '                           "location_span": end - start if node is not None and any(\n'
         '                               start <= first <= last <= end for first, last in locations.get(path, ())) else None})'),
        ('    def lexical(row):\n        if row["explicit"]:',
         '    def lexical(row):\n        if row["location_span"] is not None:\n'
         '            return 20000 + 1000 / (1 + row["location_span"])\n        if row["explicit"]:'),
    ]
    restored = candidate.replace(helper+'\n\n', '', 1)
    for old, new in changes:
        if previous.count(old) != 1 or restored.count(new) != 1:
            raise ValueError('exact source-location nomination binding required')
        restored = restored.replace(new, old, 1)
    if restored != previous:
        raise ValueError('only location helper and declared nomination bindings may change')
    return helper


def audit(archive, output, keys, original, previous, candidate, *, profile='reference', layout_source=None):
    from benchmarks.code_replay import corrective_layout_diagnostic as replay
    def chain(baseline, final):
        if profile == 'reference':
            replay.allowed_delta(baseline, previous)
            call_delta(previous, final)
        elif profile == 'locations':
            replay.allowed_delta(baseline, layout_source)
            call_delta(layout_source, previous)
            locator_delta(previous, final)
        else:
            raise ValueError('unknown declared source-chain profile')
    return replay.audit(archive, output, keys, original, candidate, validate=chain)


def main():
    import os
    import subprocess
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.corrective_transfer import OUTPUT, KEYS
    from benchmarks.code_replay import corrective_layout_diagnostic as replay
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    args = sys.argv[1:]
    if len(args) not in (1, 2) or args[0] not in ('plan', 'run'):
        raise ValueError('use plan/run with an optional declared profile')
    phase, profile = args[0], args[1] if len(args) == 2 else 'reference'
    if profile not in ('reference', 'locations'): raise ValueError('unknown nomination profile')
    run = RUN if profile == 'reference' else LOCATOR_RUN
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=run)
    def of(rows, kind): return [r['envelope']['payload'] for r in rows if r['envelope']['event_type'] == kind]
    def save(kind, payload): return vault.capture(run_id=run, kind=kind, principal=principal, payload=payload)
    rows = vault.inspect(principal, run); current = Path('atmem/knowledge/code/packing.py').read_text()
    if phase == 'plan':
        if rows: raise ValueError('fresh source-chain plan required')
        if profile == 'reference':
            parent = vault.inspect(principal, LAYOUT)
            parent_plan, = of(parent, 'external.layout_diagnostic_planned')
            started, = of(parent, 'external.layout_diagnostic_started')
            done, = of(parent, 'external.layout_diagnostic_completed')
            original = parent_plan['baseline_source']; layout_source = None
            replay.allowed_delta(original, current)
            parent_run, protocol = LAYOUT, 'query-reference-ranking-v1.md'
        else:
            parent = vault.inspect(principal, RUN)
            parent_plan, = of(parent, 'external.nomination_diagnostic_planned')
            started, = of(parent, 'external.nomination_diagnostic_started')
            done, = of(parent, 'external.nomination_diagnostic_completed')
            original, layout_source = parent_plan['original_source'], parent_plan['previous_source']
            replay.allowed_delta(original, layout_source)
            call_delta(layout_source, current)
            parent_run, protocol = RUN, 'query-source-location-v1.md'
        if (done['summary']['identities'] != 19 or not done['summary']['all_original_packs_reproduced']
                or current != started['candidate_source']):
            raise ValueError('complete matching previous source/diagnostic required')
        save('external.nomination_diagnostic_planned', {'driver_source': Path(__file__).read_text(),
            'replay_source': Path(replay.__file__).read_text(), 'original_source': original,
            'previous_source': current, 'previous_sha256': sha256(current.encode()).hexdigest(),
            'previous_diagnostic_run': parent_run, 'layout_source': layout_source, 'profile': profile,
            'protocol': (Path('specs/042-atmem-code')/protocol).read_text(),
            'models_or_grades': 0, 'selection': 'all nineteen original CD1 issues'})
        print('Complete previous source and prospective '+profile+' protocol retained.'); return
    if len(rows) != 1 or rows[0]['envelope']['event_type'] != 'external.nomination_diagnostic_planned':
        raise ValueError('exact unexecuted source-chain plan required')
    plan = rows[0]['envelope']['payload']
    if Path(__file__).read_text() != plan['driver_source']: raise ValueError('driver changed after planning')
    if Path(replay.__file__).read_text() != plan['replay_source']: raise ValueError('replay changed after planning')
    if plan.get('profile', 'reference') != profile: raise ValueError('planned profile differs')
    (call_delta if profile == 'reference' else locator_delta)(plan['previous_source'], current)
    transfer = vault.inspect(principal, PREFIX+'MEM-transfer-recovery-v1-20261018')
    end, = of(transfer, 'external.v3_MEM_recovery_completed')
    if end['proof']['request_audit']['verified_original_requests'] != 38: raise ValueError('independent archive recovery required')
    transfer_plan, = of(transfer, 'external.v3_MEM_transfer_recovery_planned')
    bootstrap = transfer_plan['standalone_recovery_program']; marker = '\nproof=archive.recover_collection'
    if bootstrap.count(marker) != 1: raise ValueError('exact verified reader bootstrap required')
    source = Path(__file__).read_text(); program = bootstrap[:bootstrap.index(marker)]
    program += '\nm=types.ModuleType("benchmarks.code_replay.corrective_layout_diagnostic");sys.modules[m.__name__]=m\n'
    program += 'exec(compile('+repr(plan['replay_source'])+",'<retained-generic-static-replay>','exec'),m.__dict__)\n"
    program += '\nns={"__name__":"reference_reader"};exec(compile('+repr(source)+",'<retained-reference-diagnostic>','exec'),ns)\n"
    program += 'print(json.dumps(ns["audit"](archive,Path('+repr(OUTPUT)+'),Path('+repr(KEYS)+'),'+repr(plan['original_source'])+','+repr(plan['previous_source'])+','+repr(current)+',profile='+repr(profile)+',layout_source='+repr(plan.get('layout_source'))+')),flush=True)\n'
    save('external.nomination_diagnostic_started', {'candidate_source': current,
        'candidate_sha256': sha256(current.encode()).hexdigest(), 'reader_program': program,
        'source_vault_access': False})
    loader = "import json,sys;exec(compile(json.load(sys.stdin)['program'],'<recorded-stdin-reader>','exec'))"
    result = subprocess.run([sys.executable, '-c', loader], input=json.dumps({'program': program}).encode(),
                            capture_output=True, timeout=3600)
    if result.returncode:
        save('external.nomination_diagnostic_failed', {'exit_code': result.returncode,
            'stderr': result.stderr.decode(errors='replace'), 'no_automatic_retry': True})
        raise RuntimeError('source-chain diagnostic failed; inspect retained result')
    value = json.loads(result.stdout)
    save('external.nomination_diagnostic_completed', value)
    print(json.dumps(value['summary']), flush=True)


if __name__ == '__main__': main()
