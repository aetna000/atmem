"""Audit all three terminal attempts and archive encrypted evidence to MEM."""
import base64
from hashlib import sha256
import json
from pathlib import Path

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.control_report import archive_all

ROOT = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/click-curation-threeway-qualified-20261019')
RUN = 'click-curation-threeway-20261019'


def main():
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / 'vault', vault_id=RUN, scope=scope)
    events = vault.inspect(principal, RUN)
    attempts = [e['envelope']['payload'] for e in events if e['envelope']['event_type'] == 'agent.attempt']
    started = [e['envelope']['payload']['arm'] for e in events if e['envelope']['event_type'] == 'trial.started']
    completed = [e['envelope']['payload']['result'] for e in events if e['envelope']['event_type'] == 'trial.completed']
    if started != ['native', 'cognee', 'atmem'] or len(attempts) != 3 or len(completed) != 3:
        raise ValueError('all predeclared attempts must be terminal; never hide failures')
    uptake = []
    for attempt in attempts:
        stream = [json.loads(line) for line in base64.b64decode(attempt['stdout_base64']).splitlines()]
        init, = [e for e in stream if e.get('type') == 'system' and e.get('subtype') == 'init']
        graph = [e for e in attempt['tool_audit'] if e['request']['method'] == 'tools/call'
                 and e['request']['params']['name'] != 'workspace_command']
        required = {'native': None, 'cognee': 'code_search', 'atmem': 'code_query'}[attempt['arm']]
        if required and not any(required in t for t in init['tools']):
            raise ValueError('enabled provider tool was missing from actual CLI initialization')
        uptake.append({'arm': attempt['arm'], 'actual_model': init['model'],
                       'actual_tools': init['tools'], 'mcp_servers': init['mcp_servers'],
                       'graph_calls': len(graph), 'changed_paths': attempt['changed_paths']})
    summary = {'format': 'atmem-curation-threeway-diagnostic-v1', 'rows': completed,
               'uptake': uptake, 'interpretation': 'single reused task; no observed provider uptake; no general savings claim'}
    vault.capture(run_id=RUN, kind='comparison.exposure_audit', principal=principal, payload=summary)
    destination = Path('/Volumes/MEM/AtMem-SWEbench-Threeway-20261019/click-curation-threeway')
    archive_all(vault, principal, {}, {'wheel_path': '/private/tmp/atmem-code-curation-acceptance-20261019/atmem-2.3.8-py3-none-any.whl'},
                destination, ROOT / 'archive-keys-qualified', protocol_id=RUN, run_ids=[])
    summary['archive'] = str(destination / (RUN + '.encrypted.json'))
    summary['archive_sha256'] = sha256(Path(summary['archive']).read_bytes()).hexdigest()
    path = Path(__file__).parents[1] / 'RandD/2026-10-19-curation-threeway-results.json'
    path.write_text(json.dumps(summary, indent=2))
    print(json.dumps({'status': 'archived_and_verified', 'results': str(path), 'archive': summary['archive']}))


if __name__ == '__main__':
    main()
