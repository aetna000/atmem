"""Real Windows traversal controls; never exercised by platform emulation."""
import os
from pathlib import Path
import subprocess

import pytest

from atmem.knowledge.projections import read_authorized_file, SourceFileBudgetExceeded

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows native file handles')


def test_nested_unicode_and_budget(tmp_path):
    nested = tmp_path / '目录'
    nested.mkdir()
    raw = 'déf 東京\n'.encode()
    (nested / 'source.py').write_bytes(raw)
    assert read_authorized_file(tmp_path, '目录/source.py', len(raw)) == raw
    with pytest.raises(SourceFileBudgetExceeded):
        read_authorized_file(tmp_path, '目录/source.py', len(raw) - 1)


def test_junction_escape_and_root_junction_are_refused(tmp_path):
    root, outside = tmp_path / 'project', tmp_path / 'outside'
    root.mkdir()
    outside.mkdir()
    (outside / 'private.py').write_text('OUTSIDE_SOURCE_CANARY')
    link = root / 'linked'
    subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(link), str(outside)],
        check=True, capture_output=True)
    try:
        with pytest.raises(OSError):
            read_authorized_file(root, 'linked/private.py', 1024)
        with pytest.raises(OSError):
            read_authorized_file(link, 'private.py', 1024)
    finally:
        os.rmdir(link)  # Remove only the test junction, not its target.
    assert (outside / 'private.py').read_text() == 'OUTSIDE_SOURCE_CANARY'


@pytest.mark.parametrize('name', ['../outside.py', 'source.py:stream', 'file./source.py', 'file /source.py'])
def test_windows_path_aliases_are_refused(tmp_path, name):
    with pytest.raises((ValueError, OSError)):
        read_authorized_file(tmp_path, name, 1024)


def test_pinned_parents_cannot_be_replaced_and_handles_release(tmp_path):
    from atmem.knowledge.windows_source import open_source
    parent = tmp_path / 'nested'
    parent.mkdir()
    source = parent / 'source.py'
    source.write_bytes(b'ORIGINAL')
    with open_source(tmp_path, 'nested/source.py') as descriptor:
        with pytest.raises(OSError):
            parent.rename(tmp_path / 'moved')
        with pytest.raises(OSError):
            source.unlink()
        assert os.read(descriptor, 16) == b'ORIGINAL'
    parent.rename(tmp_path / 'moved')
    assert (tmp_path / 'moved/source.py').read_bytes() == b'ORIGINAL'
