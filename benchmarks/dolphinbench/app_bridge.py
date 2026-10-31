"""Reuse DolphinBench's app bridge; only the macOS socket location differs."""
from contextlib import contextmanager
import os
from pathlib import Path
import threading
import tempfile


@contextmanager
def bridge(apps, socket_path):
    from reference.execution.agent_container import AppBridge
    path = Path(socket_path)
    if path.exists():
        raise ValueError('Refusing to replace an existing app socket')
    environment = {'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1',
                   'LANG': 'en_US.UTF-8', **apps['env']}
    server = AppBridge(path, [apps['command'], *apps['args']], environment)
    os.chmod(path, 0o600)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield path
    finally:
        server.stop()
        thread.join(10)
        path.unlink(missing_ok=True)


def stage_client(upstream_root, target, socket_path):
    """Location-only adaptation of the upstream byte-forwarding client."""
    from .gateway import save_new
    import hashlib
    source = Path(upstream_root) / 'reference/execution/app_client.py'
    original = source.read_text()
    if original.count('"/run/apps.sock"') != 1:
        raise ValueError('Upstream app client changed; requalify adaptation')
    target = Path(target)
    adapted = original.replace('"/run/apps.sock"', repr(str(socket_path)))
    adapted = adapted.replace('def main():', 'def main():\n    print("AtMem app byte-forwarder started", file=sys.stderr, flush=True)')
    adapted = adapted.replace('        def send():', '        print("AtMem app socket connected", file=sys.stderr, flush=True)\n\n        def send():')
    with target.open('x') as output:
        output.write(adapted)
    save_new(target.with_suffix('.provenance.json'), {
        'source': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'modification': 'Unix socket path and stderr-only connection diagnostics; forwarding unchanged',
        'adapted_sha256': hashlib.sha256(target.read_bytes()).hexdigest()})


@contextmanager
def short_socket():
    """Use a private, short socket path independent of the benchmark run root."""
    # /private/tmp is macOS-specific; /tmp is short on both macOS and Linux.
    base = Path('/tmp') if Path('/tmp').is_dir() else Path(tempfile.gettempdir())
    with tempfile.TemporaryDirectory(prefix='am-app-', dir=base) as directory:
        os.chmod(directory, 0o700)
        path = Path(directory) / 'a.sock'
        if len(os.fsencode(path)) >= 104:
            raise ValueError('App socket exceeds portable macOS Unix path limit')
        yield path
