"""Recover public immutable audit inputs without Codex history or private keys."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request


REVISION = '5ef528c499aa26b765fff9d8ed8f2c2e6ee52912'
BASE = 'https://huggingface.co/datasets/atmem/atmem-2.3.10b1-dolphinbench/resolve/' + REVISION + '/'
ZIP_SHA = '78788ad3455d04407c037706d3ff129d56eafff89beaac101f2a461cb58d7538'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    archive = args.output / 'submission.zip'
    if archive.exists():
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == ZIP_SHA, 'Existing ZIP differs; not overwritten'
    else:
        with urllib.request.urlopen(BASE + 'submission.zip', timeout=120) as response:
            raw = response.read()
        assert hashlib.sha256(raw).hexdigest() == ZIP_SHA
        with archive.open('xb') as output:
            output.write(raw)
    with urllib.request.urlopen(BASE + 'data/tasks.jsonl', timeout=120) as response:
        rows = [json.loads(line) for line in response if line.strip()]
    assert len(rows) == len({r['id'] for r in rows}) == 600
    assert sum(r['passed'] for r in rows) == 390
    payload = json.dumps(rows).encode()
    target = args.output / 'rows.json'
    if target.exists():
        assert target.read_bytes() == payload, 'Existing rows differ; not overwritten'
    else:
        with target.open('xb') as output:
            output.write(payload)
    print(json.dumps({'revision': REVISION, 'submission_sha256': ZIP_SHA,
                      'rows_sha256': hashlib.sha256(payload).hexdigest(),
                      'tasks': len(rows), 'model_calls': 0}))


if __name__ == '__main__':
    main()
