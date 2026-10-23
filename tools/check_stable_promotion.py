"""Refuse functional drift while promoting the published 2.3.10b1 artifact."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-wheel', type=Path, required=True)
    parser.add_argument('--baseline-ref', default='v2.3.10b1')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    expected = 'd5d3a23e3005392f8291f8c1201b3226752420f5841128e9eb40346d7f2d3c2b'
    if hashlib.sha256(args.baseline_wheel.read_bytes()).hexdigest() != expected:
        raise RuntimeError('Not the recorded published benchmark beta wheel')
    allowed = {'atmem/mcp/server.py': (b'SERVER_VERSION = "2.3.10b1"', b'SERVER_VERSION = "2.3.10"'),
               'atmem/openclaw_install.py': (b'OPENCLAW_PLUGIN_VERSION = "2.3.10-beta.1"', b'OPENCLAW_PLUGIN_VERSION = "2.3.10"')}
    checked, changes = {}, []
    with zipfile.ZipFile(args.baseline_wheel) as wheel:
        for name in wheel.namelist():
            if not name.startswith('atmem/') or name.endswith('/'):
                continue
            baseline = wheel.read(name)
            current = (root / name).read_bytes()
            if name in allowed:
                old, new = allowed[name]
                if baseline.count(old) != 1 or current.count(new) != 1:
                    raise RuntimeError('Version constant absent/ambiguous: ' + name)
                if current != baseline.replace(old, new):
                    raise RuntimeError('Unexpected functional change: ' + name)
                changes.append(name)
            elif current != baseline:
                raise RuntimeError('Unexpected shipped-file change: ' + name)
            checked[name] = hashlib.sha256(current).hexdigest()
    for directory in ('packages/atbot', 'integrations/openclaw/src'):
        result = subprocess.run(['git', 'diff', '--exit-code', args.baseline_ref, '--', directory],
                                cwd=root, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('Changed companion/bridge implementation: ' + directory)
    import tomllib
    baseline_project = tomllib.loads(subprocess.check_output(
        ['git', 'show', args.baseline_ref + ':pyproject.toml'], cwd=root, text=True))['project']
    stable_project = tomllib.loads((root / 'pyproject.toml').read_text())['project']
    for key in ('dependencies', 'optional-dependencies', 'requires-python'):
        if baseline_project[key] != stable_project[key]:
            raise RuntimeError('Dependency/runtime contract changed: ' + key)
    print(json.dumps({'baseline_version': '2.3.10b1', 'stable_version': '2.3.10',
        'baseline_wheel_sha256': expected, 'checked_shipped_files': len(checked),
        'version_constant_only_changes': changes, 'companion_and_bridge_source_unchanged': True,
        'dependency_and_python_contract_unchanged': True,
        'stable_product_payload_digest': hashlib.sha256(json.dumps(checked, sort_keys=True).encode()).hexdigest()}, indent=2))


if __name__ == '__main__':
    main()
