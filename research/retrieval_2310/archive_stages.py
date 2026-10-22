"""Private terminal-stage backup; credentials/host homes excluded, no deletion."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import uuid

from benchmarks.dolphinbench.gateway import save_new
from .archive import env_values


def add_verified_snapshot(archive,path,*,name,expected,diagnostics):
    """Verify and archive the same bytes, not a second unbound file read."""
    data=path.read_bytes()
    observed={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    if observed!=expected:
        save_new(diagnostics/'source-drift.json',{'path':str(path),'archive_name':name,
            'expected':expected,'observed':observed,'original_file_modified':False})
        raise ValueError('terminal evidence changed during backup: '+name)
    info=archive.gettarinfo(str(path),arcname=name)
    info.size=len(data)
    archive.addfile(info,io.BytesIO(data))


def screen_nested_archive(path,secrets):
    with tarfile.open(path,mode='r|gz') as archive:
        for member in archive:
            if (member.name.startswith('/') or '..' in Path(member.name).parts
                    or not (member.isfile() or member.isdir())):
                raise ValueError('unsafe nested source archive')
            if member.isfile():
                data=archive.extractfile(member).read()
                if any(secret in data for secret in secrets):
                    raise ValueError('nested source secret screen failed')


def collect(roots):
    files={}
    for root in roots:
        root=root.resolve()
        if not any(root.is_relative_to(p) for p in
                   (Path('/Volumes/AtMemDolphin'),Path('/Volumes/AtMemBenchRuntime'))):
            raise ValueError('only dedicated private benchmark volumes may be archived')
        if not root.name.startswith('retrieval-2310-'):raise ValueError('unrelated archive root')
        if not any((root/n).is_file() for n in ('result.json','failure.json','costs.json')):
            raise ValueError('only terminal stages may be archived')
        for path in root.rglob('*'):
            if not path.is_file() or path.is_symlink():continue
            relative=path.relative_to(root)
            if any(part.startswith('.') or part in {'host','keys','credentials'} for part in relative.parts):continue
            if any(word in path.name.casefold() for word in ('credential','auth.json','listener')):continue
            if path.suffix not in {'.json','.jsonl','.returned','.inflight'} and path.name!='budget.db':continue
            files[root.name+'/'+relative.as_posix()]=path
    return files


def protocol_supplements(paths,*,campaign):
    """Explicit, terminal operator artifacts; never follow a host-home link."""
    files={}
    for path in paths:
        path=Path(path)
        if (path.is_symlink() or path.resolve().parent!=campaign.resolve()
                or not path.is_file() or path.name.startswith('.')
                or path.suffix not in {'.py','.log','.txt','.pstats'}
                or any(word in path.name.casefold() for word in ('credential','auth.json','listener'))):
            raise ValueError('explicit private protocol source/terminal log required')
        name='frozen-protocol/'+path.name
        if name in files:raise ValueError('duplicate protocol supplement')
        files[name]=path
    return files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('roots',type=Path,nargs='+');parser.add_argument('--env-file',type=Path,required=True)
    parser.add_argument('--supplements',type=Path,nargs='*',default=[])
    args=parser.parse_args()
    from huggingface_hub import HfApi,CommitOperationAdd,hf_hub_url
    import requests
    values=env_values(args.env_file);token=values['HF_TOKEN']
    secrets=[v.encode() for k,v in values.items() if len(v)>=16 and (re.search('KEY|TOKEN|PASSWORD|SECRET',k) or k=='OPEN_ROUTER')]
    files=collect(args.roots)
    campaign=Path('/Volumes/MEM/atmem-retrieval-2310/dolphin-working-60-v1')
    files.update(protocol_supplements(args.supplements,campaign=campaign))
    for path in campaign.glob('*'):
        if path.is_file() and not path.name.startswith('.') and not path.is_symlink() and path.suffix in {'.json','.gz'}:
            files['frozen-protocol/'+path.name]=path
    records={}
    for name,path in files.items():
        data=path.read_bytes()
        if any(secret in data for secret in secrets):raise ValueError('secret screen failed; no upload')
        if path.suffix=='.gz':
            # Screen in stream order: repeated seek/extract on gzip can
            # decompress the same large source archive many times.
            screen_nested_archive(path,secrets)
        records[name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    identifier=uuid.uuid4().hex
    directory=Path('/Volumes/MEM/atmem-retrieval-2310/archives')/identifier
    save_new(directory/'manifest.json',{'format':'private-dolphin-stage-backup-v1','files':records,
        'terminal_roots':list(map(str,args.roots)),'interrupted_stages_are_not_completed_results':True,
        'host_keys_and_credentials_excluded':True,'local_deletion':False,'ready_for_600':False})
    destination=directory/'evidence.tar.gz'
    with tarfile.open(destination,'w:gz') as archive:
        for name,path in files.items():
            add_verified_snapshot(archive,path,name=name,expected=records[name],diagnostics=directory)
        archive.add(directory/'manifest.json',arcname='manifest.json',recursive=False)
    expected=hashlib.sha256(destination.read_bytes()).hexdigest()
    dataset='atmem/dolphinbench-evidence-20261020';remote=f'retrieval-2310/stages/{identifier}/evidence.tar.gz'
    api=HfApi(token=token)
    if not api.repo_info(dataset,repo_type='dataset').private:raise ValueError('private archive required')
    commit=api.create_commit(repo_id=dataset,repo_type='dataset',commit_message='Preserve terminal retrieval workflow stages and all failures privately',operations=[CommitOperationAdd(path_in_repo=remote,path_or_fileobj=str(destination))])
    checksum=hashlib.sha256();count=0
    with requests.get(hf_hub_url(dataset,remote,repo_type='dataset',revision=commit.oid),headers={'Authorization':'Bearer '+token},stream=True,timeout=120) as response:
        response.raise_for_status()
        for chunk in response.iter_content(1024*1024):checksum.update(chunk);count+=len(chunk)
    if checksum.hexdigest()!=expected or count!=destination.stat().st_size:raise ValueError('remote verification failed; all local evidence retained')
    receipt={'verified':True,'dataset':dataset,'private':True,'revision':commit.oid,
             'path':remote,'bytes':count,'sha256':expected,'files':len(records),'local_deletion':False}
    save_new(directory/'verified.json',receipt);print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
