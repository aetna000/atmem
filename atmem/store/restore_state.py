"""Content-free restore witnesses for the supported canonical restore API.

This is not a monotonic external witness: copying a whole database, witness,
feedback store and its keys can roll back all of them. Arbitrary filesystem
copies remain an operator reconciliation procedure.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import uuid

from atmem.durability import fsync_directory
from atmem.private_paths import private_path, protect_private_path

FORMAT = 'atmem-canonical-restore-v1'


def _extended(path):
    path = str(Path(path).absolute())
    if os.name == 'nt' and not path.startswith('\\\\?\\'):
        path = '\\\\?\\UNC\\'+path[2:] if path.startswith('\\\\') else '\\\\?\\'+path
    return Path(path)


def _path(store):
    path=Path(store.path).expanduser().resolve()
    # Do not repeat a potentially long database basename in the witness name.
    return _extended(path.parent/('.restore-'+sha256(str(path).encode()).hexdigest()[:16]+'.json'))


def read_restore_state(store):
    if store.path == ':memory:':
        value=getattr(store,'_restore_state',None)
        return dict(value) if value is not None else None
    path=_path(store)
    try:
        with path.open('rb') as stream:
            raw=stream.read(4097)
        if not private_path(path):
            raise RuntimeError('canonical restore witness is not private')
        value=json.loads(raw)
        if (len(raw)>4096 or type(value) is not dict
                or set(value)!={'format','restore_id','state'} or value['format']!=FORMAT
                or value['state'] not in ('pending','complete')
                or type(value['restore_id']) is not str or len(value['restore_id'])!=32
                or any(c not in '0123456789abcdef' for c in value['restore_id'])):
            raise ValueError('invalid canonical restore witness')
        return value
    except FileNotFoundError:
        return None
    except (OSError,ValueError,UnicodeError) as exc:
        raise RuntimeError('canonical restore witness is unavailable') from exc


def write_restore_state(store, *, restore_id, state):
    value={'format':FORMAT,'restore_id':restore_id,'state':state}
    if store.path == ':memory:':
        store._restore_state=value
        return
    path=_path(store)
    temporary=path.parent/('.'+uuid.uuid4().hex+'.tmp')
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_BINARY',0),0o600)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            protect_private_path(temporary)
            stream.write(json.dumps(value,sort_keys=True,separators=(',',':')).encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary,path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
