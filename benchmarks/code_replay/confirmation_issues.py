"""Fetch only immutable public problem statements for the original task pool."""
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha1, sha256
import json
from pathlib import Path

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.external_catalog import api
from benchmarks.code_replay.windows_execute import ROOT

RUN='external-confirmation-public-issues-v1-20261018'
PREFLIGHT=Path('/Volumes/MEM/AtMem-Code-Replay-20261017/cross-repository-confirmation-eligibility-v2')
TARGET=Path('/Volumes/MEM/AtMem-Code-Replay-20261017/confirmation-public-issues-v1')


def issue_blob(tree,response):
    entries=[r for r in tree['tree'] if r['path']=='problem_statement.md']
    if len(entries)!=1 or entries[0]['type']!='blob' or entries[0]['mode']!='100644':
        raise ValueError('exact public problem statement blob required')
    entry=entries[0]
    if (type(entry['size']) is not int or not 0<entry['size']<=262144
        or response.get('encoding')!='base64' or response.get('sha')!=entry['sha']):
        raise ValueError('bounded pinned public issue required')
    raw=base64.b64decode(''.join(response['content'].split()),validate=True)
    if len(raw)!=entry['size'] or sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=entry['sha']:
        raise ValueError('public issue Git blob identity differs')
    raw.decode('utf-8')
    return raw


def main():
    selection=json.loads((PREFLIGHT/'selection.json').read_bytes())
    if len(selection['selected'])!=40:raise ValueError('original forty candidates required')
    scope=EvidenceScope('benchmark','local-operator','click-20261017')
    principal=EvidencePrincipal('local-benchmark-operator',EvidenceRole.ADMINISTRATOR,scope)
    vault=ReplayEvidence(ROOT/'public-issues-v1/vault',vault_id='public-issues-v1',scope=scope)
    if vault.inspect(principal,RUN):raise ValueError('public issues already dispatched')
    TARGET.mkdir(mode=0o700,exist_ok=False)
    def save(kind,payload):return vault.capture(run_id=RUN,kind=kind,principal=principal,payload=payload)
    save('external.public_issues_planned',{'driver_source':Path(__file__).read_text(),
        'selection':selection,'allowed_content_path':'problem_statement.md','model_calls':0})
    def fetch(item):
        try:
            tree=api('git/trees/'+item['task_tree'])
            if tree.get('sha')!=item['task_tree'] or tree.get('truncated') is not False:
                raise ValueError('pinned complete task tree required')
            entries=[r for r in tree['tree'] if r['path']=='problem_statement.md']
            if len(entries)!=1:raise ValueError('single problem statement required')
            response=api('git/blobs/'+entries[0]['sha'])
            raw=issue_blob(tree,response)
            return {'instance_id':item['instance_id'],'qualified':True,'task_tree':item['task_tree'],
                'public_tree':tree,'public_blob':response,'bytes':len(raw),'sha256':sha256(raw).hexdigest(),
                'content_base64':base64.b64encode(raw).decode(),'model_calls':0}
        except Exception as exc:
            return {'instance_id':item['instance_id'],'qualified':False,'failure':type(exc).__name__+': '+str(exc)}
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch,item) for item in selection['selected']]):
            result=future.result();save('external.public_issue_result',result)
            payload=json.dumps(result,sort_keys=True).encode()
            with (TARGET/(result['instance_id']+'.json')).open('xb') as out:out.write(payload)
            row={'instance_id':result['instance_id'],'qualified':result['qualified'],
                 'bytes':len(payload),'sha256':sha256(payload).hexdigest()}
            results.append(row);print(json.dumps(row),flush=True)
    manifest={'results':results,'model_calls':0,'content_paths_fetched':['problem_statement.md']}
    with (TARGET/'manifest.json').open('x') as out:json.dump(manifest,out,sort_keys=True)
    save('external.public_issues_completed',manifest)


if __name__=='__main__':main()
