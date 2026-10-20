"""Capture harmless test-host fields before calling the real installed hook."""
import io
from pathlib import Path
import runpy
import sys

data = sys.stdin.buffer.read()
Path("code-hook-input.json").write_bytes(data)
sys.stdin = io.TextIOWrapper(io.BytesIO(data), encoding="utf-8")
script = sys.argv.pop(1)
runpy.run_path(script, run_name="__main__")
