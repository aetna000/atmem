"""Collect existing product acceptance results; never execute or repair work."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import gzip


def collect(installed: Path, atflows: Path, wheels: Path, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    report = json.loads(installed.read_text())
    flow_report = json.loads(atflows.read_text())
    assert report['format'] == 'installed-continuity-acceptance-v1'
    assert flow_report['passed'] is True
    shutil.copyfile(installed, output / 'installed-crash-raw.json')
    shutil.copyfile(atflows, output / 'atflows-http-raw.json')
    summary = {'format': 'continuity-product-acceptance-summary-v1',
        'evidence_class': 'installed-product-functional-acceptance',
        'not_claimed': ['autonomous retail score', 'held-out performance gain', 'production-wide failure rate'],
        'cases': [{'fault': case['fault'], 'effects_after_resume': case['external_effects'],
                   'attempt_modes': [a['mode'] for a in case['after']['operations'][0]['attempts']],
                   'final_status': case['after']['operations'][0]['status'],
                   'lease_wait_seconds': case['actual_wait_seconds'],
                   'document_sha256': case['document_sha256']} for case in report['cases']],
        'atflows_http_passed': True,
        'wheels': {file.name: sha256(file.read_bytes()).hexdigest() for file in wheels.glob('*.whl')}}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    manifest = {file.name: sha256(file.read_bytes()).hexdigest() for file in output.iterdir() if file.is_file()}
    (output / 'SHA256SUMS.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return summary


def collect_retail(source: Path, output: Path):
    """Archive only public workload outputs, never server state or credentials."""
    output.mkdir(parents=True, exist_ok=False)
    summary = json.loads((source / 'summary.json').read_text())
    assert summary['evidence_class'] == 'public-native-cassette-four-arm-no-fault-qualification'
    graphs = []
    for arm in ['baseline', 'atmem', 'atflows', 'both']:
        raw = (source / (arm + '.json')).read_bytes()
        data = json.loads(raw)
        assert data['arm'] == arm and data['trajectory_matches'] is True
        graphs.append(data['graph'])
        (output / (arm + '.json.gz')).write_bytes(gzip.compress(raw, mtime=0))
    assert all(graph == graphs[0] for graph in graphs)
    summary['graph_topology_equal'] = True
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (output / 'SHA256SUMS.json').write_text(json.dumps({p.name: sha256(p.read_bytes()).hexdigest()
        for p in output.iterdir() if p.is_file()}, indent=2) + '\n')
    return summary


def capture_observer(url, username, password, output: Path):
    """Read the actual observer projection; never invent missing events/prices."""
    from urllib.request import Request, build_opener, ProxyHandler
    opener = build_opener(ProxyHandler({}))
    request = Request(url + '/api/auth/login', data=json.dumps({'username': username, 'password': password}).encode(),
                      headers={'Content-Type': 'application/json', 'Origin': url})
    with opener.open(request) as response:
        cookie = response.headers['Set-Cookie'].split(';')[0]
    with opener.open(Request(url + '/api/continuity', headers={'Cookie': cookie})) as response:
        view = json.load(response)
    output.write_text(json.dumps(view, indent=2) + '\n')
    return {'workflows': len(view['workflows']), 'events': sum(len(w['events']) for w in view['workflows']),
            'unknown_cost_attempts': sum(w['unknown_cost_attempts'] for w in view['workflows'])}


def collect_faults(source: Path, output: Path):
    """Export public native journal and classifications, not credentials or vault."""
    summary = json.loads((source / 'summary.json').read_text())
    if summary['evidence_class'] != 'public-retail-recorded-response-fault-qualification':
        raise ValueError('unexpected evidence class')
    output.mkdir(parents=True, exist_ok=False)
    for arm in ['baseline', 'atmem', 'atflows', 'both']:
        raw = (source / arm / 'observations.json').read_bytes()
        (output / (arm + '.json.gz')).write_bytes(gzip.compress(raw, mtime=0))
    for name in ['summary.json', 'protocol.json']:
        shutil.copyfile(source / name, output / name)
    (output / 'SHA256SUMS.json').write_text(json.dumps({p.name: sha256(p.read_bytes()).hexdigest()
        for p in output.iterdir() if p.is_file()}, indent=2) + '\n')
    return summary


def collect_live(source: Path, output: Path, *, forbidden_values=()):
    """Publish only explicitly selected public-corpus JSON, never server state."""
    summary = json.loads((source / 'summary.json').read_text())
    if summary['evidence_class'] != 'fresh-public-retail-engineering-pilot':
        raise ValueError('unexpected live evidence class')
    files = [source / name for name in ['manifest.json', 'schedule.json', 'summary.json']]
    for arm in ['baseline', 'atmem', 'atflows', 'both']:
        files.extend((source / arm).glob('*.json'))
    for path in files:
        raw = path.read_bytes()
        if any(secret and secret.encode() in raw for secret in forbidden_values):
            raise ValueError('credential detected in candidate public export')
    output.mkdir(parents=True, exist_ok=False)
    for path in files:
        relative = path.relative_to(source)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative.parent == Path('.'):
            shutil.copyfile(path, target)
        else:
            target.with_suffix('.json.gz').write_bytes(gzip.compress(path.read_bytes(), mtime=0))
    (output / 'SHA256SUMS.json').write_text(json.dumps({str(path.relative_to(output)): sha256(path.read_bytes()).hexdigest()
        for path in output.rglob('*') if path.is_file()}, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--atflows', type=Path, required=True)
    parser.add_argument('--wheels', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.installed, args.atflows, args.wheels, args.output), indent=2))
