"""Prevent the unqualified private adapter becoming a full paid submission run."""
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize('extra,expected', [
    ([], 'Full paid execution is blocked'),
    (['--pilot-sessions', '26'], 'limited to 25 ingestion interactions'),
])
def test_unqualified_campaign_fails_before_creating_output(tmp_path, extra, expected):
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / 'must-not-be-created'
    script = ('import sys;sys.path.append(' + repr(str(root)) + ');'
              'from benchmarks.dolphinbench.campaign import main;main()')
    result = subprocess.run([sys.executable, '-I', '-c', script,
        '--output', str(output), '--env-file', str(tmp_path / 'no-credentials'),
        '--confirm-paid-calls', *extra], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert expected in result.stderr
    assert not output.exists()
