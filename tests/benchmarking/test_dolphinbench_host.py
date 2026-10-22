import importlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[2]))
driver = importlib.import_module('benchmarks.dolphinbench.driver')


def test_portable_backup_uses_product_export_and_explicit_tenant(tmp_path):
    from atmem.interchange import read_archive
    host = driver.AtMemHost(tmp_path / 'host', 'isolated-fixture')
    try:
        receipt = host.portable_export(tmp_path / 'memory.jsonl')
        manifest, records = read_archive(tmp_path / 'memory.jsonl')
        assert receipt['scope_map']['tenant_id'] == 'local'
        assert manifest.record_count == len(records) == 0
    finally:
        host.stop()
