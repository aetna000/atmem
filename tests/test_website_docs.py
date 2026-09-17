"""Execute the actual published quickstart, with all socket access denied."""
import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_website_inventory():
    runpy.run_path(str(ROOT / 'scripts/check_website_docs.py'))['validate']()


def test_http_inventory_covers_current_routes():
    handler = (ROOT / 'atmem/control/web.py').read_text()
    guide = (ROOT / 'docs/http-api.md').read_text()
    for path in set(re.findall(r'path == "(/v1/[^"]+)"', handler)):
        assert f'`{path}`' in guide, f'undocumented HTTP route: {path}'
    schema = (ROOT / 'docs/contracts/atmem-api-v1.openapi.yaml').read_text()
    assert 'url: http://127.0.0.1:8765/v1' in schema
    assert not re.search(r'^  /v1/', schema, re.M), 'server base already includes v1'


def test_documented_quickstart_offline(monkeypatch):
    import socket

    def denied(*args, **kwargs):
        raise AssertionError('quickstart must not use the network')

    monkeypatch.setattr(socket, 'socket', denied)
    text = (ROOT / 'docs/website/getting-started.md').read_text()
    blocks = re.findall(r'```python\n(.*?)```', text, re.S)
    assert len(blocks) == 1
    exec(compile(blocks[0], 'documented-quickstart', 'exec'), {})
