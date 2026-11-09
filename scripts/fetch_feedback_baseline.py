#!/usr/bin/env python3
"""Explicitly fetch a public pinned wheel for the upgrade gate; no user data."""
from hashlib import sha256
import argparse
import json
from pathlib import Path
from urllib.request import urlopen

SHA256 = '37597be588817aa2dad921a683b39b6e6417eb5bdf3ec23256655acf13b19a03'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    target=Path(args.output)
    if target.exists():
        if sha256(target.read_bytes()).hexdigest()!=SHA256:
            raise SystemExit('Existing baseline wheel checksum differs; refusing to overwrite')
        return
    with urlopen('https://pypi.org/pypi/atmem/2.3.14/json',timeout=15) as response:
        files=json.load(response)['urls']
    wheel=next(item for item in files if item['filename']=='atmem-2.3.14-py3-none-any.whl')
    if wheel['digests']['sha256']!=SHA256 or wheel['yanked'] or not wheel['url'].startswith('https://files.pythonhosted.org/'):
        raise SystemExit('Published baseline identity mismatch')
    with urlopen(wheel['url'],timeout=30) as response:
        data=response.read(20_000_001)
    if len(data)>20_000_000 or sha256(data).hexdigest()!=SHA256:
        raise SystemExit('Baseline wheel checksum/budget mismatch')
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as stream:
        stream.write(data)
    print('Verified public AtMem 2.3.14 baseline wheel.')


if __name__=='__main__':main()
