"""Actual filesystem privacy checks; fixtures contain no real credentials."""
import os
import subprocess

import pytest

from atmem.private_paths import private_path,protect_private_path


def make_public(path):
    if os.name=='nt':
        subprocess.run(['icacls.exe',str(path),'/grant','*S-1-1-0:(R)'],
                       check=True,capture_output=True)
    else:path.chmod(0o644)


def test_private_file_is_rechecked_after_permissions_change(tmp_path):
    root=tmp_path/'private';root.mkdir();protect_private_path(root)
    file=root/'fixture';file.write_bytes(b'nonsecret fixture')
    protect_private_path(file)
    assert private_path(root) and private_path(file)
    make_public(file)
    assert not private_path(file)
    protect_private_path(file)
    assert private_path(file)


def test_missing_and_special_paths_are_not_private(tmp_path):
    assert not private_path(tmp_path/'missing')
    if os.name!='nt':
        fifo=tmp_path/'fifo';os.mkfifo(fifo)
        assert not private_path(fifo)
        with pytest.raises(ValueError):protect_private_path(fifo)


@pytest.mark.skipif(os.name!='nt',reason='native Windows DACL boundary')
def test_windows_inherited_acl_requires_private_parent(tmp_path):
    root=tmp_path/'private';root.mkdir();protect_private_path(root)
    inherited=root/'inherited';inherited.write_bytes(b'nonsecret')
    assert private_path(inherited)
    subprocess.run(['icacls.exe',str(inherited),'/grant','*S-1-1-0:(R)'],
                   check=True,capture_output=True)
    assert not private_path(inherited)


@pytest.mark.skipif(os.name!='nt',reason='native Windows DACL boundary')
def test_windows_acl_read_failure_never_bypasses_permissions(tmp_path,monkeypatch):
    file=tmp_path/'fixture';file.touch()
    def unavailable():raise OSError('unavailable')
    monkeypatch.setattr('atmem.private_paths._windows_api',unavailable)
    assert not private_path(file)
    with pytest.raises(OSError):protect_private_path(file)
