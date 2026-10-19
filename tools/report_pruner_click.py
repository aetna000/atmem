"""Retain every terminal four-way trial and quantify actual pruning uptake."""
import base64
from hashlib import sha256
import json
import os
from pathlib import Path

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.control_report import archive_all

ROOT = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/click-pruner-fourway-20261020')
GPU = Path(os.environ.get('ATMEM_PRUNER_GPU_ROOT', str(ROOT.parent / 'swe-pruner-gpu-20261020-fallback')))
RUN = 'click-pruner-fourway-20261020'


def main(controlled=False, complete_gpu_artifacts=False):
    global ROOT, RUN
    if controlled:
        ROOT = ROOT.with_name('click-pruner-controlled-20261020')
        RUN = ROOT.name
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / 'vault', vault_id=RUN, scope=scope)
    events = vault.inspect(principal, RUN)
    started = [e['envelope']['payload']['arm'] for e in events if e['envelope']['event_type'] == 'trial.started']
    expected = ['atmem', 'atmem_pruner'] if controlled else ['native', 'cognee', 'atmem', 'atmem_pruner']
    if started != expected:
        raise ValueError('all predeclared attempts required; do not omit a failure')
    attempts = [e['envelope']['payload'] for e in events if e['envelope']['event_type'] == 'agent.attempt']
    completed = [e['envelope']['payload']['result'] for e in events if e['envelope']['event_type'] == 'trial.completed']
    if len(attempts) != len(expected) or len(completed) != len(expected):
        raise ValueError('all attempts must terminate and be graded before reporting')
    reads = {}
    for attempt in attempts:
        stream = [json.loads(line) for line in base64.b64decode(attempt['stdout_base64']).splitlines()]
        init, = [e for e in stream if e.get('type') == 'system' and e.get('subtype') == 'init']
        if not any('read_source' in name for name in init['tools']):
            raise ValueError('common read tool absent from actual initialization')
        rows = []
        for entry in attempt['tool_audit']:
            request = entry['request']
            if request.get('method') != 'tools/call' or request['params']['name'] != 'read_source':
                continue
            response = entry['response']
            if 'error' in response:
                rows.append({'error': response['error'], 'request': request['params']['arguments']})
                continue
            value = json.loads(response['result']['content'][0]['text'])
            if 'pruning' in value and value['pruning']['source_sha256'] != value['source_window_sha256']:
                raise ValueError('pruner source-window receipt mismatch')
            rows.append({'request': request['params']['arguments'], 'input_bytes': value['input_window_bytes'],
                'returned_code_bytes': len(value['code'].encode()), 'omitted': value['omitted'],
                'gpu_seconds': value.get('pruning', {}).get('seconds', 0),
                'original_skimmer_tokens': value.get('pruning', {}).get('origin_token_cnt'),
                'remaining_skimmer_tokens': value.get('pruning', {}).get('left_token_cnt'),
                'tool_seconds': entry['elapsed_ms'] / 1000})
        reads[attempt['arm']] = {'calls': rows, 'actual_model': init['model'],
            'successful_reads': sum('error' not in row for row in rows),
            'pruned_reads': sum(row.get('omitted', False) for row in rows),
            'input_bytes': sum(row.get('input_bytes', 0) for row in rows),
            'returned_code_bytes': sum(row.get('returned_code_bytes', 0) for row in rows),
            'gpu_seconds': sum(row.get('gpu_seconds', 0) for row in rows)}
    extra = {}
    for name in ('qualification.json', 'last-runtime.json', 'inference-audit.jsonl', 'install.log',
                 'qualification.log', 'server.py', 'cases.json'):
        path = GPU / name
        if path.is_file():
            extra[name] = path.read_text()
    if complete_gpu_artifacts and set(extra) != {'qualification.json', 'last-runtime.json', 'inference-audit.jsonl',
                                               'install.log', 'qualification.log', 'server.py', 'cases.json'}:
        raise ValueError('all recovered GPU artifacts required for complete retention snapshot')
    logs = {p.name: p.read_text() for p in ROOT.glob('*-provider.log')}
    summary = {'format': 'atmem-swe-pruner-controlled-v1' if controlled else 'atmem-swe-pruner-fourway-v1',
               'rows': completed, 'source_reads': reads,
               'gpu_qualification': json.loads((GPU / 'qualification.json').read_text()),
               'limits': 'one reused task; fixed order; controlled source reader; no general savings claim'}
    vault.capture(run_id=RUN, kind='pruner.exposure_and_runtime_audit', principal=principal,
                  payload={'summary': summary, 'provider_logs': logs})
    for name, data in extra.items():
        chunks = [data[offset:offset + 1_000_000] for offset in range(0, len(data), 1_000_000)] or ['']
        for index, chunk in enumerate(chunks):
            vault.capture(run_id=RUN, kind='pruner.gpu_artifact', principal=principal,
                payload={'name': name, 'sha256': sha256(data.encode()).hexdigest(), 'chunk': index,
                         'total_chunks': len(chunks), 'text': chunk,
                         'coverage': 'includes qualification and transport probes; scored calls counted only from agent tool audit'})
    destination = Path('/Volumes/MEM/AtMem-SWEbench-Threeway-20261019') / (RUN + ('-gpu-complete' if complete_gpu_artifacts else ''))
    archive_all(vault, principal, {}, {'wheel_path': '/private/tmp/atmem-code-curation-acceptance-20261019/atmem-2.3.8-py3-none-any.whl'},
                destination, ROOT / ('archive-keys-gpu-complete' if complete_gpu_artifacts else 'archive-keys'),
                protocol_id=RUN, run_ids=[])
    summary['archive'] = str(destination / (RUN + '.encrypted.json'))
    summary['archive_sha256'] = sha256(Path(summary['archive']).read_bytes()).hexdigest()
    path = Path(__file__).parents[1] / ('RandD/2026-10-20-swe-pruner-controlled-results.json'
        if controlled else 'RandD/2026-10-20-swe-pruner-fourway-results.json')
    path.write_text(json.dumps(summary, indent=2))
    print(json.dumps({'status': 'archived_and_verified', 'results': str(path), 'source_reads': reads}), flush=True)


if __name__ == '__main__':
    main()
