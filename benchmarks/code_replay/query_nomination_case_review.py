"""Inspect every archived repair and retain full details for discordant pairs."""
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

from benchmarks.code_replay.query_nomination_preview import evidence
from benchmarks.code_replay.query_nomination_screen import PREFIX
from benchmarks.code_replay.query_nomination_transfer import RUN as TRANSFER, OUTPUT, KEYS
from benchmarks.code_replay.query_nomination_trace_audit import reader_program

RUN = PREFIX+'case-review-v1-20261018'
FEEDBACK_RUN = PREFIX+'public-feedback-audit-v1-20261018'


def profile(args):
    if not args:
        return RUN
    if args == ['feedback']:
        return FEEDBACK_RUN
    raise ValueError('select the original review or explicit feedback audit profile')


def review(archive, output, keys):
    import base64
    import difflib
    from hashlib import sha256
    import json
    from benchmarks.code_replay.windows_archive import recover_snapshot
    from benchmarks.code_replay.windows_metrics import recover_stream
    from benchmarks.code_replay.windows_confirmation_exports import recover_export
    from benchmarks.code_replay.confirmation_v3_grade import recover_candidate
    from atmem.knowledge.source_text import source_text
    raw, _ = recover_snapshot(run_id=archive.COLLECTION, output=output/'collection', key_root=keys/'collection')
    members = {r['run_id']: r for r in json.loads(raw)['runs']}
    def read(run):
        member = members[run]; directory = sha256(run.encode()).hexdigest()
        if member['directory'] != directory:
            raise ValueError('authenticated member path required')
        raw, proof = recover_snapshot(run_id=run, output=output/directory, key_root=keys/directory)
        if proof['raw_sha256'] != member['raw_sha256'] or len(raw) != member['raw_bytes']:
            raise ValueError('complete authenticated member required')
        return json.loads(raw)
    report, = archive.of(read(archive.REPORT), 'external.v3_comparison_completed')
    lock, = archive.of(read(archive.LOCK), 'external.v3_execution_manifest_frozen')
    rows = report['rows']; by_identity = {}
    for row in rows:
        pair = by_identity.setdefault(row['instance_id'], {})
        if row['arm'] in pair:
            raise ValueError('duplicate original cell')
        pair[row['arm']] = row
    if len(rows) != 38 or len(by_identity) != 19 or any(set(p) != {'native', 'tools'} for p in by_identity.values()):
        raise ValueError('complete nineteen original pairs required')
    discordant = {i for i, pair in by_identity.items()
                  if pair['native']['quality']['task_pass'] != pair['tools']['quality']['task_pass']}
    stages = {r['block']['slot']: r for r in lock['staged_blocks']}
    originals = {}; results = []
    for row in rows:
        identity = row['instance_id']; records = read(row['task_run'])
        model, = archive.of(records, 'external.v3_model_result')
        summary, = archive.of(records, 'external.v3_case_completed')
        raw = recover_stream({r['object_id']: r for r in records}, model['raw_response_transport']['stdout'])
        events = json.loads(raw)['events']
        receipts = [r for r in events if r.get('type') == 'turn.completed']
        if receipts != model['usage_receipts'] or len(receipts) != 1:
            raise ValueError('original normal receipt required')
        if any(receipts[0]['usage'][k] != row['usage'][k] for k in ('input_tokens', 'cached_input_tokens', 'output_tokens')):
            raise ValueError('original usage differs from comparison')
        items = {}
        for event in events:
            item = event.get('item', {})
            if event.get('type') == 'item.completed' and isinstance(item.get('id'), str):
                if item['id'] in items and item != items[item['id']]:
                    raise ValueError('conflicting completed item')
                items[item['id']] = item
        case = stages[row['slot']]['cases'][row['arm']]
        prepared = case.get('prepared')
        if prepared and prepared['request']['task'] != lock['staging_manifest']['issues'][identity]:
            raise ValueError('original task binding differs')
        result = {**{k: row[k] for k in ('instance_id', 'arm', 'slot', 'quality', 'grading', 'usage')},
                  'discordant': identity in discordant, 'changed_paths': summary['changed_paths'],
                  'initial_pack': prepared['package']['content'] if prepared else '',
                  'commands': [i['command'] for i in items.values() if i.get('type') == 'command_execution'],
                  'public_tool_calls': [i for i in items.values() if i.get('type') == 'mcp_tool_call'
                                        and i.get('server') == 'benchmark_public_tests'],
                  'messages': [i.get('text', '') for i in items.values() if i.get('type') == 'agent_message'],
                  'source_task_run': row['task_run'], 'original_transport': model['raw_response_transport']['stdout']}
        if identity in discordant:
            descriptor = lock['staging_manifest']['source_descriptors'][identity]
            if identity not in originals:
                originals[identity] = recover_export(read(descriptor['export_run']), descriptor)
            original = originals[identity]['files_base64']
            candidate = recover_candidate(records, summary)['files_base64']
            patches = {}
            for name in summary['changed_paths']:
                before = source_text(name, base64.b64decode(original[name], validate=True)) if name in original else ''
                after = source_text(name, base64.b64decode(candidate[name], validate=True)) if name in candidate else ''
                patches[name] = ''.join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                                          fromfile='a/'+name, tofile='b/'+name))
            result.update(patches=patches, original_model_events=events,
                          issue=lock['staging_manifest']['issues'][identity])
        results.append(result)
    return {'summary': {'cases': 38, 'pairs': 19, 'discordant_pairs': len(discordant),
                        'models_repeated': 0, 'private_grades_repeated': 0, 'source_vault_opened': False}, 'cases': results}


def main():
    os.environ['ATMEM_BENCHMARK_PER_RUN_VAULTS'] = '1'
    run = profile(sys.argv[1:])
    vault, principal = evidence(run)
    if vault.inspect(principal, run):
        raise ValueError('case review already attempted; inspect original evidence')
    rows = vault.inspect(principal, TRANSFER)
    def only(kind):
        value, = [r['envelope']['payload'] for r in rows if r['envelope']['event_type'] == kind]
        return value
    terminal = only('external.query_nomination_MEM_recovery_completed')
    if terminal['proof']['request_audit']['verified_original_requests'] != 38 or terminal['proof']['source_vault_opened'] is not False:
        raise ValueError('independent complete recovery required')
    source = inspect.getsource(review)
    source += '\ndef audit(archive,output,keys):return review(archive,output,keys)\n'
    program = reader_program(only('external.query_nomination_MEM_transfer_planned')['standalone_recovery_program'], source)
    def save(kind, payload):
        return vault.capture(run_id=run, kind=kind, principal=principal, payload=payload)
    save('external.query_nomination_case_review_planned', {
        'driver_source': Path(__file__).read_text(), 'reader_program': program,
        'selection': 'all 38 cells; full actual source patches/events for every discordant pair',
        'source_vault_access': False, 'models_repeated': 0, 'private_grades_repeated': 0})
    loader = "import json,sys;exec(compile(json.load(sys.stdin)['program'],'<archive-only-repair-review>','exec'))"
    result = subprocess.run([sys.executable, '-c', loader], input=json.dumps({'program': program}).encode(),
                            capture_output=True, timeout=3600)
    if result.returncode:
        save('external.query_nomination_case_review_failed', {'exit_code': result.returncode, 'stderr': result.stderr.decode(errors='replace')})
        raise RuntimeError('archive-only review failed; preserve evidence, no outcome rerun')
    value = json.loads(result.stdout)
    save('external.query_nomination_case_review_completed', value)
    print(json.dumps(value['summary']), flush=True)


if __name__ == '__main__':
    main()
