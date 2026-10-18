"""Bounded consistent COPY of stopped benchmark evidence; originals stay intact."""
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile

from atmem.evidence import EvidenceScope, EvidencePrincipal, EvidenceRole
from benchmarks.code_replay.atmem_bridge import ReplayEvidence
from benchmarks.code_replay.windows_execute import ROOT
from benchmarks.code_replay.windows_transport import framed_command, framed_input


DESTINATION = "/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1"
SQL_PROGRAM = r'''
import hashlib,json,os,shutil,sqlite3,sys,time
from pathlib import Path
base=Path('/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1')
if base.parent.is_symlink() or base.parent.resolve()!=base.parent:
 raise ValueError('exact existing benchmark runtime parent required')
if min(shutil.disk_usage('/tmp').free,shutil.disk_usage('/mnt/c').free)<8*1024**3:
 raise ValueError('Windows physical/WSL disk guard')
base.mkdir(mode=0o700,exist_ok=False)
target=base/'confirmation-v1'/'vault';target.mkdir(mode=0o700,parents=True,exist_ok=False)
connection=sqlite3.connect(target/'protected-evidence.db')
connection.execute('PRAGMA cache_size=-8192')
digest=hashlib.sha256();size=0;pending='';started=time.monotonic();statements=0
while True:
 raw=sys.stdin.buffer.readline(40000001)
 if not raw:break
 size+=len(raw);digest.update(raw)
 if len(raw)>40000000 or size>4000000000 or time.monotonic()-started>900:
  raise ValueError('bounded streamed evidence copy exceeded')
 pending+=raw.decode('utf-8')
 if len(pending)>40000000:raise ValueError('SQL statement budget')
 if sqlite3.complete_statement(pending):
  connection.execute(pending);pending='';statements+=1
if pending.strip() or connection.in_transaction:
 raise ValueError('incomplete consistent SQL dump')
check=connection.execute('PRAGMA quick_check').fetchall()
if check!=[('ok',)]:raise ValueError('copied SQLite integrity check failed')
objects=connection.execute('SELECT COUNT(*),COALESCE(SUM(length(ciphertext)),0) FROM sealed_objects').fetchone()
slots=connection.execute('SELECT COUNT(*) FROM key_slots').fetchone()[0]
connection.close()
print(json.dumps({'destination':str(base),'dump_sha256':digest.hexdigest(),'dump_bytes':size,
 'sealed_objects':objects[0],'ciphertext_bytes':objects[1],'key_slots':slots,
 'quick_check':'ok','statements':statements,'originals_deleted':False}),flush=True)
'''

FILES_PROGRAM = r'''
import hashlib,json,os,sys,tarfile
from pathlib import Path
base=Path('/home/jt/atmem-benchmark-runtime-20261018/bookkeeping-v1')
expected=job['files'];seen=set();total=0
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:
 for member in archive:
  name=member.name
  if name not in expected or name in seen or not member.isfile() or member.size!=expected[name]['bytes']:
   raise ValueError('unexpected protected companion member')
  if member.size>256000000:raise ValueError('companion member size cap')
  target=base/name
  if target.is_symlink() or target.exists():raise ValueError('protected companion must not be overwritten')
  target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  if not target.parent.resolve().is_relative_to(base):raise ValueError('companion path escape')
  digest=hashlib.sha256();size=0
  with archive.extractfile(member) as source,target.open('xb') as output:
   os.chmod(target,0o600)
   while True:
    raw=source.read(65536)
    if not raw:break
    digest.update(raw);size+=len(raw);output.write(raw)
  if size!=member.size or digest.hexdigest()!=expected[name]['sha256']:
   raise ValueError('protected companion bytes differ')
  total+=size;seen.add(name)
if seen!=set(expected):raise ValueError('protected companions missing')
print(json.dumps({'members':len(seen),'bytes':total,'all_companions_verified':True,
 'key_contents_printed':False,'originals_deleted':False}),flush=True)
'''


def main():
    scope = EvidenceScope("benchmark", "local-operator", "click-20261017")
    principal = EvidencePrincipal("local-benchmark-operator", EvidenceRole.ADMINISTRATOR, scope)
    # Separate normal protected vault prevents rescanning the large source vault
    # merely to record this operational copy. No product/storage policy bypass.
    vault = ReplayEvidence(ROOT / "operator-copy-v1/vault", vault_id="operator-copy-v1", scope=scope)
    run = "external-windows-operator-copy-v1-20261018"
    if vault.inspect(principal, run):
        raise ValueError("copy already recorded; inspect original handle")
    source = ROOT / "confirmation-v1"
    database = source / "vault/protected-evidence.db"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        expected = connection.execute("SELECT COUNT(*),COALESCE(SUM(length(ciphertext)),0) FROM sealed_objects").fetchone()
        slots = connection.execute("SELECT COUNT(*) FROM key_slots").fetchone()[0]
    allowed = [
        ".evidence-keys/confirmation-v1.key", ".evidence-identity-keys/confirmation-v1.key",
        ".evidence-accounts/confirmation-v1.json", "identity/artifact.key",
    ]
    files = {}
    for name in allowed:
        path = source / name
        if path.exists():
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 256_000:
                raise ValueError("bounded regular protected companion required")
            files["confirmation-v1/" + name] = path
    for path in (source / "artifacts/sha256").glob("*/*.blob"):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 256_000_000:
            raise ValueError("bounded regular encrypted artifact companion required")
        files["confirmation-v1/" + path.relative_to(source).as_posix()] = path
    if not (source / allowed[0]).exists() or not (source / allowed[1]).exists():
        raise ValueError("existing benchmark evidence/identity keys required")
    manifest = {}
    for name, path in files.items():
        digest = sha256()
        with path.open("rb") as reader:
            for chunk in iter(lambda: reader.read(65536), b""):
                digest.update(chunk)
        manifest[name] = {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}
    def save(kind, payload):
        return vault.capture(run_id=run, kind=kind, principal=principal, payload=payload)
    save("external.operator_copy_planned", {
        "driver_source": Path(__file__).read_text(), "sql_program": SQL_PROGRAM,
        "files_program": FILES_PROGRAM, "destination": DESTINATION,
        "source_database": str(database), "source_sealed_objects": expected[0],
        "source_ciphertext_bytes": expected[1], "source_key_slots": slots,
        "companion_manifest": manifest, "originals_deleted": False,
        "reason": "Mac disk/swap exhaustion from shared-vault bookkeeping; all three owned drivers stopped",
    })
    command = framed_command()
    dump = subprocess.Popen(["/usr/bin/sqlite3", "-readonly", str(database), ".dump"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    remote = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest, size = sha256(), 0
    try:
        remote.stdin.write(framed_input({"program": SQL_PROGRAM}))
        while True:
            chunk = dump.stdout.read(65536)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            if size > 4_000_000_000:
                raise ValueError("source dump byte budget")
            remote.stdin.write(chunk)
        remote.stdin.close()
        remote.stdin = None
        dump.wait(timeout=30)
        if dump.returncode:
            raise ValueError("source SQL dump failed: " + dump.stderr.read().decode(errors="replace"))
        stdout, stderr = remote.communicate(timeout=930)
    finally:
        for process in (dump, remote):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    record = {"transport_exit": remote.returncode, "stdout_base64": base64.b64encode(stdout).decode(),
              "stderr_base64": base64.b64encode(stderr).decode(),
              "sent_dump_sha256": digest.hexdigest(), "sent_dump_bytes": size}
    if remote.returncode == 0:
        record["result"] = json.loads(stdout)
    save("external.operator_database_copy", record)
    result = record.get("result", {})
    if (remote.returncode != 0 or result.get("dump_sha256") != digest.hexdigest()
        or result.get("dump_bytes") != size or result.get("sealed_objects") != expected[0]
        or result.get("ciphertext_bytes") != expected[1] or result.get("key_slots") != slots
        or result.get("quick_check") != "ok"):
        raise ValueError("consistent copied database identity failed; original remains intact")
    remote = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        remote.stdin.write(framed_input({"program": FILES_PROGRAM, "files": manifest}))
        with tarfile.open(fileobj=remote.stdin, mode="w|") as archive:
            for name, path in files.items():
                info = tarfile.TarInfo(name)
                info.size, info.mode = path.stat().st_size, 0o600
                with path.open("rb") as reader:
                    archive.addfile(info, reader)
        remote.stdin.close()
        remote.stdin = None
        stdout, stderr = remote.communicate(timeout=180)
    finally:
        if remote.poll() is None:
            remote.terminate()
            remote.wait(timeout=10)
    record = {"transport_exit": remote.returncode, "stdout_base64": base64.b64encode(stdout).decode(),
              "stderr_base64": base64.b64encode(stderr).decode()}
    if remote.returncode == 0:
        record["result"] = json.loads(stdout)
    save("external.operator_companion_copy", record)
    if remote.returncode != 0 or record.get("result", {}).get("all_companions_verified") is not True:
        raise ValueError("companion copy incomplete; original remains intact")
    summary = {"destination": DESTINATION, "sealed_objects": expected[0], "ciphertext_bytes": expected[1],
               "database_and_companions_verified": True, "originals_deleted": False,
               "Mac_large_vault_reopened": False}
    save("external.operator_copy_completed", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
