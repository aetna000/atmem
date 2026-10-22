import hashlib
import io
import json
import tarfile

import pytest

from research.retrieval_2310.archive_stages import add_verified_snapshot,protocol_supplements,screen_nested_archive


@pytest.mark.parametrize('payload',[b'ordinary source',b'the second secret is present'])
def test_streaming_screen_checks_multiple_secrets_without_seeking_backwards(tmp_path,payload):
    path=tmp_path/'source.tar.gz'
    with tarfile.open(path,'w:gz') as archive:
        info=tarfile.TarInfo('source.py');info.size=len(payload)
        archive.addfile(info,io.BytesIO(payload))
    secrets=[b'first secret absent',b'second secret']
    if b'second secret' in payload:
        with pytest.raises(ValueError,match='secret screen'):screen_nested_archive(path,secrets)
    else:screen_nested_archive(path,secrets)


def test_streaming_screen_still_rejects_path_escape(tmp_path):
    path=tmp_path/'source.tar.gz'
    with tarfile.open(path,'w:gz') as archive:
        info=tarfile.TarInfo('../escape');info.size=1
        archive.addfile(info,io.BytesIO(b'x'))
    with pytest.raises(ValueError,match='unsafe'):screen_nested_archive(path,[])


def test_tar_contains_the_verified_bytes_even_if_original_changes_before_stat(tmp_path,monkeypatch):
    source=tmp_path/'source.json';source.write_bytes(b'original evidence')
    expected={'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'bytes':source.stat().st_size}
    original=tarfile.TarFile.gettarinfo
    def changing_stat(archive,*args,**kwargs):
        source.write_bytes(b'changed after the capture')
        return original(archive,*args,**kwargs)
    monkeypatch.setattr(tarfile.TarFile,'gettarinfo',changing_stat)
    target=tmp_path/'snapshot.tar'
    with tarfile.open(target,'w') as archive:
        add_verified_snapshot(archive,source,name='evidence.json',expected=expected,diagnostics=tmp_path)
    with tarfile.open(target) as archive:
        assert archive.extractfile('evidence.json').read()==b'original evidence'
    assert source.read_bytes()==b'changed after the capture'


def test_changed_inventory_is_rejected_with_precise_diagnostics(tmp_path):
    source=tmp_path/'source.json';source.write_bytes(b'current evidence')
    expected={'sha256':'0'*64,'bytes':16}
    with tarfile.open(tmp_path/'rejected.tar','w') as archive:
        with pytest.raises(ValueError,match='evidence.json'):
            add_verified_snapshot(archive,source,name='evidence.json',expected=expected,diagnostics=tmp_path)
        assert not archive.getmembers()
    record=json.loads((tmp_path/'source-drift.json').read_text())
    assert record['path']==str(source) and record['expected']==expected
    assert record['observed']['sha256']==hashlib.sha256(source.read_bytes()).hexdigest()


def test_explicit_protocol_sources_and_terminal_logs_are_in_the_backup(tmp_path):
    script=tmp_path/'run.py';script.write_text('pass\n')
    log=tmp_path/'terminal.log';log.write_text('completed\n')
    assert protocol_supplements([script,log],campaign=tmp_path)=={
        'frozen-protocol/run.py':script,'frozen-protocol/terminal.log':log}
    with pytest.raises(ValueError,match='duplicate'):
        protocol_supplements([script,script],campaign=tmp_path)


@pytest.mark.parametrize('name',['.hidden.py','credential.log','listener.txt','settings.env'])
def test_protocol_supplements_do_not_widen_secret_or_hidden_file_collection(tmp_path,name):
    path=tmp_path/name;path.write_text('not permitted')
    with pytest.raises(ValueError,match='explicit private'):
        protocol_supplements([path],campaign=tmp_path)


def test_protocol_supplements_reject_source_links_and_outside_paths(tmp_path):
    campaign=tmp_path/'campaign';campaign.mkdir()
    outside=tmp_path/'outside.py';outside.write_text('pass\n')
    link=campaign/'linked.py';link.symlink_to(outside)
    for path in (outside,link):
        with pytest.raises(ValueError,match='explicit private'):
            protocol_supplements([path],campaign=campaign)
