import pytest
from benchmarks.code_replay.confirmation_v3_transfer import ready, transfer_command, REMOTE, OUTPUT, KEYS


def test_wait_requires_unambiguous_completed_archive_without_model_restart():
    assert not ready({'models_stopped': False, 'archive_terminals': []})
    assert ready({'models_stopped': False, 'archive_terminals': [{}]})
    with pytest.raises(ValueError): ready({'models_stopped': True, 'archive_terminals': []})
    with pytest.raises(ValueError): ready({'models_stopped': False, 'archive_terminals': [{}, {}]})


def test_only_exact_benchmark_paths_and_internal_key_destination_are_allowed():
    assert transfer_command(REMOTE+'/confirmation-archive-v3/', OUTPUT)[-1] == str(OUTPUT)+'/'
    assert transfer_command(REMOTE+'/confirmation-archive-keys-v3/', KEYS)[-1] == str(KEYS)+'/'
    with pytest.raises(ValueError): transfer_command(REMOTE+'/confirmation-archive-keys-v3/', OUTPUT)
    with pytest.raises(ValueError): transfer_command(REMOTE+'/', OUTPUT)
    assert '--delete' not in transfer_command(REMOTE+'/confirmation-archive-v3/', OUTPUT)
