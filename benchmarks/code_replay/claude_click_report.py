"""Audit actual Claude exposure/uptake, preserve every comparison, archive."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.claude_click_study import ROOT, RUN, WHEEL, COGNEE


def main():
    scope = EvidenceScope('benchmark', 'local-operator', 'click-20261017')
    principal = EvidencePrincipal('local-benchmark-operator', EvidenceRole.ADMINISTRATOR, scope)
    vault = ReplayEvidence(ROOT / 'vault', vault_id=RUN, scope=scope)
    events = vault.inspect(principal, RUN)
    completed, = [e['envelope']['payload'] for e in events if e['envelope']['event_type'] == 'comparison.completed']
    attempts = [e['envelope']['payload'] for e in events if e['envelope']['event_type'] == 'agent.attempt']
    assert len(attempts) == 3
    uptake = []
    for attempt in attempts:
        stream = [json.loads(line) for line in base64.b64decode(attempt['stdout_base64']).splitlines()]
        init, = [e for e in stream if e.get('type') == 'system' and e.get('subtype') == 'init']
        graph_calls = [e for e in attempt['tool_audit'] if e['request']['method'] == 'tools/call'
                       and e['request']['params']['name'] != 'workspace_command']
        uptake.append({'arm': attempt['arm'], 'actual_model': init['model'], 'actual_tools': init['tools'],
            'connected_servers': init['mcp_servers'], 'graph_calls': graph_calls,
            'changed_paths': attempt['changed_paths'], 'patch_violations': attempt['patch_violations']})
    prior = []
    for name, run in (('claude-three-arm-20261018', 'click-claude-three-arm-20261018-v1'),
                      ('claude-three-arm-qualified-20261018', 'click-claude-three-arm-20261018-v1-qualified'),
                      ('claude-three-arm-consult-20261018', 'click-claude-three-arm-20261018-v2-consult')):
        old = ReplayEvidence(ROOT.parent / name / 'vault', vault_id=run, scope=scope)
        data = old.inspect(principal, run)
        prior.append({'root_name': name, 'run_id': run, 'events': data,
            'dispatches': sum(e['envelope']['event_type'] == 'trial.started' for e in data)})
    assert [p['dispatches'] for p in prior] == [0, 3, 3]
    upstream = Path('/tmp/atmem-code-research.yKNuul/cognee')
    revision = subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip()
    clean = not subprocess.check_output(['git', '-C', str(upstream), 'status', '--porcelain'], text=True).strip()
    check = subprocess.check_output([str(COGNEE), '-I', '-c', '''
import importlib.metadata as m,json
from pathlib import Path
from hashlib import sha256
source=Path('/tmp/atmem-code-research.yKNuul/cognee/cognee')
installed=Path(m.distribution('cognee').locate_file('cognee'))
files={str(p.relative_to(source)):sha256(p.read_bytes()).hexdigest() for p in source.rglob('*.py')}
bad=[n for n,h in files.items() if not (installed/n).is_file() or sha256((installed/n).read_bytes()).hexdigest()!=h]
print(json.dumps({'python_files':len(files),'mismatches':bad,'manifest_sha256':sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()}))
'''], text=True)
    identity = json.loads(check)
    assert revision == 'f154b32a9e544dac73e7ddf2010327cf9988edcd' and clean and not identity['mismatches']
    vault.capture(run_id=RUN, kind='comparison.final_audit', principal=principal, payload={
        'uptake': uptake, 'upstream_revision': revision, 'upstream_clean': clean,
        'installed_upstream': identity, 'prior_comparisons': prior,
        'all_target_attempts': 9, 'target_retries_within_protocol': 0,
        'audit_timing': 'post_run_identity_and_exposure_audit',
        'protocols': {p.name: p.read_text() for p in Path(__file__).parents[2].joinpath('specs/043-click-historical-replay').glob('claude-three-arm*.md')}})
    print(json.dumps({'rows': completed['rows'], 'upstream': identity,
        'uptake': [{k: v for k, v in u.items() if k != 'graph_calls'} | {'graph_call_count': len(u['graph_calls'])} for u in uptake]}, indent=2))
    if '--archive' in sys.argv:
        from benchmarks.code_replay.control_report import archive_all
        destination = Path('/Volumes/MEM/AtMem-Code-Replay-20261017/protected-claude-three-arm-clean-20261018')
        keys = ROOT.parent / 'keys-claude-three-arm-clean-20261018'
        if not Path('/Volumes/MEM').is_mount() or destination.exists() or keys.exists():
            raise ValueError('mounted MEM and fresh separate archive/key destinations required')
        archive_all(vault, principal, {}, {'wheel_path': str(WHEEL)}, destination, keys,
                    protocol_id=RUN, run_ids=[])
        archive_path = destination / (RUN + '.encrypted.json')
        print(json.dumps({'archive': str(archive_path), 'sha256': sha256(archive_path.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
