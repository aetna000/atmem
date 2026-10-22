"""Allowlisted private evidence backup with streamed remote hash verification.

Never includes host homes, encrypted-store keys, credentials or arbitrary roots.
No local evidence is deleted. The repository must already exist and be private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tarfile
import uuid

from benchmarks.dolphinbench.gateway import save_new


def collect(research: Path, reader: Path, graders: list[Path], repo: Path) -> dict[str, Path]:
    if research.resolve() != Path('/Volumes/MEM/atmem-retrieval-2310'):
        raise ValueError('explicit campaign evidence root required')
    selected = {}
    for label, root in [('reader', reader), *[(f'grader-{i}', p) for i,p in enumerate(graders)]]:
        root.resolve().relative_to(Path('/Volumes/AtMemDolphin'))
        if not root.name.startswith('retrieval-2310-'):
            raise ValueError('unrelated campaign root')
        for path in root.rglob('*.json'):
            relative = path.relative_to(root)
            if path.is_symlink() or any(part.startswith('.') or part in {'host','keys','credentials'} for part in relative.parts):
                continue
            selected[label+'/'+relative.as_posix()] = path
    for path in (research/'qualification').glob('*.json'):
        if not path.name.startswith('.') and not path.is_symlink():
            selected['qualification/'+path.name] = path
    for run in (research/'diagnostics').iterdir():
        if not run.is_dir() or run.is_symlink() or run.name.startswith('.'):
            continue
        for path in run.glob('*.json'):
            if not path.name.startswith('.') and not path.is_symlink():
                selected['diagnostics/'+run.name+'/'+path.name] = path
        overlay = run/'source-overlay.tar.gz'
        if overlay.is_file() and not overlay.is_symlink():
            # Archives created by our diagnostic contain only source subtrees;
            # inspect each member rather than trusting a compressed outer file.
            with tarfile.open(overlay) as archive:
                if any(not (member.isfile() or member.isdir()) or
                       member.name.startswith('/') or '..' in Path(member.name).parts or
                       any(part in {'host','keys','.env'} for part in Path(member.name).parts)
                       for member in archive.getmembers()):
                    raise ValueError('unsafe source overlay')
            selected['diagnostics/'+run.name+'/source-overlay.tar.gz'] = overlay
    # Preserve only the already-egressed inspected source, its original license
    # and README. Other conversations and raw spreadsheet exports are excluded.
    original = research/'corpora/realtalk/48b3ab884a34baf659243d3188df478dd401a70a'
    for relative in ('data/Chat_1_Emi_Elise.json', 'LICENSE', 'README.md'):
        selected['source/realtalk/'+relative] = original/relative
    for prefix in ('research/retrieval_2310', 'specs/046-retrieval-performance-2310'):
        for path in (repo/prefix).iterdir():
            if path.is_file() and not path.is_symlink() and path.suffix in {'.py','.md','.json'}:
                selected['implementation/'+path.relative_to(repo).as_posix()] = path
    for relative in ('atmem/context_engine/semantic.py','atmem/context_engine/hybrid.py',
                     'atmem/context_engine/service.py','atmem/memory.py','atmem/semantic/providers.py',
                     'atmem/adapters/hermes/v3.py','benchmarks/dolphinbench/subscription_service.py',
                     'tests/test_context_engine_semantic.py','tests/test_hermes_v3.py'):
        selected['implementation/'+relative] = repo/relative
    for path in (repo/'tests/research').glob('*.py'):
        selected['implementation/'+path.relative_to(repo).as_posix()] = path
    for path in (reader/'reader-complete.json', graders[-1]/'comparison.json', graders[-1]/'costs.json'):
        if not path.is_file():
            raise ValueError('cannot archive an unfinished comparison as complete')
    for path in selected.values():
        if not path.is_file() or path.is_symlink():
            raise ValueError('missing or symlinked evidence')
    return selected


def env_values(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        match = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$', line)
        if match:
            value = match[2]
            if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[match[1]] = value
    return values


def archive(research: Path, reader: Path, graders: list[Path], env_file: Path) -> None:
    from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_url
    import requests
    repo = Path(__file__).resolve().parents[2]
    selected = collect(research,reader,graders,repo)
    values = env_values(env_file)
    token = values['HF_TOKEN']
    secrets = [value.encode() for key,value in values.items() if len(value) >= 16 and
               (re.search('KEY|TOKEN|PASSWORD|SECRET',key) or key == 'OPEN_ROUTER')]
    records = {}
    for name,path in sorted(selected.items()):
        data = path.read_bytes()
        if any(secret in data for secret in secrets):
            raise ValueError('secret screen failed; no upload')
        if path.suffix == '.gz':
            with tarfile.open(path) as nested:
                for member in nested.getmembers():
                    if member.isfile() and any(secret in nested.extractfile(member).read() for secret in secrets):
                        raise ValueError('source overlay secret screen failed')
        records[name] = {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    identifier = uuid.uuid4().hex
    directory = research/'archives'/identifier
    directory.mkdir(parents=True)
    ledger = sqlite3.connect('file:/Volumes/AtMemDolphin/retrieval-2310-budget.db?mode=ro',uri=True)
    try:
        accounting = {'entries':ledger.execute('SELECT id,state,amount FROM entries ORDER BY id').fetchall(),
                      'grading_children':ledger.execute('SELECT name,state,amount FROM grading_children ORDER BY name').fetchall(),
                      'unit':'micro USD; child allocations are contained within confidence-and-judging, not additive'}
    finally:
        ledger.close()
    save_new(directory/'accounting.json',accounting)
    save_new(directory/'manifest.json', {'format':'atmem-retrieval-evidence-archive-v1',
        'files':records,'original_host_keys_excluded':True,'local_deletion':False,
        'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        'source_license':'REALTALK original Apache-2.0 license included; private research backup',
        'ready_for_600':False})
    destination = directory/'evidence.tar.gz'
    with tarfile.open(destination,'w:gz') as output:
        for name,path in sorted(selected.items()):
            # Check again before packing: no mutable file may silently differ
            # from the checksummed manifest prepared above.
            if hashlib.sha256(path.read_bytes()).hexdigest() != records[name]['sha256']:
                raise ValueError('evidence changed while archiving')
            output.add(path,arcname=name,recursive=False)
        output.add(directory/'manifest.json',arcname='manifest.json',recursive=False)
        output.add(directory/'accounting.json',arcname='accounting.json',recursive=False)
    expected = hashlib.sha256(destination.read_bytes()).hexdigest()
    remote = f'retrieval-2310/{identifier}/evidence.tar.gz'
    dataset = 'atmem/dolphinbench-evidence-20261020'
    api = HfApi(token=token)
    if not api.repo_info(dataset,repo_type='dataset').private:
        raise ValueError('recovery dataset must remain private')
    commit = api.create_commit(repo_id=dataset,repo_type='dataset',
        commit_message='Preserve 2.3.10 retrieval development comparison and all grading controls',
        operations=[CommitOperationAdd(path_in_repo=remote,path_or_fileobj=str(destination))])
    digest,count = hashlib.sha256(),0
    url = hf_hub_url(dataset,remote,repo_type='dataset',revision=commit.oid)
    with requests.get(url,headers={'Authorization':'Bearer '+token},stream=True,timeout=120) as response:
        response.raise_for_status()
        for chunk in response.iter_content(1024*1024):
            digest.update(chunk)
            count += len(chunk)
    if digest.hexdigest() != expected or count != destination.stat().st_size:
        raise ValueError('remote round-trip verification failed; local evidence retained')
    receipt = {'verified':True,'dataset':dataset,'private':True,'revision':commit.oid,
               'path':remote,'sha256':expected,'bytes':count,'files':len(records),'local_deletion':False}
    save_new(directory/'verified.json',receipt)
    print(json.dumps(receipt),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('research',type=Path)
    parser.add_argument('reader',type=Path)
    parser.add_argument('graders',type=Path,nargs='+')
    parser.add_argument('--env-file',type=Path,required=True)
    args=parser.parse_args()
    archive(args.research,args.reader,args.graders,args.env_file)


if __name__=='__main__':
    main()
