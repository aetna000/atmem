"""Scoped read-only WSL heartbeat; no system sleep or idle settings are changed."""
import json
from pathlib import Path
import time
from benchmarks.code_replay.swebench_pilot import remote


def main():
    stop = Path('/private/tmp/atmem-swebench-wsl-heartbeat-20261019.stop')
    previous = None
    while not stop.exists():
        r = remote("from pathlib import Path;import json;print(json.dumps({'boot':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}))", timeout=30)
        if r.returncode:
            print(json.dumps({'heartbeat': 'failed', 'exit': r.returncode}), flush=True)
        else:
            current = json.loads(r.stdout)['boot']
            if current != previous:
                print(json.dumps({'heartbeat': 'active', 'boot_changed': previous is not None, 'boot_id': current}), flush=True)
            previous = current
        time.sleep(15)


if __name__ == '__main__':
    main()
