"""Encoding boundary fixtures, not benchmark quality or training data."""
import base64
import codecs
from hashlib import sha256
import io
import tarfile

import pytest

from atmem.knowledge.source_text import source_text
from atmem.knowledge.contracts import SourceSnapshot
from atmem.knowledge.worker import source_archive
from tests.test_knowledge_extraction import SCOPE


@pytest.mark.parametrize('encoding',['utf-8','utf-8-sig','utf-16','utf-32'])
def test_explicit_text_encodings_have_identical_presentation(encoding):
    text='café 東京\nnext line\n'
    assert source_text('notes.txt',text.encode(encoding))==text


def test_utf32_both_byte_orders_precede_utf16_bom():
    for bom,encoding in [(codecs.BOM_UTF32_LE,'utf-32-le'),(codecs.BOM_UTF32_BE,'utf-32-be')]:
        assert source_text('notes.txt',bom+'café\n'.encode(encoding))=='café\n'


def test_utf16_both_byte_orders():
    for bom,encoding in [(codecs.BOM_UTF16_LE,'utf-16-le'),(codecs.BOM_UTF16_BE,'utf-16-be')]:
        assert source_text('notes.txt',bom+'café\n'.encode(encoding))=='café\n'


def test_declared_python_encoding_and_utf8_bom():
    text='# coding: iso-8859-1\ndef café(): return "olé"\n'
    assert source_text('main.py',text.encode('iso-8859-1'))==text
    assert source_text('main.py',codecs.BOM_UTF8+b'def main(): pass\n')=='def main(): pass\n'


@pytest.mark.parametrize('name,data',[
    ('main.py',b'# coding: invented_codec\npass\n'),
    ('main.py',codecs.BOM_UTF8+b'# coding: iso-8859-1\npass\n'),
    ('main.py',b'# coding: utf-8\nvalue="\xff"\n'),
    ('notes.txt',b'caf\xe9'),
    ('notes.txt',codecs.BOM_UTF16_LE+b'\x01'),
    ('notes.txt',codecs.BOM_UTF32_LE+b'\x01'),
])
def test_malformed_or_undeclared_encoding_never_gets_lossy_fallback(name,data):
    with pytest.raises(ValueError,match='encoding is invalid'):
        source_text(name,data)


@pytest.mark.parametrize('name,raw',[
    ('main.py','# coding: latin-1\ndef café(): return "olé"\n'.encode('latin-1')),
    ('notes.txt','café 東京\n'.encode('utf-16')),
    ('notes.txt','café 東京\n'.encode('utf-32')),
])
def test_worker_archive_preserves_original_bytes_and_identity(name,raw):
    snapshot=SourceSnapshot(SCOPE,'worktree','a'*40,((name,sha256(raw).hexdigest()),),'a'*64)
    with tarfile.open(fileobj=io.BytesIO(source_archive(snapshot,{name:raw}))) as archive:
        assert archive.extractfile(name).read()==raw


@pytest.mark.parametrize('encoding',['utf-8','utf-8-sig','utf-16','utf-32','latin-1'])
def test_secret_screening_sees_decoded_content_before_worker_archive(encoding):
    name='secret.py' if encoding=='latin-1' else 'secret.txt'
    text=('' if name.endswith('.txt') else '# coding: latin-1\n')+'api_key = "sk-proj-'+('x'*60)+'"\n'
    raw=text.encode(encoding)
    snapshot=SourceSnapshot(SCOPE,'worktree','a'*40,((name,sha256(raw).hexdigest()),),'a'*64)
    with pytest.raises(ValueError,match='secret screening'):
        source_archive(snapshot,{name:raw})


@pytest.mark.parametrize('encoding',['utf-8','utf-8-sig','utf-16','utf-32','latin-1'])
def test_capture_excludes_encoded_secret_before_extraction(code_env,encoding):
    from tests.test_knowledge_lifecycle import init_repository
    from atmem.knowledge.projections import CodeKnowledge
    env=code_env;init_repository(env)
    name='secret.py' if encoding=='latin-1' else 'secret.txt'
    text=('' if name.endswith('.txt') else '# coding: latin-1\n')+'api_key = "sk-proj-'+('x'*60)+'"\n'
    (env.root/name).write_bytes(text.encode(encoding))
    snapshot,files,exclusions=CodeKnowledge(env.app,env.scope).capture(str(env.root),'a'*64)
    assert name not in files and name not in dict(snapshot.files)
    assert exclusions['secret_screen']==1


def test_strict_capture_rejects_invalid_encoding_and_graph_excludes_it_explicitly(code_env):
    from tests.test_knowledge_lifecycle import init_repository,FixtureWorker
    from atmem.knowledge.projections import CodeKnowledge
    env=code_env;init_repository(env)
    (env.root/'broken.py').write_bytes(b'# coding: unknown_codec\npass\n')
    knowledge=CodeKnowledge(env.app,env.scope)
    with pytest.raises(ValueError,match='encoding is invalid'):
        knowledge.capture(str(env.root),'a'*64)
    assert env.memory.store.code_documents('local',env.project,'knowledge-job')==[]
    indexed=knowledge.index(str(env.root),FixtureWorker())
    assert indexed['excluded_counts']['source_encoding']==1
    value=knowledge.current(str(env.root))
    assert 'broken.py' not in value['source_bytes']
    assert 'broken.py' not in dict(value['snapshot']['files'])
    assert knowledge.context(str(env.root),'main',budget=4096)['excluded_counts']['source_encoding']==1
    (env.root/'second.py').write_bytes(b'# coding: unknown_codec\npass\n')
    assert knowledge.current(str(env.root)) is None
    assert knowledge.index(str(env.root),FixtureWorker())['excluded_counts']['source_encoding']==2


def test_invalid_encoding_omission_race_cannot_publish(code_env):
    from tests.test_knowledge_lifecycle import init_repository,FixtureWorker
    from atmem.knowledge.projections import CodeKnowledge
    env=code_env;init_repository(env)
    class Racing(FixtureWorker):
        def extract(self,*args,**kwargs):
            result=super().extract(*args,**kwargs)
            (env.root/'broken.py').write_bytes(b'# coding: unknown_codec\npass\n')
            return result
    with pytest.raises(ValueError,match='changed before publication'):
        CodeKnowledge(env.app,env.scope).index(str(env.root),Racing())
    assert env.memory.store.code_documents('local',env.project,'knowledge-generation')==[]


def test_capture_packing_and_source_view_agree_and_stale_source_withheld(code_env):
    from tests.test_knowledge_lifecycle import init_repository,FixtureWorker
    from atmem.knowledge.projections import CodeKnowledge
    env=code_env;init_repository(env)
    raw='# coding: latin-1\ndef main():\n    return "café"\n'.encode('latin-1')
    (env.root/'main.py').write_bytes(raw)
    (env.root/'notes.txt').write_bytes('café 東京\n'.encode('utf-32'))
    from tests.test_knowledge_extraction import artifacts,fact
    class EncodedWorker(FixtureWorker):
        def extract(self,snapshot,files,*,authorize):
            authorize(snapshot.scope)
            return artifacts([fact(line=2)])
    knowledge=CodeKnowledge(env.app,env.scope)
    assert knowledge.index(str(env.root),EncodedWorker())['status']=='published'
    value=knowledge.current(str(env.root))
    assert base64.b64decode(value['source_bytes']['main.py'])==raw
    assert dict(value['snapshot']['files'])['main.py']==sha256(raw).hexdigest()
    pack=knowledge.context(str(env.root),'main',budget=4096)
    assert 'return "café"' in pack['content']
    answer=env.app.dispatch('knowledge-source',{'project_id':env.project,'root':str(env.root),
                                             'path':'main.py','line_count':3})
    assert answer['content']==source_text('main.py',raw).rstrip('\n')
    assert answer['source_sha256']==sha256(raw).hexdigest()
    from tests.test_knowledge_portable import bundle_for
    from atmem.code.portable import CodePortable
    bundle,secret,signer=bundle_for(env)
    restored=CodePortable(env.app).open(bundle,recipient_secret_key=secret,trusted_signing_public_key=signer)
    retained=restored['state']['documents']['knowledge-generation'][0]['value']
    assert base64.b64decode(retained['source_bytes']['main.py'])==raw
    assert retained['source_bytes']['notes.txt']==value['source_bytes']['notes.txt']
    (env.root/'main.py').write_bytes(raw+b'# changed\n')
    assert knowledge.current(str(env.root)) is None
