import ast
from copy import deepcopy

import pytest

from benchmarks.code_replay import query_nomination_transfer as transfer


def test_transfer_separates_exact_archive_and_internal_keys():
    assert transfer.OUTPUT in transfer.copy_command(transfer.REMOTE_OUTPUT+'/', transfer.OUTPUT)[-1]
    assert transfer.KEYS in transfer.copy_command(transfer.REMOTE_KEYS+'/', transfer.KEYS)[-1]
    with pytest.raises(ValueError):
        transfer.copy_command(transfer.REMOTE_KEYS+'/', transfer.OUTPUT)
    with pytest.raises(ValueError):
        transfer.copy_command('/home/jt/', transfer.OUTPUT)


def test_export_guard_uses_complete_actual_membership_not_hardcoded_old_count():
    value = {'plans': [{'driver_source': 'archive', 'output': transfer.REMOTE_OUTPUT,
                       'internal_key_root': transfer.REMOTE_KEYS, 'runs': ['a', 'b', 'c']}],
             'terminal': [{'runs': 3}], 'helpers': {'grade': 'original'}}
    assert transfer.export_ready(value, 'archive', {'grade': 'original'}) == 3
    for key in ('driver_source', 'output', 'internal_key_root'):
        bad = deepcopy(value); bad['plans'][0][key] = 'different'
        with pytest.raises(ValueError):
            transfer.export_ready(bad, 'archive', {'grade': 'original'})
    bad = deepcopy(value); bad['terminal'][0]['runs'] = 2
    with pytest.raises(ValueError):
        transfer.export_ready(bad, 'archive', {'grade': 'original'})
    bad = deepcopy(value); bad['plans'][0]['runs'] = ['a', 'a', 'b']
    with pytest.raises(ValueError):
        transfer.export_ready(bad, 'archive', {'grade': 'original'})


def test_standalone_program_retains_actual_helpers_denies_live_and_requires_all_requests():
    source = transfer.recovery_program('archive-source', {'grade': 'actual-grade'}, 'audit-source')
    ast.parse(source, feature_version=(3, 10))
    assert 'run_evidence.operational_evidence=forbidden' in source
    assert 'actual-grade' in source
    assert 'archive-source' in source
    assert "proof['request_audit']['verified_original_requests']!=38" in source
    assert '!=(38,38,38)' in source
    assert transfer.OUTPUT in source and transfer.KEYS in source
