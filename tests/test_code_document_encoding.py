"""Storage boundary fixtures only; no benchmark-quality or model claims."""
import base64
from hashlib import sha256
import json
import random
import zlib

import pytest

from atmem.store import code_documents as codec
from atmem.store.sqlite import SQLiteStore

BINDING = dict(subject='owner',project='project',kind='knowledge-generation',identity='generation-1')


@pytest.fixture
def small_bounds(monkeypatch):
    monkeypatch.setattr(codec,'PHYSICAL_LIMIT',512)
    monkeypatch.setattr(codec,'LOGICAL_LIMIT',4096)


def packed():
    return codec.encode_document({'source':'text'*500},**BINDING)


def altered(change):
    row=json.loads(packed());change(row[1]);return json.dumps(row)


def test_ordinary_and_marker_named_objects_keep_legacy_representation():
    value={'format':codec.FORMAT,'payload_base64':'ordinary logical application data','東京':True}
    wire=codec.encode_document(value,**BINDING)
    assert json.loads(wire)==value
    assert codec.decode_document(wire,**BINDING)==value


def test_above_real_16mb_roundtrip_and_physical_row_bound():
    value={'source':'x'*16_000_010,'artifacts':{'original':'all bytes retained'}}
    wire=codec.encode_document(value,**BINDING)
    assert json.loads(wire)[0]==codec.FORMAT
    assert len(wire.encode())<=16_000_000
    assert codec.decode_document(wire,**BINDING)==value


@pytest.mark.parametrize('field',['subject','project','kind','identity'])
def test_compressed_rows_cannot_be_rebound(small_bounds,field):
    binding={**BINDING,field:'different'}
    with pytest.raises(codec.CodeDocumentEncodingError):
        codec.decode_document(packed(),**binding)


@pytest.mark.parametrize('change',[
    lambda h:h.update(raw_bytes=True),lambda h:h.update(raw_bytes=0),
    lambda h:h.update(raw_bytes=4097),lambda h:h.update(raw_bytes=h['raw_bytes']-1),
    lambda h:h.update(raw_sha256='0'*64),lambda h:h.update(raw_sha256='invalid'),
    lambda h:h.update(identity_sha256='0'*64),lambda h:h.update(payload_base64='!not-base64!'),
    lambda h:h.update(extra='not a supported field'),
])
def test_invalid_headers_and_hashes_rejected(small_bounds,change):
    with pytest.raises(codec.CodeDocumentEncodingError):
        codec.decode_document(altered(change),**BINDING)


@pytest.mark.parametrize('suffix',[b'extra',zlib.compress(b'concatenated')])
def test_trailing_and_concatenated_streams_rejected(small_bounds,suffix):
    wire=altered(lambda h:h.update(payload_base64=base64.b64encode(
        base64.b64decode(h['payload_base64'])+suffix).decode()))
    with pytest.raises(codec.CodeDocumentEncodingError):
        codec.decode_document(wire,**BINDING)


def test_truncated_stream_and_small_declared_bomb_rejected(small_bounds):
    bad=altered(lambda h:h.update(payload_base64=base64.b64encode(
        base64.b64decode(h['payload_base64'])[:-1]).decode()))
    with pytest.raises(codec.CodeDocumentEncodingError):
        codec.decode_document(bad,**BINDING)
    raw=b' ' * 100_000
    bad=altered(lambda h:h.update(raw_bytes=1024,raw_sha256=sha256(raw).hexdigest(),
                                 payload_base64=base64.b64encode(zlib.compress(raw)).decode()))
    with pytest.raises(codec.CodeDocumentEncodingError):
        codec.decode_document(bad,**BINDING)


@pytest.mark.parametrize('raw',[b'['+b' '*1000+b']',b'{"a":1,"a":2'+b' '*1000+b'}',
                              b'{"a":NaN'+b' '*1000+b'}',b'{"a":"\xff"'+b' '*1000+b'}'])
def test_invalid_logical_json_rejected_even_with_matching_size_and_hash(small_bounds,raw):
    bad=altered(lambda h:h.update(raw_bytes=len(raw),raw_sha256=sha256(raw).hexdigest(),
                                 payload_base64=base64.b64encode(zlib.compress(raw)).decode()))
    with pytest.raises(codec.CodeDocumentEncodingError):
        codec.decode_document(bad,**BINDING)


def test_write_bounds_do_not_enable_other_kinds_or_discard_data(small_bounds):
    with pytest.raises(codec.CodeDocumentEncodingError):
        codec.encode_document({'large':'x'*5000},**BINDING)
    with pytest.raises(codec.CodeDocumentEncodingError):
        codec.encode_document({'large':'x'*1000},**{**BINDING,'kind':'settings'})
    raw=random.Random(0).randbytes(2000)
    with pytest.raises(codec.CodeDocumentEncodingError,match='physical'):
        codec.encode_document({'random':base64.b64encode(raw).decode()},**BINDING)
    with pytest.raises(codec.CodeDocumentEncodingError):
        codec.encode_document([codec.FORMAT,{}],**BINDING)


def test_all_store_reads_are_logical_scoped_and_transactional(small_bounds):
    store=SQLiteStore()
    value={'source':'text'*500}
    try:
        store.put_code_document('owner','project','knowledge-generation','generation-1',value)
        assert store.code_document('owner','project','knowledge-generation','generation-1')==value
        assert store.code_documents('owner','project','knowledge-generation')==[value]
        assert store.code_document_items('owner','project','knowledge-generation')==[
            {'document_id':'generation-1','value':value}]
        assert store.code_document('other','project','knowledge-generation','generation-1') is None
        assert store.code_documents('owner','other','knowledge-generation')==[]
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.put_code_document('owner','project','knowledge-generation','generation-1',{'source':'new'*500})
                raise RuntimeError('interrupted publication')
        assert store.code_document('owner','project','knowledge-generation','generation-1')==value
        store.put_code_document('owner','project','knowledge-generation','generation-1',{'small':'replacement'})
        assert store.code_documents('owner','project','knowledge-generation')==[{'small':'replacement'}]
        store.delete_code_documents('owner','project','knowledge-generation','generation-1')
        assert store.code_document_items('owner','project','knowledge-generation')==[]
    finally:store.close()


def test_corrupt_generation_is_withheld_but_canonical_memory_remains_usable(code_env):
    from tests.test_knowledge_lifecycle import init_repository,FixtureWorker
    from atmem.knowledge.projections import CodeKnowledge
    env=code_env;init_repository(env)
    knowledge=CodeKnowledge(env.app,env.scope)
    knowledge.index(str(env.root),FixtureWorker())
    env.memory.store._conn.execute("UPDATE code_documents SET payload_json=? WHERE kind='knowledge-generation'",
                                   (json.dumps([codec.FORMAT,{}]),))
    assert knowledge.current(str(env.root)) is None
    assert knowledge.context(str(env.root),'main',budget=4096)['status']=='not_current'
    # A corrupt derived row must not authorize partial evidence or disable
    # ordinary deterministic memory. New indexing refuses to overwrite it.
    assert env.seed()
    with pytest.raises(codec.CodeDocumentEncodingError):
        knowledge.index(str(env.root),FixtureWorker())


def large_generation(env):
    from tests.test_knowledge_lifecycle import init_repository,FixtureWorker
    from atmem.knowledge.projections import CodeKnowledge
    from atmem.knowledge.code.extractor import ExtractionArtifacts
    init_repository(env)
    class LargeArtifacts(FixtureWorker):
        def extract(self,*args,**kwargs):
            original=super().extract(*args,**kwargs)
            return ExtractionArtifacts(original.facts_jsonl+b' '*12_000_000+b'\n',
                                       original.receipt_json,original.insights_json)
    knowledge=CodeKnowledge(env.app,env.scope)
    assert knowledge.index(str(env.root),LargeArtifacts())['status']=='published'
    value=knowledge.current(str(env.root))
    assert len(json.dumps(value).encode())>16_000_000
    return value


def test_large_original_artifacts_survive_encrypted_bundle_restore_and_clear(code_env,tmp_path):
    from tests.test_knowledge_portable import bundle_for
    from atmem.code.application import CodeApplication
    from atmem.code.portable import CodePortable
    from atmem.code.deletion import CodeDeletion
    from atmem.memory import Memory
    env=code_env;original=large_generation(env)
    bundle,secret,signer=bundle_for(env)
    target=Memory(':memory:',auto_vectors=False)
    root=tmp_path/'new-clone';root.mkdir()
    try:
        app=CodeApplication(target,subject_id='local');portable=CodePortable(app)
        value=portable.open(bundle,recipient_secret_key=secret,trusted_signing_public_key=signer)
        retained=value['state']['documents']['knowledge-generation'][0]
        assert retained['value']==original
        preview=portable.preview(value,root=str(root))
        assert portable.restore(value,root=str(root),preview_token=preview['preview_token'])['imported']
        assert target.store.code_document('local',env.project,'knowledge-generation',retained['document_id'])==original
        deletion=CodeDeletion(app);preview=deletion.preview(env.project)
        assert deletion.clear(env.project,preview['preview_token'])['local_verified']
        assert target.store.code_documents('local',env.project,'knowledge-generation')==[]
        # Clearing the restored project did not touch the original authority.
        assert env.memory.store.code_documents('local',env.project,'knowledge-generation')==[original]
    finally:target.close()


def test_large_document_reopens_from_real_encrypted_household(tmp_path,monkeypatch):
    pytest.importorskip('sqlcipher3')
    from atmem.core.keys import initialize_encrypted_household
    monkeypatch.setattr('atmem.core.keys.DEFAULT_KEY_PATH',tmp_path/'keys/db.key')
    monkeypatch.delenv('ATMEM_DB_KEY',raising=False)
    database=tmp_path/'memory.db';initialize_encrypted_household(database,backend='file')
    value={'original':'CODE_GENERATION_ENCRYPTION_CANARY_'+'x'*16_000_010}
    store=SQLiteStore(database)
    try:store.put_code_document('owner','project','knowledge-generation','generation-1',value)
    finally:store.close()
    assert b'CODE_GENERATION_ENCRYPTION_CANARY_' not in database.read_bytes()
    assert not database.read_bytes().startswith(b'SQLite format 3')
    reopened=SQLiteStore(database)
    try:assert reopened.code_document('owner','project','knowledge-generation','generation-1')==value
    finally:reopened.close()
