from atmem.core.storage import DerivedGeneration
from atmem.semantic.pgvector import PgVectorIndex
from atmem.semantic.qdrant import QdrantIndex
from atmem.store.sqlite import SQLiteStore

class Cursor:
    def __enter__(self): return self
    def __exit__(self,*_): pass
    def execute(self,*_): pass
class Connection:
    def cursor(self): return Cursor()
    def commit(self): pass
class Client:
    def __init__(self): self.calls=[]
    def delete(self,**kwargs): self.calls.append(kwargs)

def test_backup_restore_and_generation_bound_derived_lifecycle(tmp_path):
    source=SQLiteStore(tmp_path/"a.db"); backup=tmp_path/"backup.db"; source.backup_to(backup)
    target=SQLiteStore(tmp_path/"b.db"); assert target.restore_from(backup)["integrity"]=="ok"
    generation=DerivedGeneration("g1",1,"a"*64,"b"*64)
    pg=PgVectorIndex(Connection()); qclient=Client(); q=QdrantIndex(qclient)
    pg.activate("s",generation); q.activate("s",generation)
    assert pg.active_generation("s").canonical_generation==1
    for adapter in (pg,q):
        try: adapter.discard_generation("s","g1")
        except ValueError: pass
        else: raise AssertionError("active generation deletion must fail")
    source.close(); target.close()
