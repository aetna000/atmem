import asyncio,base64,hashlib,json,re,secrets,subprocess,tempfile,time
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

import argparse
parser=argparse.ArgumentParser(description='Explicit synthetic-only managed AtMem integration check; uses current gcloud operator credentials.')
parser.add_argument('--private-directory',type=Path,required=True)
parser.add_argument('--evidence',type=Path,required=True)
parser.add_argument('--allow-synthetic-writes',action='store_true',required=True)
options=parser.parse_args()
private=options.private_directory
config=json.loads((private/'config.json').read_text());base=config['issuer']
users=json.loads((private/'synthetic-accounts.json').read_text())
assert len(users)==2 and all(re.fullmatch(r'atmem-(reviewer|isolation)-[0-9a-f]{10}@example\.invalid',u['email']) for u in users)
assert (private/'synthetic-accounts.json').stat().st_mode & 0o077 == 0
client_id='atmem-independent-cloud-test';callback=config['clients'][client_id][0]
evidence={'surface':'managed Cloud Run HTTPS; independent MCP client, not ChatGPT','issuer':base,'tests':[],'synthetic_only':True}

def checked(name):evidence['tests'].append(name);print(name,'passed',flush=True)
def csrf(r):
 m=re.search(r'name="csrf" value="([^"]+)"',r.text);assert m,r.text[:200];return m[1]
def login(u,scope='memory:read memory:write memory:delete'):
 b=httpx.Client(follow_redirects=False,timeout=60);u['browser']=b
 proof=b.post('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword',params={'key':config['firebase_api_key']},json={'email':u['email'],'password':u['password'],'returnSecureToken':True})
 assert proof.status_code==200 and proof.json()['localId']==u['uid'], 'synthetic UID must match the authenticated Firebase account before any cleanup'

 verifier=secrets.token_urlsafe(48);challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
 params={'response_type':'code','client_id':client_id,'redirect_uri':callback,'scope':scope,'resource':base+'/mcp','state':'cloud-test-'+secrets.token_hex(5),'code_challenge':challenge,'code_challenge_method':'S256'}
 a=b.get(base+'/authorize',params=params);assert a.status_code in [302,303,307],(a.status_code,a.text[:200])
 form=b.get(a.headers['location']);assert form.status_code==200
 consent=b.post(a.headers['location'],headers={'Origin':base},data={'csrf':csrf(form),'email':u['email'],'password':u['password'],'decision':'approve'})
 assert consent.status_code==303,(consent.status_code,consent.text[:200])
 q=parse_qs(urlparse(consent.headers['location']).query);assert q['state']==[params['state']]
 t=b.post(base+'/token',data={'grant_type':'authorization_code','client_id':client_id,'code':q['code'][0],'redirect_uri':callback,'code_verifier':verifier,'resource':base+'/mcp'})
 assert t.status_code==200,(t.status_code,t.text[:200]);u.update(t.json());return u
async def invoke(u,name,args):
 async with httpx.AsyncClient(headers={'Authorization':'Bearer '+u['access_token']},timeout=60) as h:
  async with streamable_http_client(base+'/mcp',http_client=h) as (r,w,_):
   async with ClientSession(r,w) as s:
    await s.initialize();response=await s.call_tool(name,args);assert not response.isError;return response.structuredContent
def call(u,name,args={}):return asyncio.run(invoke(u,name,args))
def proposal(u,name,args):
 r=call(u,name,args);assert r['ok'],r;return r['data']
def approve(u,p,decision='approve'):
 b=u['browser'];preview=b.get(p['approval_url']);assert preview.status_code==200
 r=b.post(p['approval_url'],headers={'Origin':base},data={'csrf':csrf(preview),'decision':decision});assert r.status_code==200

a,b=users
try:
 r=httpx.post(base+'/mcp',json={'jsonrpc':'2.0','id':1,'method':'ping'},timeout=60);assert r.status_code==401;checked('unauthenticated MCP rejected')
 login(a);login(b);checked('Firebase sign-in and real HTTPS OAuth PKCE')
 scopes=call(a,'list_memory_scopes');assert scopes['ok'];checked('authenticated scopes')
 marker='cloud-check-'+secrets.token_hex(5);text='My test project codename is '+marker+'.'
 p=proposal(a,'propose_memory',{'scope':'personal','content':text,'idempotency_key':marker})
 denied=call(a,'commit_memory_action',{'scope':'personal','action_id':p['action_id'],'operation':'save'});assert not denied['ok'];checked('unapproved commit rejected')
 wrong=b['browser'].get(p['approval_url']);assert wrong.status_code==404;checked('other user cannot approve')
 approve(a,p)
 saved=call(a,'commit_memory_action',{'scope':'personal','action_id':p['action_id'],'operation':'save'});assert saved['ok'] and saved['data']['durable'];rid=saved['data']['record_ids'][0];checked('real durable save')
 replay=call(a,'commit_memory_action',{'scope':'personal','action_id':p['action_id'],'operation':'save'});assert replay['ok'] and replay['data']['record_ids']==[rid];checked('idempotent save retry')
 read=call(a,'read_memory',{'scope':'personal','record_id':rid});assert read['ok'] and marker in read['data']['record']['content'];checked('detail and provenance')
 recall=call(a,'search_memory',{'scope':'personal','query':'test project codename'});assert recall['ok'] and any(r['id']==rid for r in recall['data']['records']);checked('real recall')
 assert not call(b,'read_memory',{'scope':'personal','record_id':rid})['ok'];assert not call(b,'search_memory',{'scope':'personal','query':marker})['data']['records'];checked('cross-account isolation')
 # Independently open encrypted Firestore state with the real engine. Operator
 # credentials are obtained privately; neither tokens nor keys enter evidence.
 cfg=dict(config);cfg['home']=tempfile.mkdtemp(prefix='atmem-managed-inspect-');Path(cfg['home']).chmod(0o700);cfg.pop('key_env');cfg['key_file']=str(private/'master.key')
 cfgfile=Path(cfg['home'])/'config.json';cfgfile.write_text(json.dumps(cfg));cfgfile.chmod(0o600)
 from atmem.chatgpt.config import Settings
 settings=Settings.load(cfgfile)
 from atmem.chatgpt.repository import Repository
 from atmem.chatgpt.service import Service
 from google.cloud import firestore
 from google.oauth2.credentials import Credentials
 from cryptography.hazmat.primitives.ciphers.aead import AESGCM
 class OperatorRepository(Repository):
  def __init__(self):
   self.settings=settings
   access=subprocess.run(['gcloud','auth','print-access-token'],capture_output=True,text=True,check=True).stdout.strip()
   self.client=firestore.Client(project=settings.project,database=settings.database,credentials=Credentials(access))
   self.root=self.client.collection(settings.collection);self.cipher=AESGCM(settings.derive('firestore-envelope-v1'))
 repo=OperatorRepository();service=Service(settings,repo)
 payload=json.loads(repo.load(a['uid']).payload)
 assert payload['format']=='atmem-cloud-household-v1'
 path=Path(cfg['home'])/'inspect.db';path.write_bytes(base64.b64decode(payload['database']))
 Path(str(path)+'.encryption.json').write_text(json.dumps(payload['policy']))
 from atmem import Memory
 from atmem.core.storage import HouseholdPolicy
 memory=Memory(path,policy=HouseholdPolicy.load(path),auto_vectors=False)
 try:
  subject=service._subject(memory.store._conn,a['uid'],'personal')
  row=memory.store.get_record(subject,rid);assert row['content']==text
  assert memory.verify(subject)['valid']
 finally:memory.close()
 checked('independent persisted engine and audit verification')
 version=read['data']['record']['version']
 p=proposal(a,'propose_memory_correction',{'scope':'personal','record_id':rid,'version':version,'content':'My test project codename is corrected-'+marker+'.','idempotency_key':'correct-'+marker});approve(a,p)
 corrected=call(a,'commit_memory_action',{'scope':'personal','action_id':p['action_id'],'operation':'correct'});assert corrected['ok'];rid=corrected['data']['record_ids'][0];checked('real versioned correction')
 current=call(a,'read_memory',{'scope':'personal','record_id':rid});assert current['ok']
 p=proposal(a,'preview_memory_deletion',{'scope':'personal','record_id':rid,'version':current['data']['record']['version'],'idempotency_key':'delete-'+marker});approve(a,p)
 deleted=call(a,'commit_memory_action',{'scope':'personal','action_id':p['action_id'],'operation':'delete'});assert deleted['ok'] and deleted['data']['deleted'];assert deleted['data']['receipt']['format']=='atmem-exact-record-deletion-receipt-v1';checked('exact deletion receipt')
 assert call(a,'search_memory',{'scope':'personal','query':'corrected-'+marker})['data']['records']==[];checked('deleted memory absent')
 audit=call(a,'list_memory_activity',{'scope':'personal'});assert audit['ok'];checked('scoped audit activity')
 refreshed=a['browser'].post(base+'/token',data={'grant_type':'refresh_token','client_id':client_id,'refresh_token':a['refresh_token'],'scope':'memory:read memory:write memory:delete','resource':base+'/mcp'});assert refreshed.status_code==200;a.update(refreshed.json());checked('registered Firebase revalidation on refresh')
 # Revoke only this synthetic grant, then confirm the same access token fails.
 r=a['browser'].post(base+'/revoke',data={'client_id':client_id,'token':a['access_token'],'token_type_hint':'access_token'});assert r.status_code==200
 rejected=httpx.post(base+'/mcp',headers={'Authorization':'Bearer '+a['access_token']},json={'jsonrpc':'2.0','id':1,'method':'ping'},timeout=30);assert rejected.status_code==401;checked('grant revocation immediate')
 # Remove only the two synthetic households, including superseded revisions.
 for u in users:
  doc=repo._doc('household',u['uid']);repo.client.recursive_delete(doc)
  assert not doc.get().exists and not list(doc.collection('chunks').limit(1).stream())
  if u.get('access_token'):
   u['browser'].post(base+'/revoke',data={'client_id':client_id,'token':u['access_token'],'token_type_hint':'access_token'})
 checked('synthetic household cleanup')
 import shutil
 shutil.rmtree(cfg['home'])
 evidence['passed']=True
finally:
 for u in users:
  if u.get('browser'):u['browser'].close()
 options.evidence.write_text(json.dumps(evidence,indent=2))
