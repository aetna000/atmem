#!/usr/bin/env python3
"""Real managed CIMD/account-deletion check; creates only a new synthetic account."""
import argparse,asyncio,base64,hashlib,html,json,re,secrets,subprocess,tempfile,time,shutil
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

parser=argparse.ArgumentParser()
parser.add_argument('--private-directory',type=Path,required=True)
parser.add_argument('--evidence',type=Path,required=True)
parser.add_argument('--allow-synthetic-writes',action='store_true',required=True)
args=parser.parse_args();private=args.private_directory
config=json.loads((private/'config.json').read_text());base=config['issuer']
assert config['project']=='atmemai' and config['database']=='atmem-chatgpt'
state_path=private/'public-managed-account.json'
assert not state_path.exists(),'Preserve an interrupted account check for recovery; do not silently create another.'
evidence={'surface':'independent MCP client and real managed HTTPS, not ChatGPT invocation','synthetic_only':True,'checks':[]}
browser=httpx.Client(follow_redirects=False,timeout=60)
def checked(name):evidence['checks'].append(name);print(name,'passed',flush=True)
def csrf(r):
 match=re.search(r'name="csrf" value="([^"]+)"',r.text);assert match;return match[1]
async def invoke(name,arguments):
 async with httpx.AsyncClient(headers={'Authorization':'Bearer '+access},timeout=60) as client:
  async with streamable_http_client(base+'/mcp',http_client=client) as (r,w,_):
   async with ClientSession(r,w) as session:
    await session.initialize();result=await session.call_tool(name,arguments);assert not result.isError;return result.structuredContent
def call(name,arguments={}):return asyncio.run(invoke(name,arguments))
def approve(p):
 page=browser.get(p['approval_url']);assert page.status_code==200
 result=browser.post(p['approval_url'],headers={'Origin':base},data={'csrf':csrf(page),'decision':'approve'});assert result.status_code==200
try:
 health=browser.get(base+'/health');assert health.status_code==200
 metadata=browser.get(base+'/.well-known/oauth-authorization-server').json()
 assert metadata['client_id_metadata_document_supported'] and metadata['token_endpoint_auth_methods_supported']==['none'];checked('live public-client discovery')
 email='atmem-deletion-'+secrets.token_hex(10)+'@example.invalid';password=secrets.token_urlsafe(30)
 created=browser.post('https://identitytoolkit.googleapis.com/v1/accounts:signUp',params={'key':config['firebase_api_key']},json={'email':email,'password':password,'returnSecureToken':True});assert created.status_code==200
 uid=created.json()['localId'];state={'uid':uid,'email':email,'password':password,'synthetic_created_for':'public-managed-deletion'}
 state_path.write_text(json.dumps(state));state_path.chmod(0o600)
 owner=subprocess.run(['gcloud','auth','print-access-token'],capture_output=True,text=True,check=True).stdout.strip()
 verified=browser.post('https://identitytoolkit.googleapis.com/v1/projects/atmemai/accounts:update',headers={'Authorization':'Bearer '+owner,'x-goog-user-project':'atmemai'},json={'localId':uid,'emailVerified':True});assert verified.status_code==200
 checked('isolated synthetic Firebase identity created; admin verification is not mailbox evidence')
 client_id='https://chatgpt.com/oauth/client.json';document=browser.get(client_id).json();callback=document['redirect_uris'][0]
 verifier=secrets.token_urlsafe(48);challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
 response=browser.get(base+'/authorize',params={'response_type':'code','client_id':client_id,'redirect_uri':callback,'resource':base+'/mcp','scope':'memory:read memory:write memory:delete','state':'public-managed','code_challenge':challenge,'code_challenge_method':'S256'})
 assert response.status_code in [302,303,307],(response.status_code,response.text[:200])
 form=browser.get(response.headers['location']);consent=browser.post(response.headers['location'],headers={'Origin':base},data={'csrf':csrf(form),'email':email,'password':password,'decision':'approve'});assert consent.status_code==303
 query=parse_qs(urlparse(consent.headers['location']).query);assert query['state']==['public-managed'] and query['iss']==[metadata['issuer']]
 token=browser.post(base+'/token',data={'grant_type':'authorization_code','client_id':client_id,'redirect_uri':callback,'resource':base+'/mcp','code':query['code'][0],'code_verifier':verifier});assert token.status_code==200
 access=token.json()['access_token'];checked('official CIMD authorization, issuer and PKCE exchange')
 marker='public-'+secrets.token_hex(8)
 proposal=call('propose_memory',{'scope':'personal','content':'My synthetic project codename is '+marker+'.','idempotency_key':marker});assert proposal['ok'];approve(proposal['data'])
 saved=call('commit_memory_action',{'scope':'personal','action_id':proposal['data']['action_id'],'operation':'save'});assert saved['ok'] and saved['data']['durable'];rid=saved['data']['record_ids'][0];checked('real governed memory created before deletion')
 # Account-bound encrypted recovery with actual native engine verification.
 cfg=dict(config);cfg['home']=tempfile.mkdtemp(prefix='atmem-public-inspect-');Path(cfg['home']).chmod(0o700);cfg.pop('key_env');cfg['key_file']=str(private/'master.key')
 path=Path(cfg['home'])/'config.json';path.write_text(json.dumps(cfg));path.chmod(0o600)
 from atmem.chatgpt.config import Settings
 settings=Settings.load(path)
 from atmem.chatgpt.repository import Repository,AccountClosed
 from google.cloud import firestore
 from google.oauth2.credentials import Credentials
 from cryptography.hazmat.primitives.ciphers.aead import AESGCM
 class OperatorRepository(Repository):
  def __init__(self):
   self.settings=settings;self.client=firestore.Client(project=settings.project,database=settings.database,credentials=Credentials(owner));self.root=self.client.collection(settings.collection);self.cipher=AESGCM(settings.derive('firestore-envelope-v1'))
 repo=OperatorRepository();backup=repo.export_snapshot(uid);before=repo.load(uid)
 assert marker.encode() not in backup
 restored=repo.restore_snapshot(uid,backup,expected_generation=before.generation);assert restored['generation']==before.generation+1
 read=call('read_memory',{'scope':'personal','record_id':rid});assert read['ok'] and marker in read['data']['record']['content'];checked('managed encrypted recovery and native audit roundtrip')
 # Separate fresh password and explicit whole-account confirmation.
 page=browser.get(base+'/account/delete');assert 'No data is deleted at this step' in page.text
 preview=browser.post(base+'/account/delete',headers={'Origin':base},data={'csrf':csrf(page),'decision':'preview','email':email,'password':password});assert preview.status_code==303
 page=browser.get(base+'/account/delete');assert email in page.text and 'every personal and project memory' in page.text
 # Keep only a private recovery cookie if the check is interrupted.
 state['deletion_cookie']=browser.cookies.get('atmem_human');state_path.write_text(json.dumps(state));state_path.chmod(0o600)
 result=browser.post(base+'/account/delete',headers={'Origin':base},data={'csrf':csrf(page),'decision':'delete','understood':'yes'});assert result.status_code==200,result.text[:200]
 receipt=json.loads(html.unescape(re.search(r'<pre>(.*?)</pre>',result.text,re.S)[1]))
 assert receipt['access_revoked'] and receipt['household_purged'] and receipt['firebase_account_deleted'];assert not receipt['backup_deletion_verified'];checked('fresh-confirmed whole-account purge and Firebase deletion receipt')
 denied=browser.post(base+'/mcp',headers={'Authorization':'Bearer '+access},json={'jsonrpc':'2.0','id':1,'method':'ping'});assert denied.status_code==401;checked('all-account fence denies prior access token')
 head=repo._doc('household',uid);assert not head.get().exists and not list(head.collection('chunks').stream())
 try:repo.restore_snapshot(uid,backup,expected_generation=0)
 except AccountClosed:pass
 else:raise AssertionError('deleted account could be restored')
 checked('no household chunks remain and deleted account cannot be restored')
 lookup=browser.post('https://identitytoolkit.googleapis.com/v1/projects/atmemai/accounts:lookup',headers={'Authorization':'Bearer '+owner,'x-goog-user-project':'atmemai'},json={'localId':[uid]});assert lookup.status_code==200 and not lookup.json().get('users');checked('Firebase account absence independently verified')
 assert 'Account deletion receipt' in browser.get(base+'/account/delete').text;checked('browser receipt recovery')
 evidence['receipt']=receipt;evidence['passed']=True
 state_path.unlink();shutil.rmtree(cfg['home'])
finally:
 browser.close();args.evidence.write_text(json.dumps(evidence,indent=2))
assert evidence.get('passed'), 'Managed check incomplete; preserve its private recovery state.'
