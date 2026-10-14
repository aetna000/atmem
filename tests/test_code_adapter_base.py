from __future__ import annotations

from pathlib import Path

import pytest

from atmem.code.adapters.base import HostConfigTransaction, HostProbe


class _Adapter:
    host = "test"

    def __init__(self, path: Path, verified: bool = True) -> None:
        self.path = path
        self.verified = verified
        self.version = "1.0"

    def probe(self) -> HostProbe:
        return HostProbe("test", self.version, "test-os", self.verified, self.verified,
                         "host_acknowledged", "a" * 64 if self.verified else None)

    def configuration_path(self) -> Path:
        return self.path

    def planned_configuration(self, previous: bytes | None) -> bytes:
        return (previous or b"") + b"\nAtMem Code hook\n"


def test_exact_prior_config_is_restored(tmp_path) -> None:
    path = tmp_path / "host.json"
    path.write_bytes(b"original bytes\n")
    transaction = HostConfigTransaction(_Adapter(path))
    assert transaction.preview()["existed"] is True
    transaction.apply()
    assert b"AtMem Code" in path.read_bytes()
    transaction.restore()
    assert path.read_bytes() == b"original bytes\n"


def test_unverified_or_changed_config_fails_closed(tmp_path) -> None:
    path = tmp_path / "host.json"
    path.write_bytes(b"prior")
    with pytest.raises(RuntimeError, match="unverified"):
        HostConfigTransaction(_Adapter(path, verified=False)).apply()
    transaction = HostConfigTransaction(_Adapter(path))
    path.write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="changed"):
        transaction.apply()


def test_created_file_can_be_removed_but_not_after_external_edit(tmp_path) -> None:
    path = tmp_path / "host.json"
    transaction = HostConfigTransaction(_Adapter(path))
    transaction.apply()
    path.write_bytes(b"owner changed it")
    with pytest.raises(RuntimeError, match="changed after activation"):
        transaction.restore()
    assert path.read_bytes() == b"owner changed it"


def test_host_upgrade_after_preview_blocks_install(tmp_path) -> None:
    adapter = _Adapter(tmp_path / "host.json")
    transaction = HostConfigTransaction(adapter)
    adapter.version = "2.0"
    with pytest.raises(RuntimeError, match="version or platform changed"):
        transaction.apply()
