"""Archive-only descriptive CD1 exploration audit; no new model or grader calls."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re

PREFIX = 'external-windows-corrective-development-'


def source_text_overlap(pack, events):
    """Count distinctive matching lines, not their file identity or usefulness.

    Removing a display line-number prefix is the only normalization. Short
    boilerplate, omission labels and pack headers cannot create positive hits.
    """
    def source_line(line):
        return re.sub(r'^\s*\d+: ?', '', line)
    lines = {source_line(line) for line in pack.splitlines()
             if re.match(r'^\s*\d+: ', line)}
    lines = {line for line in lines if len(line.strip()) >= 24 and not line.lstrip().startswith('[')}
    matched = set(); calls = 0
    items = {e['item']['id']: e['item'] for e in events
             if e.get('type') == 'item.completed' and isinstance(e.get('item', {}).get('id'), str)}
    for item in items.values():
        if item.get('type') != 'command_execution' or not isinstance(item.get('aggregated_output'), str):
            continue
        hits = {source_line(line) for line in item['aggregated_output'].splitlines()} & lines
        if hits: calls += 1; matched.update(hits)
    return {'eligible_distinct_pack_lines': len(lines), 'matching_distinct_lines': len(matched),
            'matching_distinct_utf8_bytes': sum(len(line.encode()) for line in matched),
            'commands_with_matching_text': calls,
            'assurance': 'text overlap proxy; not proof of same-file rereading, attention, waste or token attribution'}


def audit(archive, output, keys):
    from benchmarks.code_replay.windows_archive import recover_snapshot
    from benchmarks.code_replay.windows_metrics import recover_stream
    from benchmarks.code_replay.confirmation_v3_trace_audit import audit_events
    raw, _ = recover_snapshot(run_id=archive.COLLECTION, output=output/'collection', key_root=keys/'collection')
    members = {row['run_id']: row for row in json.loads(raw)['runs']}
    def read(run):
        row = members[run]; directory = sha256(run.encode()).hexdigest()
        if directory != row['directory']: raise ValueError('exact original archive directory required')
        raw, observed = recover_snapshot(run_id=run, output=output/directory, key_root=keys/directory)
        if observed['raw_sha256'] != row['raw_sha256'] or len(raw) != row['raw_bytes']:
            raise ValueError('authenticated original archive member differs')
        return json.loads(raw)
    report, = archive.of(read(PREFIX+'comparison-v1-20261018'), 'external.v3_comparison_completed')
    lock, = archive.of(read(archive.LOCK), 'external.v3_execution_manifest_frozen')
    expected = {(block['slot'], arm): (block['instance_id'], block['repeat'])
                for block in lock['staging_manifest']['blocks'] for arm in block['order']}
    rows = report['rows']
    if (len(rows) != 38 or len(expected) != 38 or len({(r['slot'], r['arm']) for r in rows}) != 38
            or any(expected.get((r['slot'], r['arm'])) != (r['instance_id'], r['repeat']) for r in rows)):
        raise ValueError('all original 38 cells required, never a favorable subset')
    stages = {block['block']['slot']: block for block in lock['staged_blocks']}
    results = []
    for row in rows:
        records = read(row['task_run'])
        model, = archive.of(records, 'external.v3_model_result')
        raw = recover_stream({e['object_id']: e for e in records}, model['raw_response_transport']['stdout'])
        result = json.loads(raw); events = result['events']
        receipts = [event for event in events if event.get('type') == 'turn.completed']
        if (receipts != model['usage_receipts'] or len(receipts) != 1
                or any(receipts[0]['usage'][key] != row['usage'][key]
                       for key in ('input_tokens', 'cached_input_tokens', 'output_tokens'))):
            raise ValueError('original normal CLI usage must match the completed comparison')
        prepared = stages[row['slot']]['cases'][row['arm']].get('prepared')
        pack = prepared['package']['content'] if prepared else ''
        results.append({**{key: row[key] for key in ('slot', 'arm', 'instance_id', 'repeat', 'task_run', 'usage', 'quality')},
            'initial_context_bytes': len(pack.encode()), 'initial_context_sha256': sha256(pack.encode()).hexdigest(),
            'trace': audit_events(events), 'source_overlap': source_text_overlap(pack, events),
            'original_transport': model['raw_response_transport']['stdout']})
    summary = {'cases': 38, 'source_vault_opened': False, 'models_repeated': 0,
               'private_grades_repeated': 0, 'not_causal_attribution': True, 'arms': {}}
    for arm in ('native', 'tools'):
        selected = [row for row in results if row['arm'] == arm]
        summary['arms'][arm] = {
            'attempts': len(selected),
            'native_commands': sum(row['trace']['native_commands'] for row in selected),
            'native_output_bytes': sum(row['trace']['native_command_output_bytes'] for row in selected),
            'exact_duplicate_output_bytes': sum(row['trace']['exact_duplicate_output_bytes'] for row in selected),
            'code_mcp_calls': sum(row['trace']['code_mcp_calls'] for row in selected),
            'tasks_with_matching_source_text': sum(row['source_overlap']['matching_distinct_lines'] > 0 for row in selected),
            'matching_distinct_source_text_bytes': sum(row['source_overlap']['matching_distinct_utf8_bytes'] for row in selected),
            'item_types': dict(sum((Counter(row['trace']['completed_item_types']) for row in selected), Counter()))}
    return {'summary': summary, 'cases': results}


def main():
    import inspect
    import os
    import subprocess
    import sys
    from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
    from benchmarks.code_replay.run_evidence import operational_evidence
    from benchmarks.code_replay.windows_confirmation_images import EVIDENCE_ROOT
    from benchmarks.code_replay.corrective_transfer import recovery_program, OUTPUT, KEYS
    from benchmarks.code_replay.corrective_archive import archive_source, request_audit_source
    from benchmarks.code_replay.corrective_execution import grading_source
    from benchmarks.code_replay import confirmation_v3_archive, confirmation_v3_grade, confirmation_v3_dispatch_audit
    run = PREFIX+'trace-audit-v1-20261018'
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = operational_evidence(EVIDENCE_ROOT, vault_id='confirmation-v1', scope=scope, writing_run=run)
    if vault.inspect(principal, run): raise ValueError('audit already attempted; inspect original result')
    end, = confirmation_v3_archive.of(vault.inspect(principal, PREFIX+'MEM-transfer-recovery-v1-20261018'),
                                    'external.v3_MEM_recovery_completed')
    if end['proof']['request_audit']['verified_original_requests'] != 38:
        raise ValueError('completed independent recovery required before diagnostic')
    bootstrap = recovery_program(archive_source(inspect.getsource(confirmation_v3_archive)),
        grading_source(inspect.getsource(confirmation_v3_grade)),
        request_audit_source(inspect.getsource(confirmation_v3_dispatch_audit)))
    marker = '\nproof=archive.recover_collection'
    if bootstrap.count(marker) != 1: raise ValueError('exact frozen reader bootstrap required')
    program = bootstrap[:bootstrap.index(marker)]
    source = Path(__file__).read_text()
    program += '\nns={"__name__":"cd1_archive_audit"};exec(compile('+repr(source)+",'<CD1-descriptive-audit>','exec'),ns)\n"
    program += 'print(json.dumps(ns["audit"](archive,Path('+repr(OUTPUT)+'),Path('+repr(KEYS)+'))),flush=True)\n'
    def save(kind, payload): return vault.capture(run_id=run, kind=kind, principal=principal, payload=payload)
    save('external.v3_trace_audit_planned', {'driver_source': source, 'reader_program': program,
         'cases': 38, 'selection': 'every original cell', 'model_or_grade_retries': 0})
    result = subprocess.run([sys.executable, '-c', program], capture_output=True, timeout=3600)
    if result.returncode:
        save('external.v3_trace_audit_failed', {'exit_code': result.returncode,
             'stderr': result.stderr.decode(errors='replace'), 'no_automatic_retry': True})
        raise RuntimeError('archive diagnostic failed; no model or grade retried')
    value = json.loads(result.stdout)
    save('external.v3_trace_audit_completed', value)
    print(json.dumps(value['summary']), flush=True)


if __name__ == '__main__': main()
