from __future__ import annotations
import importlib.util,json,os,subprocess,sys
from pathlib import Path
import pytest
from atmem.chatgpt.config import Settings

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('package_chatgpt_plugin',ROOT/'scripts/package_chatgpt_plugin.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)


def source_files():
    return package.load_files()


def test_development_package_is_reproducible_and_inspected(tmp_path):
    files=source_files();assert package.validate(files)==[]
    a=tmp_path/'one.zip';b=tmp_path/'two.zip'
    assert package.archive(a,files)==package.archive(b,files)
    assert a.read_bytes()==b.read_bytes()
    assert package.validate(files,public=True)


def test_initial_package_has_real_mcp_auth_and_complete_review_cases():
    files=source_files();mcp=json.loads(files['mcp.json']);assert len(mcp['mcpServers'])==1
    server=mcp['mcpServers']['atmem'];assert server['type']=='streamable-http'
    assert server['extensions']['com.openai']['auth']['type']=='oauth'
    cases=json.loads(files['plugin.json'])['extensions']['com.openai']['review']['test_cases']
    assert len(cases['positive'])==5 and len(cases['negative'])==3


def test_public_preparation_refuses_placeholder_urls_and_secrets(tmp_path):
    files=source_files();manifest=json.loads(files['plugin.json'])
    assert any('privacyPolicyURL' in s for s in package.validate(files,public=True))
    mcp=json.loads(files['mcp.json']);mcp['mcpServers']['atmem']['headers']={'Authorization':'Bearer TEST-ONLY-NOT-A-REAL-TOKEN'}
    files['mcp.json']=json.dumps(mcp).encode();assert any('headers' in s for s in package.validate(files))


def test_init_is_isolated_and_repeat_does_not_overwrite(tmp_path):
    root=tmp_path/'runtime'
    result=subprocess.run([sys.executable,'-m','atmem.chatgpt','init-test','--directory',str(root)],capture_output=True,text=True,check=True,cwd=ROOT)
    receipt=json.loads(result.stdout);assert receipt['test_only'] and not receipt['key_exposed']
    key=(root/'service.key').read_bytes()
    repeated=subprocess.run([sys.executable,'-m','atmem.chatgpt','init-test','--directory',str(root)],capture_output=True,text=True,cwd=ROOT)
    assert repeated.returncode!=0 and (root/'service.key').read_bytes()==key


def config(tmp_path):
    key=tmp_path/'master.key';key.write_text('de'*32);key.chmod(0o600)
    return {'home':str(tmp_path/'home'),'project':'demo-atmem-plugin','issuer':'http://127.0.0.1:8769',
        'key_file':str(key),'firebase_api_key':'emulator','emulator':True,'clients':{'test':['http://127.0.0.1:9901/callback']}}


def test_configuration_never_selects_real_home_or_emulators_in_production(tmp_path,monkeypatch):
    v=config(tmp_path);v['home']=str(Path.home()/'.atmem')
    path=tmp_path/'config.json';path.write_text(json.dumps(v))
    with pytest.raises(ValueError,match='dedicated home'):Settings.load(path)
    v=config(tmp_path);v['emulator']=False;v['issuer']='https://mcp.example.invalid';v['clients']={'test':['https://client.example.invalid/callback']}
    path.write_text(json.dumps(v));monkeypatch.setenv('FIRESTORE_EMULATOR_HOST','127.0.0.1:8085')
    with pytest.raises(ValueError,match='emulator environment'):Settings.load(path)


def test_configuration_checks_key_permissions_and_invited_accounts(tmp_path,monkeypatch):
    v=config(tmp_path);v['emulator']=False;v['issuer']='https://mcp.example.invalid';v['clients']={'test':['https://client.example.invalid/callback']}
    for name in ['FIRESTORE_EMULATOR_HOST','FIREBASE_AUTH_EMULATOR_HOST','ATMEM_HOME']:monkeypatch.delenv(name,raising=False)
    path=tmp_path/'config.json';path.write_text(json.dumps(v))
    with pytest.raises(ValueError,match='invited'):Settings.load(path)
    v['allowed_firebase_uids']=['synthetic-uid'];path.write_text(json.dumps(v))
    Path(v['key_file']).chmod(0o644)
    if os.name!='nt':
        with pytest.raises(ValueError,match='0600'):Settings.load(path)


def test_named_database_is_selected_and_invalid_paths_rejected(tmp_path,monkeypatch):
    from unittest.mock import patch
    from atmem.chatgpt.repository import Repository
    v=config(tmp_path);v['database']='atmem-chatgpt'
    monkeypatch.setenv('FIRESTORE_EMULATOR_HOST','127.0.0.1:8085')
    monkeypatch.setenv('FIREBASE_AUTH_EMULATOR_HOST','127.0.0.1:9099')
    monkeypatch.delenv('ATMEM_HOME',raising=False)
    path=tmp_path/'config.json';path.write_text(json.dumps(v))
    settings=Settings.load(path)
    with patch('atmem.chatgpt.repository.firestore.Client') as client:
        Repository(settings)
        assert client.call_args.kwargs['database']=='atmem-chatgpt'
    v['database']='../(default)';path.write_text(json.dumps(v))
    with pytest.raises(ValueError,match='database ID'):Settings.load(path)


def test_cloud_candidate_uses_real_https_cimd_without_credentials():
    files=source_files();override=json.loads((ROOT/'deploy/chatgpt/cloud-package-metadata.json').read_text())
    files['mcp.json']=json.dumps(override['mcp']).encode()
    assert package.validate(files)==[]
    mcp=json.loads(files['mcp.json']);client=mcp['mcpServers']['atmem']['extensions']['com.openai']['auth']['client']
    assert client=={'mode':'cimd'}
    client['clientId']='not-allowed-for-cimd';files['mcp.json']=json.dumps(mcp).encode()
    assert any('CIMD' in error for error in package.validate(files))


def test_codex_private_archive_passes_unmodified_transport_schema(tmp_path):
    import zipfile
    import jsonschema

    original = source_files()
    metadata = json.loads((ROOT / 'deploy/chatgpt/cloud-package-metadata.json').read_text())
    original['mcp.json'] = json.dumps(metadata['mcp']).encode()
    output = tmp_path / 'codex.zip'
    package.archive(output, package.codex_private_files(original))
    with zipfile.ZipFile(output) as archive:
        mcp = json.loads(archive.read('atmem-chatgpt/mcp.json'))
    schema = json.loads((ROOT / 'tests/fixtures/chatgpt/mcp.schema.json').read_text())
    jsonschema.Draft202012Validator(schema).validate(mcp)
    assert mcp['mcpServers']['atmem'] == {
        'type': 'streamable-http', 'url': metadata['mcp']['mcpServers']['atmem']['url']
    }
    assert 'extensions' in json.loads(original['mcp.json'])['mcpServers']['atmem']
    with pytest.raises(ValueError, match='hosted HTTPS'):
        package.codex_private_files(source_files())
