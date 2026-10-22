"""Encrypted derived-cache deletion and stale-access qualification, no models."""
from pathlib import Path

import pytest

from atmem.context_engine.cache_lifecycle import is_part_cache
from atmem.context_engine.contracts import ContextRequestV3
from atmem.context_engine.formation import FormationManager,SourceEpisode,SourcePart
from atmem.context_engine.part_semantic import SourcePartSemanticIndex
from atmem.context_engine.service import stored_manifest
from atmem.contracts.models import AuthorityScope
from atmem.memory import Memory
from atmem.service.household import HouseholdApplication


class Embedder:
    identity={'model':'plumbing-fixture','revision':'fixed','endpoint':'http://127.0.0.1:11434','truncate':False}
    def verify_identity(self):pass
    def embed_documents(self,texts):return [[1.,0.,0.] for _ in texts]


@pytest.fixture
def cached(tmp_path):
    pytest.importorskip('sqlcipher3')
    database=tmp_path/'memory.db'
    HouseholdApplication.initialize(database,encrypted=True,backend='file')
    memory=Memory(database,auto_vectors=False)
    manager=FormationManager(memory.store)
    opened=[]
    def create(subject='owner',*,path=None):
        scope=AuthorityScope(subject,'agent','workspace')
        gen=manager.begin_generation(scope,profile_id='context-fast')
        source=manager.retain_source(SourceEpisode(episode_id='source-'+subject,scope=scope,
            parts=(SourcePart('text',0,'text','text/plain',b'Fixture retained source.'),)))
        manager.form_source(source,gen,range_granularity='sentence')
        manager.verify_generation(gen);manager.activate_generation(gen)
        generation=manager.active_generation(scope)
        request=ContextRequestV3(context_id='context',request_id='request',scope=scope,
            query='retained source',profile_id='context-fast',generation=generation['canonical_generation'],
            turn_id='turn',mode='active')
        manifest=stored_manifest(memory.store,request,generation_id=gen)
        index=SourcePartSemanticIndex(memory.store,generation_id=gen,manifest=manifest,
            path=path or tmp_path/(gen+'.db'),model_identity=Embedder.identity)
        index.build(Embedder());opened.append(index)
        return gen,source,index,manifest
    yield memory,manager,create
    for index in opened:
        try:index.close()
        except Exception:pass
    memory.close()


def test_source_delete_physically_purges_registered_vectors_and_metadata(cached):
    memory,manager,create=cached
    gen,source,index,manifest=create()
    assert is_part_cache(memory.store.semantic_index_paths('owner')[0])
    assert index.connection.execute('SELECT COUNT(*) FROM part_vectors').fetchone()[0]>0
    receipt=manager.delete_source(source)
    assert receipt['deleted'] and receipt['semantic_cache_cleanup'][0]['verified_absent']
    assert index.connection.execute('SELECT COUNT(*) FROM part_vectors').fetchone()[0]==0
    assert index.connection.execute('SELECT COUNT(*) FROM part_index').fetchone()[0]==0
    with pytest.raises(ValueError,match='stale|deleted'):
        index.nominate([1,0,0],allowed_unit_ids=frozenset(manifest.authorized_unit_ids))


def test_subject_reset_does_not_purge_other_subject_in_shared_encrypted_cache(cached):
    memory,manager,create=cached
    _,_,index,_=create()
    _,_,other,_=create('other',path=index.path)
    memory.store.reset_subject('owner')
    assert index.connection.execute('SELECT COUNT(*) FROM part_vectors WHERE index_id=?',(index.index_id,)).fetchone()[0]==0
    assert other.connection.execute('SELECT COUNT(*) FROM part_vectors WHERE index_id=?',(other.index_id,)).fetchone()[0]>0


def test_retired_generation_cannot_serve_then_discard_cleans_vectors(cached):
    _,manager,create=cached
    gen,_,index,manifest=create()
    manager.retire_generation(gen)
    with pytest.raises(ValueError,match='retired'):
        index.nominate([1,0,0],allowed_unit_ids=frozenset(manifest.authorized_unit_ids))
    manager.discard_generation(gen)
    assert index.connection.execute('SELECT COUNT(*) FROM part_vectors').fetchone()[0]==0


def test_missing_cache_blocks_canonical_source_deletion(cached):
    memory,manager,create=cached
    gen,source,index,_=create()
    index.close()
    # Model an external rename, not a deletion. Restore it for fixture cleanup.
    moved=index.path.with_suffix('.moved');index.path.rename(moved)
    try:
        with pytest.raises(RuntimeError,match='deletion cannot be verified'):
            manager.delete_source(source)
        assert memory.store._conn.execute('SELECT 1 FROM context_source_episodes WHERE source_id=?',(source,)).fetchone()
        assert manager.active_generation(AuthorityScope('owner','agent','workspace'))['generation_id']==gen
    finally:moved.rename(index.path)


def test_reopening_pre_registry_cache_adopts_it_without_reembedding(cached):
    memory,manager,create=cached
    gen,source,index,manifest=create()
    memory.store._conn.execute('DELETE FROM semantic_index_registry WHERE subject_id=?',('owner',))
    index.close()
    adopted=SourcePartSemanticIndex(memory.store,generation_id=gen,manifest=manifest,
        path=index.path,model_identity=Embedder.identity)
    try:
        assert is_part_cache(memory.store.semantic_index_paths('owner')[0])
        with pytest.raises(ValueError,match='already built'):adopted.build(Embedder())
        assert manager.delete_source(source)['semantic_cache_cleanup'][0]['verified_absent']
        assert adopted.connection.execute('SELECT COUNT(*) FROM part_vectors').fetchone()[0]==0
    finally:adopted.close()


def test_legacy_record_forget_uses_cache_kind_not_legacy_vector_schema(cached):
    memory,_,create=cached
    _,_,index,_=create()
    memory.remember('owner','My editor is Vim.',force=True)
    result=memory.forget('owner','Vim')
    assert result['deleted']
    assert index.connection.execute('SELECT COUNT(*) FROM part_vectors').fetchone()[0]==0
    assert not index.connection.execute("SELECT 1 FROM sqlite_master WHERE name='vector_epochs'").fetchone()


def test_live_cache_rejects_deleted_unit_even_if_generation_revision_is_unchanged(cached):
    memory,_,create=cached
    gen,_,index,manifest=create()
    identity=manifest.authorized_unit_ids[0]
    memory.store._conn.execute("UPDATE context_evidence_units SET lifecycle='deleted' WHERE generation_id=? AND unit_id=?",(gen,identity))
    with pytest.raises(ValueError,match='authorization'):
        index.nominate([1,0,0],allowed_unit_ids=frozenset(manifest.authorized_unit_ids))


def test_cache_cannot_replace_canonical_or_other_registered_index_kind(cached):
    memory,_,create=cached
    gen,_,index,manifest=create()
    with pytest.raises(ValueError,match='separate from canonical'):
        SourcePartSemanticIndex(memory.store,generation_id=gen,manifest=manifest,
            path=memory.store.path,model_identity=Embedder.identity)
    memory.store.register_semantic_index('owner',str(index.path),active_epoch_id='legacy-index')
    with pytest.raises(ValueError,match='different registered index kind'):
        SourcePartSemanticIndex(memory.store,generation_id=gen,manifest=manifest,
            path=index.path,model_identity=Embedder.identity)


def test_health_does_not_open_part_cache_as_legacy_index(cached,monkeypatch):
    from types import SimpleNamespace
    from atmem.control.manager import ControlPlaneManager
    memory,_,create=cached
    _,_,index,_=create()
    manager=object.__new__(ControlPlaneManager)
    monkeypatch.setattr(manager,'state',lambda:SimpleNamespace(host='generic',subject_id='owner'))
    monkeypatch.setattr(manager,'_generic_memory_db',lambda state:memory.store.path)
    health=manager.semantic_health('owner')
    assert health['context_retrieval_caches'][0]['present'] is True
    assert not index.connection.execute("SELECT 1 FROM sqlite_master WHERE name='vector_epochs'").fetchone()
