"""Record and replay a generic layout-ranking correction; never run a model."""
import ast
import contextlib
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import types

PREFIX = 'external-windows-corrective-development-'
RUN = PREFIX+'layout-diagnostic-v1-20261018'
BASELINE = '159e4b0f1c52c3bd0752d38ddaa5e2764927b4daa39adc400baeaeddb2d85042'


def allowed_delta(baseline, candidate):
    helpers = [node for node in ast.parse(candidate).body
               if isinstance(node, ast.FunctionDef) and node.name == '_query_term_weights']
    if len(helpers) != 1: raise ValueError('one layout helper required')
    helper = ast.get_source_segment(candidate, helpers[0])
    old = '    weights = {t: 1 + math.log(1 + len(candidates) / (1 + frequency[t])) for t in terms}'
    new = '    query_weights = _query_term_weights(task)\n    weights = {t: query_weights[t] * (1 + math.log(1 + len(candidates) / (1 + frequency[t]))) for t in terms}'
    if candidate.count(new) != 1 or baseline.count(old) != 1:
        raise ValueError('exact query-weight binding required')
    restored = candidate.replace(helper+'\n\n', '', 1).replace(new, old, 1)
    if restored != baseline:
        raise ValueError('only layout helper and lexical query weights may change')
    return helper


def lexical_inspector(source, namespace):
    function = next(node for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef) and node.name == 'pack_generation')
    text = ast.get_source_segment(source, function)
    marker = '    executable = [r for r in candidates'
    if text.count(marker) != 1: raise ValueError('exact lexical boundary required')
    text = text[:text.index(marker)]+'''    ranked=sorted(candidates,key=lambda r:(-lexical(r),r['path'],r['start']))
    return [{'name':r['name'],'path':r['path'],'start':r['start'],'score':lexical(r),
             'explicit':r['explicit'],'name_matches':sorted(r['label'] & terms)} for r in ranked[:5]]
'''
    derived = dict(namespace)
    exec(compile(text, '<declared-layout-lexical-inspector>', 'exec'), derived)
    return derived['pack_generation']


def audit(archive, output, keys, baseline, candidate, *, validate=allowed_delta):
    from benchmarks.code_replay.windows_archive import recover_snapshot
    from benchmarks.code_replay.packing_replay_audit import retained_generation
    validate(baseline, candidate)
    if sha256(baseline.encode()).hexdigest() != BASELINE: raise ValueError('frozen baseline source required')
    modules = []
    for source in (baseline, candidate):
        module = types.ModuleType('layout_diagnostic_packer')
        exec(compile(source, '<retained-layout-diagnostic-packer>', 'exec'), module.__dict__)
        modules.append((module, lexical_inspector(source, module.__dict__)))
    raw, _ = recover_snapshot(run_id=archive.COLLECTION, output=output/'collection', key_root=keys/'collection')
    members = {row['run_id']: row for row in json.loads(raw)['runs']}
    def read(run):
        row = members[run]; directory = sha256(run.encode()).hexdigest()
        if row['directory'] != directory: raise ValueError('exact archive member path required')
        raw, proof = recover_snapshot(run_id=run, output=output/directory, key_root=keys/directory)
        if proof['raw_sha256'] != row['raw_sha256'] or len(raw) != row['raw_bytes']:
            raise ValueError('authenticated original member differs')
        return json.loads(raw)
    lock, = archive.of(read(archive.LOCK), 'external.v3_execution_manifest_frozen')
    stages = lock['staged_blocks']; identities = set(lock['staging_manifest']['issues'])
    if (len(stages) != 19 or len(identities) != 19
            or {row['block']['instance_id'] for row in stages} != identities):
        raise ValueError('all nineteen original issues required')
    results = []
    for stage in stages:
        identity = stage['block']['instance_id']; task = lock['staging_manifest']['issues'][identity]
        generation, case = retained_generation(read(stage['task_run']))
        if case['prepared']['request']['task'] != task: raise ValueError('original query binding differs')
        streams = io.StringIO()
        with contextlib.redirect_stderr(streams):
            old = modules[0][0].pack_generation(generation, task, budget=4096)
            if old != case['prepared']['package']['content']:
                raise ValueError('baseline does not reproduce original pack; never skip this case')
            new = modules[1][0].pack_generation(generation, task, budget=4096)
            ranks = [inspect(generation, task, budget=4096) for _, inspect in modules]
        weights = modules[1][0]._query_term_weights(task)
        results.append({'identity': identity, 'stage_run': stage['task_run'],
            'original_pack_reproduced': True, 'changed': old != new,
            'baseline_pack': old, 'candidate_pack': new, 'top_lexical': ranks,
            'downweighted_terms': sorted(term for term, weight in weights.items() if weight < 1),
            'warnings': streams.getvalue()})
    return {'summary': {'identities': 19, 'all_original_packs_reproduced': True,
        'changed_packs': sum(row['changed'] for row in results), 'source_vault_opened': False,
        'models_repeated': 0, 'private_grades_repeated': 0, 'efficacy_claim': False}, 'cases': results}


def main():
    import os
    import subprocess
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.corrective_transfer import OUTPUT, KEYS
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=RUN)
    rows = vault.inspect(principal, RUN)
    def save(kind, payload): return vault.capture(run_id=RUN, kind=kind, principal=principal, payload=payload)
    packing = Path('atmem/knowledge/code/packing.py').read_text()
    if sys.argv[1:] == ['plan']:
        if rows or sha256(packing.encode()).hexdigest() != BASELINE:
            raise ValueError('fresh plan with complete unchanged CD1 source required')
        save('external.layout_diagnostic_planned', {'driver_source': Path(__file__).read_text(),
            'baseline_source': packing, 'baseline_sha256': BASELINE,
            'protocol': Path('specs/042-atmem-code/query-layout-ranking-v1.md').read_text(),
            'models_or_grades': 0, 'selection': 'all nineteen original CD1 issues'})
        print('Frozen baseline source and prospective layout protocol retained.'); return
    if sys.argv[1:] != ['run'] or [row['envelope']['event_type'] for row in rows] != ['external.layout_diagnostic_planned']:
        raise ValueError('exact unexecuted plan required; no automatic diagnostic retry')
    plan = rows[0]['envelope']['payload']
    if Path(__file__).read_text() != plan['driver_source']: raise ValueError('diagnostic changed after planning')
    helper = allowed_delta(plan['baseline_source'], packing)
    transfer = vault.inspect(principal, PREFIX+'MEM-transfer-recovery-v1-20261018')
    end, = [row['envelope']['payload'] for row in transfer
            if row['envelope']['event_type'] == 'external.v3_MEM_recovery_completed']
    if end['proof']['request_audit']['verified_original_requests'] != 38:
        raise ValueError('completed independent recovery required')
    transfer_plan, = [row['envelope']['payload'] for row in transfer
                      if row['envelope']['event_type'] == 'external.v3_MEM_transfer_recovery_planned']
    bootstrap = transfer_plan['standalone_recovery_program']
    marker = '\nproof=archive.recover_collection'
    if bootstrap.count(marker) != 1: raise ValueError('exact verified reader bootstrap required')
    source = Path(__file__).read_text(); program = bootstrap[:bootstrap.index(marker)]
    program += '\nns={"__name__":"layout_reader"};exec(compile('+repr(source)+",'<retained-layout-audit>','exec'),ns)\n"
    program += 'print(json.dumps(ns["audit"](archive,Path('+repr(OUTPUT)+'),Path('+repr(KEYS)+'),'+repr(plan['baseline_source'])+','+repr(packing)+')),flush=True)\n'
    save('external.layout_diagnostic_started', {'candidate_source': packing,
         'candidate_sha256': sha256(packing.encode()).hexdigest(), 'layout_helper': helper,
         'reader_program': program, 'source_vault_access': False})
    result = subprocess.run([sys.executable, '-c', program], capture_output=True, timeout=3600)
    if result.returncode:
        save('external.layout_diagnostic_failed', {'exit_code': result.returncode,
             'stderr': result.stderr.decode(errors='replace'), 'no_automatic_retry': True})
        raise RuntimeError('static diagnostic failed; inspect original evidence')
    value = json.loads(result.stdout)
    save('external.layout_diagnostic_completed', value)
    print(json.dumps(value['summary']), flush=True)


if __name__ == '__main__': main()
