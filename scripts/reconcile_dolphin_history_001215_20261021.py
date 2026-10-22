"""Reconcile one stopped local history import; never replay model inference."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import traceback

ROOT = Path('/Volumes/AtMemDolphin/campaign-atmem-v3-full-r2-20261021')
sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append('/Volumes/AtMemDolphin/upstream')

from atmem.core.canonical import canonical_json, sha256_hex
from benchmarks.dolphinbench.adapter import AtMemAdapter
from benchmarks.dolphinbench.gateway import save_new
from harness.runner import Runner, digest
from harness.submission import read_release


def main():
    assert not any((ROOT / 'tests').glob('*/*.json'))
    release = read_release(Path('/Volumes/AtMemDolphin/upstream'))
    spec = next(s for s in release['morgan']['sessions'] if s['id'] == '001215')
    marker = ROOT / 'ingestion/morgan/001215.inflight'
    assert json.loads(marker.read_text())['source_sha256'] == digest(spec)
    run = json.loads((ROOT / 'run.json').read_text())
    options = {'campaign_identity': run['configuration']['campaign'],
        'env_file': '/Users/javadtaghia/gitlab/aetnamem/.env.atmem-c709e',
        'memory_engine': 'context-v3', 'ingestion_mode': 'source-episode',
        'app_python': '/private/tmp/atmem-dolphin-apps-v3-20261021/bin/python',
        'runtime_root': '/private/tmp/atmem-dolphin-runtime-v3-20261021',
        'subscription_endpoint': 'not-used-for-local-history-recovery'}
    adapter = AtMemAdapter(options, ROOT)
    try:
        runner = Runner(release, ROOT, adapter, identity=adapter.identity(),
                        release_root=Path('/Volumes/AtMemDolphin/upstream'))
        host = adapter.host('morgan')
        binding = host.service._binding(host.service._load(host.binding['binding_id']))
        session = binding._session('001215')
        legacy_id = 'hermes-v3-' + sha256_hex(canonical_json([binding.profile_id, session, '001215']))
        with binding.v3().memory() as (memory, scope):
            row = memory.store._conn.execute('SELECT source_id FROM context_source_episodes WHERE legacy_episode_id=?',
                                             (legacy_id,)).fetchone()
            if row is not None:
                parts = memory.store._conn.execute('SELECT content_bytes FROM context_source_parts WHERE source_id=? ORDER BY ordinal',
                                                     (row['source_id'],)).fetchall()
                from harness.adapter import Interaction
                expected = Interaction('morgan', 'ingestion', '001215', spec['messages'][0].strip(),
                    spec['narrative_date'], {}, ROOT).dated_message.encode()
                assert len(parts) == 1 and bytes(parts[0][0]) == expected
        save_new(ROOT / 'repairs/history-001215-reconciliation.json', {
            'persona': 'morgan', 'id': '001215', 'source_digest': digest(spec),
            'prior_source_row_exists': row is not None,
            'existing_bytes_verified_if_present': True,
            'authorized_recovery': 'exact original observation through the same scoped, idempotent product API',
            'model_calls_replayed': 0, 'test_tasks_executed': 0})
        shutil.move(str(marker), str(ROOT / 'repairs/history-001215-original-inflight.json'))
        try:
            result = runner._execute('ingestion', 'morgan', spec)
        except Exception:
            # Surface only an original local product error, not an invented
            # success. Idempotency protects the original source identity.
            from harness.adapter import Interaction
            observation = Interaction('morgan', 'ingestion', '001215', spec['messages'][0].strip(),
                                      spec['narrative_date'], {}, ROOT)
            try:
                binding.v3().observe(observation.dated_message, session_id=session, observation_id='001215')
            except Exception as error:
                save_new(ROOT / 'repairs/history-001215-product-error.json', {
                    'error_type': type(error).__name__, 'message': str(error)[:500],
                    'traceback': traceback.format_exc(), 'paid_inference_calls': 0})
                print(json.dumps({'underlying_error_type': type(error).__name__,
                                  'detail': str(error)[:300]}), flush=True)
            raise
        print(json.dumps({'reconciled': True, 'persona': 'morgan', 'id': '001215',
            'captured': result['attempts'][0]['product_receipt'].get('captured'),
            'model_calls_replayed': 0}), flush=True)
    finally:
        adapter.stop()


if __name__ == '__main__':
    main()
