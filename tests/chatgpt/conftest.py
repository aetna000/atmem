from __future__ import annotations
import base64,hashlib,json,os,re,secrets,socket,subprocess,sys,time
from pathlib import Path
from urllib.parse import urlencode,urlparse,parse_qs
import pytest
httpx=pytest.importorskip("httpx")
pytest.importorskip("mcp")
pytest.importorskip("google.cloud.firestore")
pytest.importorskip("sqlcipher3")

ROOT=Path(__file__).resolve().parents[2]


def csrf(response):
    match=re.search(r'name="csrf" value="([^"]+)"',response.text)
    assert match,response.text
    return match[1]


class Harness:
    def __init__(self,root,config,process,env,port):
        self.root=root;self.config=config;self.process=process;self.env=env
        self.base=f'http://127.0.0.1:{port}';self.users=[]
    def user(self,scopes='memory:read memory:write memory:delete'):
        email=f'test-{secrets.token_hex(8)}@example.invalid';password=secrets.token_urlsafe(24)
        response=httpx.post('http://'+self.env['FIREBASE_AUTH_EMULATOR_HOST']+'/identitytoolkit.googleapis.com/v1/accounts:signUp',params={'key':'emulator'},json={'email':email,'password':password,'returnSecureToken':True})
        assert response.status_code==200,response.text
        user={'uid':response.json()['localId'],'email':email,'password':password,'browser':httpx.Client(follow_redirects=False,timeout=20)}
        self.users.append(user)
        verifier=secrets.token_urlsafe(48)
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        params={'response_type':'code','client_id':'atmem-test-client','redirect_uri':'http://127.0.0.1:9901/callback','scope':scopes,'resource':self.base+'/mcp','state':'state-'+secrets.token_hex(8),'code_challenge':challenge,'code_challenge_method':'S256'}
        b=user['browser'];response=b.get(self.base+'/authorize',params=params)
        assert response.status_code in [302,303,307],response.text
        login=b.get(response.headers['location']);assert login.status_code==200,login.text
        approved=b.post(response.headers['location'],headers={'Origin':self.base},data={'csrf':csrf(login),'email':email,'password':password,'decision':'approve'})
        assert approved.status_code==303,approved.text
        query=parse_qs(urlparse(approved.headers['location']).query)
        assert query['state']==[params['state']]
        token=b.post(self.base+'/token',data={'grant_type':'authorization_code','client_id':'atmem-test-client','code':query['code'][0],'redirect_uri':params['redirect_uri'],'code_verifier':verifier,'resource':self.base+'/mcp'})
        assert token.status_code==200,token.text
        user.update(token.json());user['code']=query['code'][0];user['verifier']=verifier
        return user
    def approve(self,user,proposal,approve=True):
        browser=user['browser'];url=proposal['approval_url'];preview=browser.get(url)
        assert preview.status_code==200,preview.text
        response=browser.post(url,headers={'Origin':self.base},data={'csrf':csrf(preview),'decision':'approve' if approve else 'deny'})
        assert response.status_code==200,response.text
        return response
    def restart(self):
        self.process.terminate();self.process.wait(timeout=10)
        self.process=self.launch(self.config,self.env,self.root/'service.log')
        self.wait_ready()
    def wait_ready(self):
        for _ in range(100):
            if self.process.poll() is not None:raise AssertionError((self.root/'service.log').read_text())
            try:
                if httpx.get(self.base+'/health',timeout=1).status_code==200:return
            except httpx.HTTPError:pass
            time.sleep(.1)
        raise AssertionError('service did not start')
    @staticmethod
    def launch(config,env,log):
        handle=log.open('a')
        child_env=env.copy();cwd=ROOT
        if env.get('ATMEM_CHATGPT_INSTALLED_ROOT'):
            child_env['PYTHONPATH']=env['ATMEM_CHATGPT_INSTALLED_ROOT'];cwd=config.parent
            probe=subprocess.run([sys.executable,'-c','import atmem;print(atmem.__file__)'],cwd=cwd,env=child_env,capture_output=True,text=True,check=True)
            assert Path(probe.stdout.strip()).is_relative_to(Path(env['ATMEM_CHATGPT_INSTALLED_ROOT']))
            (config.parent.parent/'installed-server.json').write_text(json.dumps({'module':probe.stdout.strip(),'installed_artifact':True}))
        return subprocess.Popen([sys.executable,'-m','atmem.chatgpt','serve','--config',str(config)],cwd=cwd,env=child_env,stdout=handle,stderr=handle)


@pytest.fixture(scope='session')
def cloud(tmp_path_factory):
    if not os.environ.get('FIRESTORE_EMULATOR_HOST') or not os.environ.get('FIREBASE_AUTH_EMULATOR_HOST'):
        pytest.skip('requires real local Firebase Auth/Firestore emulators; see documented emulator command')
    root=tmp_path_factory.mktemp('chatgpt-cloud')
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    env=os.environ.copy()
    for name in ['ATMEM_HOME','ATMEM_DB_KEY','ATMEM_DB']:env.pop(name,None)
    subprocess.run([sys.executable,'-m','atmem.chatgpt','init-test','--directory',str(root/'runtime'),'--port',str(port)],cwd=ROOT,env=env,check=True,capture_output=True)
    config=root/'runtime/config.json'
    process=Harness.launch(config,env,root/'service.log')
    h=Harness(root,config,process,env,port);h.wait_ready()
    yield h
    h.process.terminate();h.process.wait(timeout=10)
    for u in h.users:u['browser'].close()
    # Explicit synthetic project only. Never run emulator cleanup on a real one.
    from atmem.chatgpt.config import Settings
    from atmem.chatgpt.repository import Repository
    settings=Settings.load(config);repository=Repository(settings)
    repository.client.recursive_delete(repository.root)
    removed=httpx.delete('http://'+env['FIREBASE_AUTH_EMULATOR_HOST']+'/emulator/v1/projects/demo-atmem-plugin/accounts')
    assert removed.status_code==200
    cleanup={'firestore_namespace_removed':not list(repository.root.limit(1).stream()),'synthetic_auth_accounts_removed':True}
    assert cleanup['firestore_namespace_removed']
    (root/'synthetic-cleanup.json').write_text(json.dumps(cleanup))
    if os.environ.get('ATMEM_CHATGPT_EVIDENCE_DIR'):
        import shutil
        output=Path(os.environ['ATMEM_CHATGPT_EVIDENCE_DIR']);output.mkdir(parents=True,exist_ok=True)
        for name in ['calls.jsonl','tool-inventory.json','synthetic-cleanup.json','browser-verification.json','consent-mobile.png','installed-server.json']:
            if (root/name).exists():shutil.copyfile(root/name,output/name)
    import shutil
    shutil.rmtree(config.parent)
