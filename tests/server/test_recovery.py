import os
from atmem.store.sqlite import SQLiteStore
from atmem.server.recovery import encrypted_backup, verified_restore
def test_encrypted_verified_backup_restore(tmp_path):
    source=SQLiteStore(tmp_path/"source.db"); backup=tmp_path/"backup.bin"; key=os.urandom(32)
    receipt=encrypted_backup(source,backup,key); assert b"SQLite format" not in backup.read_bytes(); assert receipt["bytes"]>0
    target=SQLiteStore(tmp_path/"target.db"); assert verified_restore(target,backup,key)["verified"]
    source.close(); target.close()
