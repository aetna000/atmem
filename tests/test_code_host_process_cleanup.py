"""Fixture-only descendant cleanup; does not claim host feature support."""
import os
from pathlib import Path
import runpy
import sys

import pytest


@pytest.mark.skipif(os.name == 'nt', reason='POSIX process-group regression')
def test_owned_cli_descendants_stop_before_temp_home_cleanup(tmp_path):
    run = runpy.run_path(str(Path(__file__).parent / 'fixtures/host_process.py'))['run_owned_cli']
    # The descendant drops stdio, so the parent exits without waiting for it.
    result = run([sys.executable, '-c',
        'import subprocess,sys; subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],'
        'stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); print("main completed")'],
        cwd=tmp_path, env=os.environ.copy(), timeout=5)
    assert result.returncode == 0 and result.stdout == 'main completed\n'
