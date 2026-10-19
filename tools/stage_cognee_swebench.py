"""Stage only public, snapshot-verified extraction inputs for a Cognee probe.

No solver/reference patches, hidden tests, database, keys or owner files leave
Windows. The common-source comparison uses Cognee's documented snapshot API.
"""
import argparse
import base64
from hashlib import sha256
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile

from benchmarks.code_replay.swebench_pilot import remote, REMOTE

PROGRAM = '''import sys,os,pathlib,json,base64,hashlib,io,tarfile
root=pathlib.Path('/home/user/atmem-swebench-20261019')
cache=root/'large-repo-fix/sympy-cached'
source=root/'sources/atmem-swe-lite-2b2d648c3e2649fd89b983a2fc5c9b5a'
os.environ['ATMEM_HOME']=str(cache/'home')
from atmem.memory import Memory
from atmem.code.identity import CodeIdentity
from atmem.code.application import CodeApplication
from atmem.knowledge.projections import CodeKnowledge
from atmem.knowledge.contracts import stable_digest
from atmem.knowledge.code.source_policy import SOURCE_POLICY
m=Memory(cache/'memory.db',auto_vectors=False)
scope=CodeIdentity(m.store).resolve(source,subject_id='index-qualification',profile_id='shared',agent_id='qualification')
knowledge=CodeKnowledge(CodeApplication(m,subject_id=scope.subject_id),scope)
manifest=m.store.code_document(scope.subject_id,scope.project_id,'qualification-artifact','manifest')
config=stable_digest({'worker_image':manifest['image_id'],'source_policy':SOURCE_POLICY})
snapshot,files,exclusions=knowledge.capture(str(source),config,max_source_bytes=24000000,omit_oversized_files=True,omit_invalid_text=True)
assert snapshot.snapshot_id==manifest['snapshot_id']
parts={}
for name,item in manifest['artifacts'].items():
 raw=b''.join(base64.b64decode(m.store.code_document(scope.subject_id,scope.project_id,'qualification-artifact',key)['payload_base64'],validate=True) for key in item['chunks'])
 assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
 parts[name]=raw
metadata={'format':'shared-enola-snapshot-qualification-v1','source_snapshot':snapshot.to_dict(),'worker_image_id':manifest['image_id'],'excluded_counts':exclusions,'artifacts':{name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in parts.items()}}
output=io.BytesIO()
with tarfile.open(fileobj=output,mode='w:gz') as archive:
 entries={**{'source/'+name:raw for name,raw in files.items()},'artifacts/facts.jsonl':parts['facts'],'artifacts/receipt.json':parts['receipt'],'artifacts/insights.json':parts['insights'],'metadata.json':json.dumps(metadata).encode()}
 for name,raw in entries.items():
  member=tarfile.TarInfo(name);member.size=len(raw);member.mode=384;archive.addfile(member,io.BytesIO(raw))
m.close()
raw=output.getvalue()
print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'payload_base64':base64.b64encode(raw).decode()}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    if args.destination.exists() or args.destination.is_symlink():
        raise ValueError('fresh public benchmark staging directory required')
    if shutil.disk_usage(args.destination.parent).free < 3 * 1024 ** 3:
        raise ValueError('Mac preparation reserve below 3 GiB')
    # Run in the existing pinned AtMem environment; returned bytes are public
    # source/artifacts only and never printed to the console.
    program = "import subprocess;r=subprocess.run([" + repr(REMOTE + '/candidate-large-repo-20261019/venv/bin/python') + ",'-I','-c',job['payload']],capture_output=True,text=True,timeout=90);print(r.stdout);raise SystemExit(r.returncode)"
    response = remote(program, PROGRAM, timeout=120)
    if response.returncode:
        raise RuntimeError('public snapshot staging failed')
    bundle = json.loads(response.stdout)
    raw = base64.b64decode(bundle['payload_base64'], validate=True)
    if len(raw) > 32_000_000 or sha256(raw).hexdigest() != bundle['sha256']:
        raise ValueError('public snapshot archive bound/integrity failed')
    args.destination.mkdir(mode=0o700)
    expanded = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        seen = set()
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            expanded += member.size
            if (not member.isfile() or member.size > 32_000_000 or expanded > 64_000_000
                    or path.is_absolute() or '..' in path.parts or str(path) != member.name
                    or member.name in seen or path.parts[0] not in {'source', 'artifacts', 'metadata.json'}):
                raise ValueError('unsafe public snapshot member')
            seen.add(member.name)
            target = args.destination / member.name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
    print(json.dumps({'destination': str(args.destination), 'archive_sha256': bundle['sha256'],
                      'expanded_bytes': expanded, 'source': 'public snapshot, no evaluation answers'}), flush=True)


if __name__ == '__main__':
    main()
