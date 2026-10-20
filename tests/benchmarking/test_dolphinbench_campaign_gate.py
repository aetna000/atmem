"""Prevent the unqualified private adapter becoming a full paid submission run."""
from pathlib import Path
import subprocess
import sys


def test_unqualified_full_campaign_fails_before_creating_output(tmp_path):
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / 'must-not-be-created'
    script = ('import sys;sys.path.append(' + repr(str(root)) + ');'
              'from benchmarks.dolphinbench.campaign import main;main()')
    result = subprocess.run([sys.executable, '-I', '-c', script,
        '--output', str(output), '--env-file', str(tmp_path / 'no-credentials'),
        '--confirm-paid-calls'], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert 'Full paid execution is blocked' in result.stderr
    assert not output.exists()
