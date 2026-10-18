import json
from pathlib import Path
import zlib

import pytest

from benchmarks.code_replay.windows_archive import decompress_exact, export_snapshot, recover_snapshot


def test_segmented_export_restores_all_bytes_and_rejects_swapped_or_tampered_parts(tmp_path):
    raw = b'First complete model/tool/source evidence.\n' * 8
    output, keys = tmp_path / 'archive', tmp_path / 'internal-keys'
    manifest = export_snapshot(raw, run_id='fixture', output=output, key_root=keys, segment_bytes=128)
    restored, observed = recover_snapshot(run_id='fixture', output=output, key_root=keys)
    assert restored == raw and observed == manifest
    assert len(manifest['segments']) == 3
    assert not (output / 'recipient.secret').exists()
    first, second = output / manifest['segments'][0]['file'], output / manifest['segments'][1]['file']
    # Modify only this disposable fixture, never benchmark evidence.
    first.write_bytes(second.read_bytes())
    with pytest.raises(ValueError, match='encrypted segment bytes'):
        recover_snapshot(run_id='fixture', output=output, key_root=keys)
    with pytest.raises(ValueError, match='never overwrite'):
        export_snapshot(raw, run_id='fixture', output=output, key_root=keys)


def test_compression_is_bounded_and_trailing_data_is_not_accepted():
    packed = zlib.compress(b'complete evidence')
    assert decompress_exact(packed, 17) == b'complete evidence'
    for value, size in [(packed, 16), (packed, 18), (packed + b'extra', 17), (packed[:-1], 17)]:
        with pytest.raises(ValueError):
            decompress_exact(value, size)


def test_keys_must_not_be_exported_to_external_volume(tmp_path):
    with pytest.raises(ValueError, match='remain internal'):
        export_snapshot(b'evidence', run_id='fixture', output=tmp_path / 'archive',
            key_root=Path('/Volumes/MEM/atmem-forbidden-export-fixture-keys'))
