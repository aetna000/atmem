"""Encrypted snapshot writers cannot silently overwrite another process."""
import os
import subprocess
import sys

import pytest

from atmem.control.store import ControlStore, reencrypt_control_container


def test_another_process_cannot_open_a_stale_writable_snapshot(tmp_path):
    path = tmp_path / "control.db"
    key = os.urandom(32)
    store = ControlStore(path, encryption_key=key)
    try:
        script = """
import sys
from atmem.control.store import ControlStore
try:
    store = ControlStore(sys.argv[1], encryption_key=bytes.fromhex(sys.argv[2]))
except BlockingIOError:
    print('busy')
else:
    store.close()
    raise SystemExit('unexpected concurrent writable snapshot')
"""
        process = subprocess.run([sys.executable, "-c", script, str(path), key.hex()],
                                 capture_output=True, text=True, timeout=15)
        assert process.returncode == 0, process.stderr
        assert process.stdout.strip() == "busy"
        with store.transaction():
            store._conn.execute("INSERT INTO schema_meta VALUES ('revocation-canary', 'revoked')")
        committed = path.read_bytes()
        store.close()
        assert path.read_bytes() == committed  # Clean close does not rewrite.
    finally:
        store.close()
    script = """
import sys
from atmem.control.store import ControlStore
store = ControlStore(sys.argv[1], encryption_key=bytes.fromhex(sys.argv[2]))
try:
    assert store._conn.execute("SELECT value FROM schema_meta WHERE key='revocation-canary'").fetchone()['value'] == 'revoked'
finally:
    store.close()
"""
    process = subprocess.run([sys.executable, "-c", script, str(path), key.hex()],
                             capture_output=True, text=True, timeout=15)
    assert process.returncode == 0, process.stderr


def test_encrypted_reopen_preserves_schema_and_existing_rows_without_rewrite(tmp_path):
    path = tmp_path / "control.db"
    key = os.urandom(32)
    store = ControlStore(path, encryption_key=key)
    with store.transaction():
        store._conn.execute("INSERT INTO schema_meta VALUES ('preserve', 'yes')")
    store.close()
    unchanged = path.read_bytes()
    upgraded = ControlStore(path, encryption_key=key)
    try:
        assert upgraded.schema_version() == 6
        assert upgraded._conn.execute("SELECT value FROM schema_meta WHERE key='preserve'").fetchone()["value"] == "yes"
    finally:
        upgraded.close()
    assert path.read_bytes() == unchanged


def test_reentrant_stale_snapshot_cannot_overwrite_a_nested_commit(tmp_path):
    path = tmp_path / "control.db"
    key = os.urandom(32)
    outer = ControlStore(path, encryption_key=key)
    inner = ControlStore(path, encryption_key=key)
    with inner.transaction():
        inner._conn.execute("INSERT INTO schema_meta VALUES ('preserve', 'revoked')")
    inner.close()
    outer._conn.execute("INSERT INTO schema_meta VALUES ('stale', 'must-not-write')")
    with pytest.raises(RuntimeError, match="changed"):
        outer.close()
    check = ControlStore(path, encryption_key=key)
    try:
        assert check._conn.execute("SELECT value FROM schema_meta WHERE key='preserve'").fetchone()["value"] == "revoked"
        assert check._conn.execute("SELECT value FROM schema_meta WHERE key='stale'").fetchone() is None
    finally:
        check.close()


def test_rotation_cannot_be_overwritten_by_reentrant_old_key_writer(tmp_path):
    path = tmp_path / "control.db"
    old, new = os.urandom(32), os.urandom(32)
    store = ControlStore(path, encryption_key=old)
    reencrypt_control_container(path, old, new)
    store._conn.execute("INSERT INTO schema_meta VALUES ('stale', 'must-not-write')")
    with pytest.raises(RuntimeError, match="changed"):
        store.close()
    reopened = ControlStore(path, encryption_key=new)
    try:
        assert reopened._conn.execute("SELECT value FROM schema_meta WHERE key='stale'").fetchone() is None
    finally:
        reopened.close()


def test_second_host_process_waits_then_reads_committed_state(tmp_path):
    path = tmp_path / "control.db"
    key = os.urandom(32)
    store = ControlStore(path, encryption_key=key)
    with store.transaction():
        store._conn.execute("INSERT INTO schema_meta VALUES ('host-one', 'committed')")
    script = """
import sys
from atmem.control.store import ControlStore
print('opening', flush=True)
store = ControlStore(sys.argv[1], encryption_key=bytes.fromhex(sys.argv[2]))
try:
    assert store._conn.execute("SELECT value FROM schema_meta WHERE key='host-one'").fetchone()['value'] == 'committed'
    with store.transaction():
        store._conn.execute("INSERT INTO schema_meta VALUES ('host-two', 'committed')")
finally:
    store.close()
"""
    child = subprocess.Popen([sys.executable, "-c", script, str(path), key.hex()],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "opening"
        store.close()
        _, error = child.communicate(timeout=10)
        assert child.returncode == 0, error
    finally:
        store.close()
        if child.poll() is None:
            child.kill()
            child.wait()
    check = ControlStore(path, encryption_key=key)
    try:
        assert check._conn.execute("SELECT value FROM schema_meta WHERE key='host-two'").fetchone()["value"] == "committed"
    finally:
        check.close()
