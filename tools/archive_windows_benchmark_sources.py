"""Archive and verify old owned source workspaces before explicit removal.

Encrypted benchmark artifacts only go to MEM; recovery keys remain on the Mac.
Does not delete results, databases, runtimes, images or arbitrary directories.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from benchmarks.code_replay.swebench_pilot import remote, SOCKET

ROOT = '/home/user/atmem-swebench-20261019'
INSPECT = '''import os,re,json,hashlib,subprocess,stat
from pathlib import Path
root=Path('/home/user/atmem-swebench-20261019/sources')
def idle():
 if subprocess.check_output(['docker','ps','-q']).strip():raise RuntimeError('Docker executor is active')
def fingerprint(path):
 h=hashlib.sha256();size=0;count=0
 for parent,dirs,files in os.walk(path,followlinks=False):
  dirs.sort()
  for name in sorted(dirs+files):
   p=Path(parent)/name;s=p.lstat()
   h.update(json.dumps([str(p.relative_to(path)),s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns],separators=(',',':')).encode())
   size+=s.st_size if stat.S_ISREG(s.st_mode) else 0;count+=1
 return {'fingerprint':h.hexdigest(),'file_bytes':size,'entries':count}
idle()
'''


def call(program, payload=None, timeout=60):
    result = remote(program, payload, timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--resume-archive', action='store_true', help='resume retained pre-deletion archive preparation')
    args = parser.parse_args()
    scan = INSPECT + '''
paths=sorted(root.iterdir())
if any(p.is_symlink() or not p.is_dir() or not re.fullmatch('atmem-swe-lite-[a-f0-9]{32}',p.name) for p in paths):raise RuntimeError('unexpected source child; stop')
print(json.dumps({p.name:fingerprint(p) for p in paths}))
'''
    destination = Path('/Volumes/MEM/AtMem-SWEbench-Threeway-20261019/windows-source-workspaces')
    receipt_path = destination / 'manifest.json'
    prior = json.loads(receipt_path.read_text()) if args.resume_archive else None
    if prior and (prior['state'] != 'preparing' or prior['source_root'] != ROOT + '/sources'):
        raise ValueError('resume is only valid before transfer/deletion')
    manifest = prior['inventory'] if prior else call(scan, timeout=300)
    if not args.apply:
        print(json.dumps({'apply': False, 'directories': len(manifest),
                          'file_bytes': sum(x['file_bytes'] for x in manifest.values())}))
        return
    if not manifest or not Path('/Volumes/MEM').is_mount():
        raise RuntimeError('source inventory or archive disk unavailable')
    if not prior:
        destination.mkdir(mode=0o700, exist_ok=False)
    keydir = Path('/Users/javadtaghia/Library/Application Support/AtMem Benchmarks/windows-source-workspace-recovery-20261019')
    keyfile = keydir / 'key.json'
    if prior:
        if keyfile.is_symlink() or keyfile.stat().st_mode & 0o077:
            raise ValueError('private recovery key permissions required')
        saved = json.loads(keyfile.read_text())
        key, nonce = bytes.fromhex(saved['key_hex']), bytes.fromhex(saved['nonce_hex'])
    else:
        keydir.mkdir(mode=0o700, exist_ok=False)
        key, nonce = os.urandom(32), os.urandom(12)
        with os.fdopen(os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as out:
            json.dump({'key_hex': key.hex(), 'nonce_hex': nonce.hex()}, out)
    receipt = {'format': 'atmem-benchmark-scratch-archive-v1', 'cipher': 'AES-256-GCM',
               'source_root': ROOT + '/sources', 'inventory': manifest, 'results_deleted': False,
               'key_file': str(keyfile), 'state': 'preparing'}
    receipt_path.write_text(json.dumps(receipt, indent=2))
    archive = ROOT + '/old-source-workspaces-20261019.tar.gz'
    if prior:
        made = call(INSPECT + '''
import time
archive=Path('/home/user/atmem-swebench-20261019/old-source-workspaces-20261019.tar.gz')
def active():
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:args=(p/'cmdline').read_bytes().split(b'\\0')
  except (OSError,ProcessLookupError):continue
  if args and args[0].split(b'/')[-1]==b'tar' and str(archive).encode() in args:return True
 return False
deadline=time.monotonic()+360
while active():
 if time.monotonic()>deadline:raise TimeoutError('retained archive still being prepared; originals untouched')
 time.sleep(1)
if not archive.is_file():raise RuntimeError('retained archive missing; originals untouched')
subprocess.run(['gzip','-t',str(archive)],check=True,timeout=180)
h=hashlib.sha256()
with archive.open('rb') as f:
 for block in iter(lambda:f.read(1048576),b''):h.update(block)
print(json.dumps({'sha256':h.hexdigest(),'bytes':archive.stat().st_size,'resumed_complete_gzip_verified':True}))
''', timeout=660)
    else:
        made = call(INSPECT + '''
names=sorted(job['payload'])
if {p.name:fingerprint(p) for p in root.iterdir()}!=job['payload']:raise RuntimeError('source state changed')
archive=Path('/home/user/atmem-swebench-20261019/old-source-workspaces-20261019.tar.gz')
if archive.exists():raise RuntimeError('archive already exists; do not overwrite')
subprocess.run(['tar','-czf',str(archive),'-C',str(root),'--',*names],check=True,timeout=300)
h=hashlib.sha256()
with archive.open('rb') as f:
 for block in iter(lambda:f.read(1048576),b''):h.update(block)
print(json.dumps({'sha256':h.hexdigest(),'bytes':archive.stat().st_size}))
''', manifest, timeout=900)
    encrypted = destination / 'sources.tar.gz.aesgcm'
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(b'atmem-benchmark-scratch-archive-v1')
    process = subprocess.Popen(['ssh', '-S', SOCKET, '-o', 'BatchMode=yes', '-T',
        'user@192.168.0.87', 'wsl -d Ubuntu -u root -- cat ' + archive],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest, count = sha256(), 0
    with encrypted.open('xb') as out:
        for block in iter(lambda: process.stdout.read(1048576), b''):
            count += len(block); digest.update(block); out.write(encryptor.update(block))
        out.write(encryptor.finalize()); out.flush(); os.fsync(out.fileno())
    stderr = process.stderr.read(); code = process.wait(timeout=15)
    if code or count != made['bytes'] or digest.hexdigest() != made['sha256']:
        raise RuntimeError('transfer verification failed; originals untouched: ' + stderr.decode(errors='replace')[-500:])
    decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, encryptor.tag)).decryptor()
    decryptor.authenticate_additional_data(b'atmem-benchmark-scratch-archive-v1')
    verified = sha256()
    with encrypted.open('rb') as inp:
        for block in iter(lambda: inp.read(1048576), b''):
            verified.update(decryptor.update(block))
    verified.update(decryptor.finalize())
    if verified.hexdigest() != made['sha256']:
        raise RuntimeError('independent decryption failed; originals untouched')
    receipt.update(state='archive_verified_before_deletion', archive=str(encrypted),
                   tag_hex=encryptor.tag.hex(), plaintext_archive=made)
    receipt_path.write_text(json.dumps(receipt, indent=2))
    print(json.dumps({'state': receipt['state'], 'bytes': count, 'directories': len(manifest)}), flush=True)
    removed = call(INSPECT + '''
import shutil
if {p.name:fingerprint(p) for p in root.iterdir()}!=job['payload']:raise RuntimeError('source state changed; originals retained')
removed=[]
for name in sorted(job['payload']):
 idle();p=root/name
 if p.parent!=root or p.is_symlink() or not re.fullmatch('atmem-swe-lite-[a-f0-9]{32}',name):raise RuntimeError('unsafe deletion target')
 shutil.rmtree(p);removed.append(name)
Path('/home/user/atmem-swebench-20261019/old-source-workspaces-20261019.tar.gz').unlink()
print(json.dumps({'removed':removed,'remaining':sorted(p.name for p in root.iterdir())}))
''', manifest, timeout=600)
    receipt.update(state='completed', removal=removed)
    receipt_path.write_text(json.dumps(receipt, indent=2))
    print(json.dumps({'state': 'completed', 'removed_directories': len(removed['removed']),
                      'archived_file_bytes': sum(x['file_bytes'] for x in manifest.values()),
                      'recoverable_archive': str(encrypted), 'results_deleted': False}))


if __name__ == '__main__':
    main()
