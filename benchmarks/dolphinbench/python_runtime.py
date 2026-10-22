"""Read-only interpreter qualification before reserving benchmark spend."""
from __future__ import annotations

import hashlib
import json
import base64
from pathlib import Path
import subprocess

PROBE='''import json,sys,ssl,pathlib
base=pathlib.Path(sys.base_prefix)
print(json.dumps({'executable':str(pathlib.Path(sys.executable).resolve()),
 'base_prefix':str(base),'version':sys.version,'platform':sys.platform,
 'openssl':ssl.OPENSSL_VERSION,
 'shared_libraries':[str(p.resolve()) for p in (base/'lib').glob('libpython*.dylib')]}))'''


def qualify_python(executable):
    result=subprocess.run([str(executable),'-I','-c',PROBE],check=True,
        capture_output=True,text=True,timeout=30)
    value=json.loads(result.stdout)
    targets=[Path(value['executable']),*map(Path,value['shared_libraries'])]
    if value['platform']=='darwin':
        for path in targets:
            signature=subprocess.run(['codesign','--verify','--strict',str(path)],
                capture_output=True,text=True,timeout=30)
            if signature.returncode:
                raise ValueError('Python code signature verification failed: '+str(path))
    value['binary_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in targets}
    value['macos_code_signatures_verified']=value['platform']=='darwin'
    return value


PACKAGE_PROBE = '''import importlib.metadata,json,sysconfig
print(json.dumps({'site':sysconfig.get_paths()['purelib'], 'distributions':[
 {'name':d.metadata['Name'],'version':d.version,'files':[
  {'path':str(f),'hash':str(f.hash) if f.hash else None}
  for f in (d.files or []) if str(f).endswith(('.py','.so','.dylib'))]}
 for d in importlib.metadata.distributions()]}))'''


def qualify_application(executable):
    """Verify installed wheel payloads before importing native MCP dependencies.

    Interpreter signatures alone do not cover extension modules. RECORD is the
    installed wheel's expected payload, not a newly calculated approval of a
    possibly damaged binary. Keep imports after verification to avoid SIGKILL.
    """
    result = subprocess.run([str(executable), '-I', '-c', PACKAGE_PROBE],
        capture_output=True, text=True, check=True, timeout=30)
    value = json.loads(result.stdout)
    site = Path(value['site']).resolve()
    payload = {}
    packages = {}
    for dist in value['distributions']:
        name = dist['name'].lower().replace('_', '-')
        if name in packages:
            raise ValueError('Duplicate installed application distribution')
        packages[name] = dist['version']
        for file in dist['files']:
            path = (site / file['path']).resolve()
            if not path.is_relative_to(site):
                raise ValueError('Application wheel payload escapes site-packages')
            expected = file['hash']
            if not expected or not expected.startswith('<FileHash mode: sha256 value: '):
                raise ValueError('Application wheel payload lacks SHA256 RECORD hash')
            encoded = base64.urlsafe_b64encode(hashlib.sha256(path.read_bytes()).digest()).decode().rstrip('=')
            if expected != '<FileHash mode: sha256 value: '+encoded+'>':
                raise ValueError('Application wheel payload differs from RECORD: '+str(path))
            relative = path.relative_to(site).as_posix()
            if relative in payload and payload[relative] != encoded:
                raise ValueError('Conflicting application wheel payload')
            payload[relative] = encoded
    if not payload:
        raise ValueError('Application wheel payload inventory is empty')
    subprocess.run([str(executable), '-I', '-c', 'import mcp,pydantic,rpds'],
        capture_output=True, text=True, check=True, timeout=30)
    return {'packages':packages, 'payload_sha256_base64':payload,
            'wheel_record_verified':True, 'mcp_import_verified':True}


def qualify_application_repair(previous, replacement):
    """Allow relocation/repair only to identical declared wheel code payloads."""
    # Inspect prior expected RECORD metadata without importing damaged extensions.
    result = subprocess.run([str(previous), '-I', '-c', PACKAGE_PROBE],
        capture_output=True, text=True, check=True, timeout=30)
    old = json.loads(result.stdout)
    current = qualify_application(replacement)
    packages = {d['name'].lower().replace('_','-'):d['version'] for d in old['distributions']}
    expected = {f['path']:f['hash'] for d in old['distributions'] for f in d['files']}
    actual = {p:'<FileHash mode: sha256 value: '+h+'>'
              for p,h in current['payload_sha256_base64'].items()}
    if packages != current['packages'] or expected != actual:
        raise ValueError('Replacement application package code or versions changed')
    return {'previous':str(previous),'replacement':str(replacement),
            'identical_expected_wheel_payload':True, 'replacement_inventory':current}
